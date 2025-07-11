import os
import asyncio
from google import genai
from google.genai import types
from pydantic import BaseModel
import json

from gather_tools_prompt import GATHER_TOOLS_PROMPT_1, GATHER_TOOLS_PROMPT_2
from ai_updater_utils import read_file_content, write_to_file

SYSTEM_PROMPT ='''You are the first stage in an AI pipeline for updating SDK code.
Your role is to act as an intelligent context selector. Follow all instructions meticulously.
'''
SYSTEM_PROMPT_2 = '''You are a precise code context evaluator specializing in SDK development.
Your role is to make focused inclusion/exclusion decisions about individual files for implementation context.
Be analytical and decisive - only include files that provide clear value for implementing proto changes.
Avoid over-inclusion that could overwhelm downstream processes with irrelevant context.
'''
class ContextFiles(BaseModel):
    """Model for storing the files that should be included as context."""
    file_paths: list[str]
    explanation: list[str]

class ContextInclusion(BaseModel):
    """Model for whether or not a file should be included as context."""
    filename: str
    inclusion: bool
    reasoning: str

class AIUpdater:
    """Class for updating SDK code based on proto changes using AI."""

    def __init__(self, api_key=""):
        """Initialize the AIUpdater.

        Args:
            args: Command line arguments
            api_key (str): Google API key. If None, will use GOOGLE_API_KEY env var
        """
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.sdk_root_dir = os.path.dirname(self.current_dir)

        # Initialize the Gemini client
        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set and no API key provided")
        self.client = genai.Client(api_key=api_key)

    async def get_relevant_context(self) -> types.GenerateContentResponse:
        """Get relevant context files for analysis.

        Args:
            git_diff_output (str): Git diff output

        Returns:
            GenerateContentResponse: LLM response containing relevant files
        """
        git_diff_output = read_file_content(os.path.join(self.current_dir, "proto_diff.txt"))
        sdk_tree_output = read_file_content(os.path.join(self.current_dir, "sdktree.txt"))
        tests_tree_output = read_file_content(os.path.join(self.current_dir, "teststree.txt"))

        prompt = GATHER_TOOLS_PROMPT_1.format(
            sdk_tree_structure=sdk_tree_output,
            tests_tree_structure=tests_tree_output,
            git_diff_output=git_diff_output
        )

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                thinking_config=types.ThinkingConfig(thinking_budget=-1),
                system_instruction=SYSTEM_PROMPT,
                response_schema=ContextFiles,
                response_mime_type="application/json"
            )
        )
        print(f"Model version: {response.model_version}")
        print(f"Token data from from getrelevantdirs_prompt: {response.usage_metadata.total_token_count}\n")
        print(response.usage_metadata)
        write_to_file(os.path.join(self.current_dir, "gather_tools_response.txt"), response.text)

        print("Number of files to analyze: ", len(response.parsed.file_paths))

        file_analysis = []
        for file_path in response.parsed.file_paths:
            file_content = "File path: " + file_path + "\n" + read_file_content(os.path.join(self.sdk_root_dir, file_path))
            prompt = GATHER_TOOLS_PROMPT_2.format(
                git_diff_output=git_diff_output,
                file_content=file_content
            )
            file_analysis.append(self.client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    thinking_config=types.ThinkingConfig(thinking_budget=-1),
                    system_instruction=SYSTEM_PROMPT_2,
                    response_schema=ContextInclusion,
                    response_mime_type="application/json"
                )
            ))
        file_analysis = await asyncio.gather(*file_analysis)

        file_analysis = [response.text for response in file_analysis]
        analysis_str = ""
        for analysis in file_analysis:
            analysis_str += analysis
        print("Number of files analyzed: ", len(file_analysis))
        write_to_file(os.path.join(self.current_dir, "gather_tools_response_2.txt"), analysis_str)



def main():
    """Main entry point for the AI updater script."""
    # Create and run the updater
    updater = AIUpdater()
    asyncio.run(updater.get_relevant_context())


if __name__ == "__main__":
    main()
