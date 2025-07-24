import os
import argparse
import subprocess
import asyncio

from google import genai
from google.genai import types
from pydantic import BaseModel

from ai_updater_utils import read_file_content, write_to_file, calculate_cost
from ai_updater_tools import apply_patch

from prompts.getrelevantcontext_prompts import GETRELEVANTCONTEXT_P1, GETRELEVANTCONTEXT_P2, GETRELEVANTCONTEXT_S1, GETRELEVANTCONTEXT_S2
from prompts.diffparser_prompts import DIFFPARSER_P, DIFFPARSER_S
from prompts.applychanges_prompts import GENERATECOMPLETEFILE_P, GENERATECOMPLETEFILE_S, GENERATEPATCH_P, GENERATEPATCH_S

class ContextFiles(BaseModel):
    """Model for storing the files that should be analyzed as potential context.
    file_paths: The paths to the files that could be relevant to the changes.
    """
    file_paths: list[str]

class ContextInclusion(BaseModel):
    """Model for whether or not a file should be included as context.
    filename: The path to the file.
    inclusion: Whether or not the file should be included as context.
    reasoning: The reasoning for why the file should be included as context.
    """
    filename: str
    inclusion: bool
    reasoning: str

class RequiredChanges(BaseModel):
    """Model for storing analysis of code needed based on diff.
    files_to_update: The paths to the files that need to be updated.
    implementation_details: The details of the changes to be made to the files.
    requires_creation: Whether each file needs to be created from scratch (True) or already exists and needs updating (False).
    """
    files_to_update: list[str]
    implementation_details: list[str]
    requires_creation: list[bool]

class GeneratedFile(BaseModel):
    """Model for storing AI-generated file content.
    file_content: The entire content of the file.
    """
    file_content: str

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

        os.environ['SDK_ROOT_DIR'] = self.sdk_root_dir
        os.environ['CURRENT_DIR'] = self.current_dir

        # Initialize the Gemini client
        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set and no API key provided")
        self.client = genai.Client(api_key=api_key)
        self.total_cost = 0.0

    async def get_relevant_context(self, git_diff_output: str) -> list[ContextInclusion]:
        """Two stage approach to use AI to gather the most relevant context files.
        Stage 1: Gather all files that could be relevant to the changes.
        Stage 2: Asynchronous AI calls are made to analyze each file to determine if it is actually relevant as context.

        Args:
            git_diff_output (str): Git diff output containing proto/code changes

        Returns:
            list[ContextInclusion]: List of ContextInclusion objects containing relevant files
        """
        sdk_tree_output = subprocess.check_output(["tree", os.path.join("src", "viam")], text=True, cwd=self.sdk_root_dir)
        tests_tree_output = subprocess.check_output(["tree", "tests"], text=True, cwd=self.sdk_root_dir)

        prompt = GETRELEVANTCONTEXT_P1.format(
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
                system_instruction=GETRELEVANTCONTEXT_S1,
                seed=12345
            )
        )
        print(f"Finished get_relevant_context stage 1. Gemini model used: {response.model_version}")
        self.total_cost += calculate_cost(response.usage_metadata, response.model_version)
        if self.args.debug:
            if self.args.work:
                print(f"get_relevant_context stage 1 response: {response.text}")
            elif self.args.test:
                write_to_file(os.path.join(self.current_dir, "getrelevantcontext_stage1.txt"), str(response.text), quiet=True)

        file_analysis = []
        for file_path in response.parsed.file_paths:
            file_content = f"File path: {file_path}\n" + read_file_content(os.path.join(self.sdk_root_dir, file_path))
            prompt = GETRELEVANTCONTEXT_P2.format(
                git_diff_output=git_diff_output,
                file_content=file_content
            )
            file_analysis.append(self.client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    thinking_config=types.ThinkingConfig(thinking_budget=-1),
                    system_instruction=GETRELEVANTCONTEXT_S2,
                    response_schema=ContextInclusion,
                    response_mime_type="application/json",
                    seed=12345
                )
            ))
        file_analysis = await asyncio.gather(*file_analysis)
        analysis_str = ""
        for response in file_analysis:
            analysis_str += response.text
            self.total_cost += calculate_cost(response.usage_metadata, response.model_version)
        if self.args.debug:
            if self.args.work:
                print(f"get_relevant_context stage 2 response: {analysis_str}")
            elif self.args.test:
                write_to_file(os.path.join(self.current_dir, "getrelevantcontext_stage2.txt"), analysis_str, quiet=True)
        print(f"Finished get_relevant_context stage 2. Gemini model used: {file_analysis[0].model_version}")
        return [response.parsed for response in file_analysis]

    def get_diff_analysis(self, git_diff_output: str, relevant_files: list[ContextInclusion]) -> types.GenerateContentResponse:
        """Analyze git diff using AI to identify required code changes. Outputs a list of files that need to be updated
        or created, and detailed instructions for the changes to be made to the files.

        Args:
            git_diff_output: Git diff output as string
            relevant_files: List of relevant file paths for context

        Returns:
            GenerateContentResponse: LLM response containing analysis of needed changes
        """
        # Gather relevant context files from the project and format them for the prompt
        relevant_context = ""
        for file in relevant_files:
            if file.inclusion:
                file_path = os.path.join(self.sdk_root_dir, file.filename)
                file_content = read_file_content(file_path)
                relevant_context += f"File: {file.filename}\nContent: \n{file_content}\n--------------------------------\n"

        prompt = DIFFPARSER_P.format(git_diff_output=git_diff_output, selected_context_files=relevant_context)
        response =self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=RequiredChanges,
                thinking_config=types.ThinkingConfig(thinking_budget=-1),
                system_instruction=DIFFPARSER_S,
                seed=12345
            )
        )

        self.total_cost += calculate_cost(response.usage_metadata, response.model_version)
        if self.args.debug:
            if self.args.work:
                print(f"get_diff_analysis response: {response.text}")
            elif self.args.test:
                write_to_file(os.path.join(self.current_dir, "getdiffanalysis.txt"), response.text, quiet=True)
        print(f"Finished get_diff_analysis. Gemini model used: {response.model_version}")
        return response

    async def generate_patch(self, file_path: str, implementation_detail: str):
        """Attemps to apply the AI suggested changes to a single file. If the patch generation fails,
        the file will be completely regenerated as a fallback (via generate_file).

        Args:
            file_path: The path to the file that needs to be updated.
            implementation_detail: The details of the changes to be made to the file.
        """
        existing_file_content = read_file_content(os.path.join(self.sdk_root_dir, file_path))
        prompt = GENERATEPATCH_P.format(implementation_detail=implementation_detail, existing_file_content=f"=== {file_path} ===\n{existing_file_content}")
        response = await self.client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                thinking_config=types.ThinkingConfig(thinking_budget=-1),
                system_instruction=GENERATEPATCH_S,
                seed=12345,
                tools=[apply_patch]
            )
        )

        self.total_cost += calculate_cost(response.usage_metadata, response.model_version)
        if len(response.automatic_function_calling_history) == 1:
            patch_success = False
        else:
            patch_success = response.automatic_function_calling_history[-1].parts[0].function_response.response['result']['success']

        original_file_dir = os.path.dirname(os.path.join(self.sdk_root_dir, file_path))
        original_filename = os.path.basename(file_path)
        if self.args.test:
            dir_structure = os.path.relpath(original_file_dir, self.sdk_root_dir)
            ai_generated_dir = os.path.join(os.path.dirname(self.sdk_root_dir), "ai_generated", dir_structure)
            os.makedirs(ai_generated_dir, exist_ok=True)
            ai_file_path = os.path.join(ai_generated_dir, original_filename)
        elif self.args.work:
            ai_file_path = os.path.join(original_file_dir, original_filename)

        if patch_success:
            search_text = response.automatic_function_calling_history[-2].parts[0].function_call.args['search_text']
            replacement_text = response.automatic_function_calling_history[-2].parts[0].function_call.args['replacement_text']
            attempt_number = response.automatic_function_calling_history[-2].parts[0].function_call.args['attempt_number']
            patched_content = existing_file_content
            for search, replace in zip(search_text, replacement_text):
                patched_content = patched_content.replace(search, replace)
            write_to_file(ai_file_path, patched_content, quiet=True)
            print(f"Successfully patched {file_path} in {attempt_number} attempts.\n")
        else:
            print(f"Failed to patch {file_path}. Falling back to complete file generation.\n")
            await self.generate_file(file_path=file_path, implementation_detail=implementation_detail, fallback=True)

    async def generate_file(self, file_path: str, implementation_detail: str, fallback: bool = False):
        existing_file_content = f"=== {file_path} ===\n"
        if fallback:
            existing_file_content = f"=== {file_path} ===\n" + existing_file_content
        prompt = GENERATECOMPLETEFILE_P.format(implementation_detail=implementation_detail, existing_file_content=existing_file_content)
        response = await self.client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=GeneratedFile,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                system_instruction=GENERATECOMPLETEFILE_S,
                seed=12345
            )
        )
        self.total_cost += calculate_cost(response.usage_metadata, response.model_version)
        original_file_dir = os.path.dirname(os.path.join(self.sdk_root_dir, file_path))
        original_filename = os.path.basename(file_path)
        if self.args.test:
            dir_structure = os.path.relpath(original_file_dir, self.sdk_root_dir)
            ai_generated_dir = os.path.join(os.path.dirname(self.sdk_root_dir), "ai_generated", dir_structure)
            os.makedirs(ai_generated_dir, exist_ok=True)
            ai_file_path = os.path.join(ai_generated_dir, original_filename)
        elif self.args.work:
            ai_file_path = os.path.join(original_file_dir, original_filename)
        write_to_file(ai_file_path, response.parsed.file_content, quiet=True)
        print(f"Successfully generated {file_path}\n")

    async def apply_changes(self, diff_analysis: types.GenerateContentResponse):
        """Apply all code changes suggested by the AI by choosing the appropriate update strategy for each file.

        This is the main orchestrator method that determines the best approach for each file:
        - For new files: uses create_complete_files()
        - For existing files needing targeted updates: uses create_patches() first
        - Falls back to create_complete_files() if patching fails

        The method analyzes the diff_analysis response to determine which files need updates
        and selects the most appropriate generation strategy for each file.

        Args:
            diff_analysis: LLM response from diff analysis containing file update requirements
        """
        # Parse the response from diff analysis (according to defined Pydantic model)
        parsed_response: RequiredChanges = diff_analysis.parsed

        if(len(parsed_response.files_to_update) != len(parsed_response.implementation_details)):
            raise ValueError("ERROR: AI OUTPUT A DIFFERENT NUMBER OF FILENAMES THAN IMPLEMENTATION DETAILS")
        if(len(parsed_response.files_to_update) == 0):
            print("THE AI WORKFLOW DID NOT DETERMINE THAT ANY FILES NEED TO BE UPDATED BASED ON THE GIVEN PROTO UPDATE DIFF")
            return

        required_changes = []
        for i in range(len(parsed_response.files_to_update)):
            file_path = parsed_response.files_to_update[i]
            implementation_detail = parsed_response.implementation_details[i]
            requires_creation = parsed_response.requires_creation[i]
            if requires_creation:
                required_changes.append(self.generate_file(file_path=file_path, implementation_detail=implementation_detail))
            else:
                required_changes.append(self.generate_patch(file_path=file_path, implementation_detail=implementation_detail))
        await asyncio.gather(*required_changes)
        print(f"Finished applying changes. Gemini model used: gemini-2.5-flash")

    async def run(self):
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
            print("There were no proto changes detected that required an update to the SDK. Exiting.")
            return

        if self.args.debug:
            if self.args.work:
                print(f"Git diff output: {git_diff_output}")
            elif self.args.test:
                write_to_file(os.path.join(self.current_dir, "gitdifftest.txt"), git_diff_output, quiet=True)

        relevant_context = await self.get_relevant_context(git_diff_output)

        diff_analysis = self.get_diff_analysis(git_diff_output, relevant_context)

        if not self.args.noai:
            await self.apply_changes(diff_analysis)

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
    asyncio.run(updater.run())


if __name__ == "__main__":
    main()
