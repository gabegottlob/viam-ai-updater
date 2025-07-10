import os
from google import genai
from google.genai import types
from pydantic import BaseModel
import argparse
import subprocess

from prompts.getrelevantcontext_prompts import GETRELEVANTCONTEXT_P, GETRELEVANTCONTEXT_S
from prompts.diffparser_prompts import DIFFPARSER_P, DIFFPARSER_S
from prompts.generateimplementations_prompts import GENERATEIMPLEMENTATIONS_P, GENERATEIMPLEMENTATIONS_S

class ContextFiles(BaseModel):
    """Model for storing the files that should be included as context."""
    file_paths: list[str]
    explanation: list[str]

class RequiredChanges(BaseModel):
    """Model for storing analysis of code needed based on diff."""
    files_to_update: list[str]
    implementation_details: list[str]

class GeneratedFiles(BaseModel):
    """Model for storing AI-generated file content."""
    file_paths: list[str]
    file_contents: list[str]

def write_to_file(filepath: str, content: str) -> None:
    """Write content to a file at the specified path. This will overwrite the existing file contents if it already exists.

    Args:
        filepath: Path to the file to write
        content: Content to write to the file
    """
    print(f"Writing to: {filepath}")
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"Successfully wrote to: {filepath} \n")

def read_file_content(file_path) -> str:
    """Read and return the content of a file.

    Args:
        file_path: Path to the file to read

    Returns:
        str: Content of the file or error message if reading fails
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

class AIUpdater:
    """Class for updating SDK code based on proto changes using AI."""

    def __init__(self, args, api_key=""):
        """Initialize the AIUpdater.

        Args:
            args: Command line arguments
            api_key (str): Google API key. If None, will use GOOGLE_API_KEY env var
        """
        self.args = args

        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        if args.test:
            self.sdk_root_dir = args.test
        elif args.work:
            self.sdk_root_dir = args.work
        else:
            self.sdk_root_dir = os.path.dirname(self.current_dir)

        # Initialize the Gemini client
        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set and no API key provided")
        self.client = genai.Client(api_key=api_key)
        self.total_cost = 0.0

    def calculate_cost(self, usage_metadata: types.GenerateContentResponse.UsageMetadata, model: str) -> float:
        """Calculates the estimated cost of a Gemini response.

        Args:
            usage_metadata: The usage_metadata object from the Gemini response.
            model: The name of the Gemini model used to generate the response.

        Returns:
            float: The estimated cost of the response.
        """
        if model == "gemini-2.5-flash":
            INPUT_COST_PER_MILLION_TOKENS = 0.30
            OUTPUT_COST_PER_MILLION_TOKENS = 2.50
        else:
            print(f"WARNING: {model} is not a supported model for cost calculation")
            return 0.0

        input_tokens = usage_metadata.prompt_token_count
        output_tokens = usage_metadata.candidates_token_count

        cost = (input_tokens / 1_000_000) * INPUT_COST_PER_MILLION_TOKENS + (output_tokens / 1_000_000) * OUTPUT_COST_PER_MILLION_TOKENS
        return cost

    def get_relevant_context(self, git_diff_output: str) -> types.GenerateContentResponse:
        """Utilizes AI to gather relevant context files for analysis.

        Args:
            git_diff_output (str): Git diff output containing proto/code changes

        Returns:
            GenerateContentResponse: Gemini LLM response containing relevant files
        """
        sdk_tree_output = subprocess.check_output(["tree", os.path.join("src", "viam")], text=True, cwd=self.sdk_root_dir)
        tests_tree_output = subprocess.check_output(["tree", "tests"], text=True, cwd=self.sdk_root_dir)

        prompt = GETRELEVANTCONTEXT_P.format(
            sdk_tree_structure=sdk_tree_output,
            tests_tree_structure=tests_tree_output,
            git_diff_output=git_diff_output
        )

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=ContextFiles,
                thinking_config=types.ThinkingConfig(thinking_budget=-1),
                system_instruction=GETRELEVANTCONTEXT_S
            )
        )
        print(f"Model version: {response.model_version}")
        print(f"Token data from from context gathering call: {response.usage_metadata.total_token_count}\n")
        self.total_cost += self.calculate_cost(response.usage_metadata, "gemini-2.5-flash")
        return response

    def get_diff_analysis(self, git_diff_output: str, relevant_files: list[str]) -> types.GenerateContentResponse:
        """Analyze git diff using LLM to identify required code changes.

        Args:
            git_diff_output: Git diff output as string
            relevant_files: List of relevant file paths for context

        Returns:
            GenerateContentResponse: LLM response containing analysis of needed changes
        """
        # Gather relevant context files from the project and format them for the prompt
        relevant_context = ""
        for file in relevant_files:
            file_path = os.path.join(self.sdk_root_dir, file)
            file_content = read_file_content(file_path)
            relevant_context += f"File: {file}\nContent: \n{file_content}\n--------------------------------\n"

        if self.args.debug and self.args.test:
            write_to_file(os.path.join(self.current_dir, "relevantcontexttest.txt"), relevant_context)

        # Format the prompt with gathered context
        prompt = DIFFPARSER_P.format(selected_context_files=relevant_context, git_diff_output=git_diff_output)

        # Generate content if AI is enabled, otherwise return empty response
        response =self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=RequiredChanges,
                thinking_config=types.ThinkingConfig(thinking_budget=-1),
                system_instruction=DIFFPARSER_S
            )
        )

        # Count tokens for logging
        print(f"Model version: {response.model_version}")
        print(f"Token data from from diff analysis call: {response.usage_metadata.total_token_count}\n")
        self.total_cost += self.calculate_cost(response.usage_metadata, "gemini-2.5-flash")
        return response

    def generate_implementations(self, diff_analysis: types.GenerateContentResponse):
        """Generate implementation code based on diff analysis.

        Args:
            diff_analysis: LLM response from diff analysis
        """
        # Parse the response from diff analysis (according to defined Pydantic model)
        parsed_response: RequiredChanges = diff_analysis.parsed

        # Add existing files content to the prompt
        existing_files_text = "\n=== EXISTING FILES ===\n"
        for file_path in parsed_response.files_to_update:
            try:
                with open(os.path.join(self.sdk_root_dir, file_path), 'r') as f:
                    file_content = f.read()
                    existing_files_text += f"\n=== {file_path} ===\n{file_content}\n"
            except FileNotFoundError:
                print(f"Warning: File {file_path} not found. Skipping this file.")
            except Exception as e:
                print(f"Error reading file {file_path}: {str(e)}")

        prompt = GENERATEIMPLEMENTATIONS_P.format(implementation_details=parsed_response.implementation_details, existing_files_text=existing_files_text)

        # Generate and write files if AI is enabled
        if not self.args.noai:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema=GeneratedFiles,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    system_instruction=GENERATEIMPLEMENTATIONS_S
                )
                )
            print(f"Model version: {response.model_version}")
            print(f"Token data from from implementation generation call: {response.usage_metadata.total_token_count}\n")
            self.total_cost += self.calculate_cost(response.usage_metadata, "gemini-2.5-flash")

            # Write the generated content to files
            parsed_response: GeneratedFiles = response.parsed
            if self.args.debug and self.args.test:
                write_to_file(os.path.join(self.current_dir, "generatedfilestest.txt"), response.text)

            if(len(parsed_response.file_paths) != len(parsed_response.file_contents)):
                raise ValueError("ERROR: AI OUTPUT A DIFFERENT NUMBER OF FILENAMES THAN GENERATED FILE CONTENTS")

            if(len(parsed_response.file_paths) == 0):
                print("THE AI WORKFLOW DID NOT DETERMINE THAT ANY FILES NEED TO BE UPDATED")
                return

            for index, file_path in enumerate(parsed_response.file_paths):
                # Output AI generated files
                original_file_dir = os.path.dirname(os.path.join(self.sdk_root_dir, file_path))
                original_filename = os.path.basename(file_path)
                filename_without_ext, file_ext = os.path.splitext(original_filename)
                ai_filename = f"{filename_without_ext}{file_ext}"
                if self.args.test:
                    dir_structure = os.path.relpath(original_file_dir, self.sdk_root_dir)
                    ai_generated_dir = os.path.join(os.path.dirname(self.sdk_root_dir), "ai_generated", dir_structure)
                    os.makedirs(ai_generated_dir, exist_ok=True)
                    ai_file_path = os.path.join(ai_generated_dir, ai_filename)
                elif self.args.work:
                    ai_file_path = os.path.join(original_file_dir, ai_filename)
                write_to_file(ai_file_path, parsed_response.file_contents[index])

    def run(self):
        """Main execution method for the AI updater."""
        # Get diff and output (and write to file for debugging)
        # Note: the way I am currently doing git diff excludes the _pb2.py files because it clutters the diff and confuses the LLM
        git_diff_dir = os.path.join(self.sdk_root_dir, "src", "viam", "gen")

        if self.args.test:
            # Check if specific proto diff file was specified for testing reasons
            scenario_dir = os.path.dirname(self.sdk_root_dir)
            if os.path.exists(os.path.join(scenario_dir, "proto_diff.txt")):
                with open(os.path.join(scenario_dir, "proto_diff.txt"), "r") as f:
                    git_diff_output = f.read()
            else:
                git_diff_output = subprocess.check_output(["git", "diff", "HEAD~1", "HEAD", "--", git_diff_dir, ":!*_pb2.py"],
                                                        text=True,
                                                        cwd=self.sdk_root_dir)
        elif self.args.work:
            git_diff_output = subprocess.check_output(["git", "diff", "HEAD~1", "HEAD", "--", git_diff_dir, ":!*_pb2.py"],
                                                  text=True,
                                                  cwd=self.sdk_root_dir)

        if git_diff_output == "":
            print("There were no changes detected that required an update to the SDK. Exiting.")
            return

        if self.args.debug:
            if self.args.work:
                print(f"Git diff output: {git_diff_output}")
            elif self.args.test:
                write_to_file(os.path.join(self.current_dir, "gitdifftest.txt"), git_diff_output)

        relevant_context = self.get_relevant_context(git_diff_output)
        if self.args.debug:
            if self.args.work:
                print(f"Relevant context files: {relevant_context.text}")
            elif self.args.test:
                write_to_file(os.path.join(self.current_dir, "relevantcontextfilestest.txt"), str(relevant_context.text))

        diff_analysis = self.get_diff_analysis(git_diff_output, relevant_context.parsed.file_paths)
        if self.args.debug:
            if self.args.work:
                print(f"Diff analysis: {diff_analysis.text}")
            elif self.args.test:
                write_to_file(os.path.join(self.current_dir, "diffanalysistest.txt"), diff_analysis.text)

        self.generate_implementations(diff_analysis)

        print(f"\nTotal estimated cost for this run: ${self.total_cost:.4f}")

def main():
    """Main entry point for the AI updater script."""
    parser = argparse.ArgumentParser(description="Viam SDK AI Updater")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode to print various helpful files")
    parser.add_argument("--noai", action="store_true", help="Disable AI (for testing)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--test", type=str, help="Enable when running tests. Supply path to root directory of desired test repo")
    group.add_argument("--work", type=str, help="Enable when running in workflow. Supply path to root direcory repo to be updated")

    args = parser.parse_args()

    # Create and run the updater
    updater = AIUpdater(args=args)
    updater.run()


if __name__ == "__main__":
    main()
