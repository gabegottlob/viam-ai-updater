import os
from google import genai
from google.genai import types
from pydantic import BaseModel
import subprocess

from gather_tools_prompt import GATHER_TOOLS_PROMPT, GATHER_TOOLS_PROMPT_2

SYSTEM_PROMPT ='''You are an expert AI agent tasked with intelligently selecting context from throughout an SDK codebase. Follow the instructions in the prompt
meticulously and ensure your output matches what is requested in the prompt.
'''


class ContextFiles(BaseModel):
    """Model for storing the files that should be included as context."""
    file_paths: list[str]
    explanation: list[str]

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

def read_file_tool(file_path: str) -> dict:
        """Read and return the content of a file.

        Args:
            file_path: Path to the file to read

        Returns:
            str: Content of the file or error message if reading fails
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sdk_root_dir = os.path.dirname(current_dir)
        file_path = os.path.join(sdk_root_dir, file_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                print(f"Reading file: {file_path}")
                return {"file_path": file_path, "file_content": f.read()}
        except Exception as e:
            return {"file_path": file_path, "file_content": f"Error reading file: {str(e)}"}


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


    def get_relevant_context(self) -> types.GenerateContentResponse:
        """Get relevant context files for analysis.

        Args:
            git_diff_output (str): Git diff output

        Returns:
            GenerateContentResponse: LLM response containing relevant files
        """
        #git_diff_dir = os.path.join(self.sdk_root_dir, "src", "viam", "gen")
        git_diff_output = read_file_content(os.path.join(self.current_dir, "proto_diff.txt"))
        sdk_tree_output = read_file_content(os.path.join(self.current_dir, "sdktree.txt"))
        tests_tree_output = read_file_content(os.path.join(self.current_dir, "teststree.txt"))

        prompt = GATHER_TOOLS_PROMPT_2.format(
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
                tools=[read_file_tool]
            )
        )
        print(f"Model version: {response.model_version}")
        print(f"Token data from from getrelevantdirs_prompt: {response.usage_metadata.total_token_count}\n")
        write_to_file(os.path.join(self.current_dir, "gather_tools_response.txt"), response.text)


def main():
    """Main entry point for the AI updater script."""
    # Create and run the updater
    updater = AIUpdater()
    updater.get_relevant_context()


if __name__ == "__main__":
    main()
