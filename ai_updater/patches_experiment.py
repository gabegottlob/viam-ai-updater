import os
import argparse
import subprocess
import asyncio
import json
import tempfile

from google import genai
from google.genai import types
from pydantic import BaseModel

from ai_updater_utils import read_file_content, write_to_file, calculate_cost

from patches_prompts import GENERATEPATCHES_P, GENERATEPATCHES_S

class GeneratedPatch(BaseModel):
    """Model for storing AI-generated patch content."""
    file_path: str
    replace_text: list[str]
    with_text: list[str]


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


    def apply_patch(self, patch: str, ai_file_path: str):
        """Apply a patch to the repository.
        Args:
            patch: The patch to apply
            ai_file_path: The absolute path to the AI-generated file
        """
        with tempfile.NamedTemporaryFile(mode='r+', suffix='.patch', encoding='utf-8') as temp_patch_file:
            temp_patch_file.write(patch)
            temp_patch_path = temp_patch_file.name
            # For debugging, print content of the temporary patch file
            # print(f"Content in test patch file: {temp_patch_file.read()}")
            subprocess.check_output(["patch", "-i", temp_patch_path, "-o", ai_file_path], cwd=self.sdk_root_dir)
            print(f"Applied patch to {ai_file_path}")

    def find_replace_text(self, replace_text: list[str], with_text: list[str], old_file_path: str, new_file_path: str):
        """Finds and replaces text in a file. Writes the new file to the specified file path.
        Args:
            replace_text: The text to replace
            with_text: The text to replace with
            old_file_path: The path to the old file
            new_file_path: The path to the new file
        """
        file_content = read_file_content(old_file_path)
        for r, w in zip(replace_text, with_text):
            file_content = file_content.replace(r, w)
        write_to_file(new_file_path, file_content, quiet=True)
        print(f"Patched {new_file_path}\n")

    async def generate_patches(self):
        """Generate implementation code based on diff analysis.

        Args:
            diff_analysis: LLM response from diff analysis
        """
        with open(os.path.join(self.current_dir, "getdiffanalysis.json"), "r") as f:
            parsed_response = json.load(f)
        generated_patches = []
        for i in range(len(parsed_response["files_to_update"])):
            file_path = parsed_response["files_to_update"][i]
            implementation_detail = parsed_response["implementation_details"][i]
            existing_file_content = ""
            try:
                with open(os.path.join(self.sdk_root_dir, file_path), 'r') as f:
                    file_content = f.read()
                    existing_file_content += f"\n=== {file_path} ===\n{file_content}\n"
            except FileNotFoundError:
                print(f"Warning: File {file_path} not found")
                existing_file_content += f"\n=== {file_path} ===\nThis file does not exist in the repository. It will need to be created from scratch.\n"
            prompt = GENERATEPATCHES_P.format(implementation_detail=implementation_detail, existing_file_content=existing_file_content)
            generated_patches.append(self.client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema=GeneratedPatch,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    system_instruction=GENERATEPATCHES_S
                )
            ))
        generated_patches = await asyncio.gather(*generated_patches)
        #Calculate cost and write updated files to the repository
        write_to_file("patch1.txt", str(generated_patches[0].text))
        for response in generated_patches:
            #self.total_cost += calculate_cost(response.usage_metadata, response.model_version)
            file_path = response.parsed.file_path
            original_abs_path = os.path.join(self.sdk_root_dir, file_path)
            original_file_dir = os.path.dirname(original_abs_path)
            original_filename = os.path.basename(file_path)
            filename_without_ext, file_ext = os.path.splitext(original_filename)
            ai_filename = f"{filename_without_ext}_ai{file_ext}"
            ai_file_path = os.path.join(original_file_dir, ai_filename)

            self.find_replace_text(response.parsed.replace_text, response.parsed.with_text, original_abs_path, ai_file_path)
        print(f"Finished generate_implementations. Gemini model used: {generated_patches[0].model_version}")

def main():
    """Main entry point for the AI updater script."""

    updater = AIUpdater()
    # with open(os.path.join(updater.sdk_root_dir, "sample_patch.patch"), "r") as f:
    #     patch = f.read()
    # updater.apply_patch(patch, os.path.join(updater.sdk_root_dir, "patched_file.txt"))
    asyncio.run(updater.generate_patches())


if __name__ == "__main__":
    main()
