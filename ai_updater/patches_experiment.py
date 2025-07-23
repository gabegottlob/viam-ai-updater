import os
import argparse
import subprocess
import asyncio
import json
import tempfile
import time

from google import genai
from google.genai import types
from pydantic import BaseModel

from ai_updater_utils import read_file_content, write_to_file, calculate_cost

from patches_experiment_prompts import GENERATEPATCH_P, GENERATEPATCH_S

from fuzzysearch import find_near_matches, find_near_matches_in_file
from diff_match_patch import diff_match_patch

class GeneratedFile(BaseModel):
    """Model for storing AI-generated file content.
    file_content: The entire content of the file.
    """
    file_content: str

class GeneratedPatch(BaseModel):
    """Model for storing AI-generated patch content.
    replace_text: List of text to search for.
    with_text: List of text to replace with.
    """
    search_text: list[str]
    replacement_text: list[str]

class RequiredChanges(BaseModel):
    """Model for storing analysis of code needed based on diff.
    files_to_update: The paths to the files that need to be updated.
    implementation_details: The details of the changes to be made to the files.
    requires_creation: Whether each file needs to be created from scratch (True) or already exists and needs updating (False).
    """
    files_to_update: list[str]
    implementation_details: list[str]
    requires_creation: list[bool]

def apply_patch(file_path: str, search_text: list[str], replacement_text: list[str]) -> dict:
    """Applies a list of patches to a file sequentially.

    Args:
        file_path: Path to the file to patch
        search_text: List of text blocks to search for
        replacement_text: List of text blocks to replace with (corresponds to search_text)

    Returns:
        dict: Status with success/failure and detailed messages
    """
    if len(search_text) != len(replacement_text):
        print(f"ERROR: Mismatched list lengths - {len(search_text)} search blocks but {len(replacement_text)} replacement blocks")
        return {
            "success": False,
            "error": f"ERROR: Mismatched list lengths - {len(search_text)} search blocks but {len(replacement_text)} replacement blocks"
        }

    if not os.path.exists(file_path):
        print(f"ERROR: File {file_path} does not exist")
        return {
            "success": False,
            "error": f"ERROR: File {file_path} does not exist"
        }

    try:
        with open(file_path, "r") as f:
            file_content = f.read()
    except Exception as e:
        print(f"ERROR: Failed to read file {file_path}: {str(e)}")
        return {
            "success": False,
            "error": f"ERROR: Failed to read file {file_path}: {str(e)}"
        }

    # Validate all patches before applying any
    for i, (search, replace) in enumerate(zip(search_text, replacement_text)):
        if not search:
            print(f"ERROR: Patch {i+1}: Search text is empty")
            return {
                "success": False,
                "error": f"ERROR: Patch {i+1}: Search text is empty"
            }

        search_count = file_content.count(search)
        if search_count == 0:
            print(f"ERROR: Patch {i+1}: Search text not found in file. The AI needs to generate a search block that exists in the file exactly as written.")
            return {
                "success": False,
                "error": f"ERROR: Patch {i+1}: Search text not found in file. The AI needs to generate a search block that exists in the file exactly as written."
            }
        elif search_count > 1:
            print(f"ERROR: Patch {i+1}: Search text appears {search_count} times in file. The AI must include more surrounding context to make the search block unique.")
            return {
                "success": False,
                "error": f"ERROR: Patch {i+1}: Search text appears {search_count} times in file. The AI must include more surrounding context to make the search block unique."
            }

    # Apply patches sequentially
    patched_content = file_content
    patches_applied = 0

    for i, (search, replace) in enumerate(zip(search_text, replacement_text)):
        if patched_content.count(search) == 1:
            patched_content = patched_content.replace(search, replace, 1)  # Replace only first occurrence
            patches_applied += 1
        else:
            # This shouldn't happen due to validation above, but handle it just in case
            print(f"ERROR: Patch {i+1}: Search text uniqueness changed during patching process (applied {patches_applied} patches successfully before failure)")
            return {
                "success": False,
                "error": f"ERROR: Patch {i+1}: Search text uniqueness changed during patching process (applied {patches_applied} patches successfully before failure)"
            }

    # Write the patched content to a new _ai file
    try:
        original_file_dir = os.path.dirname(file_path)
        original_filename = os.path.basename(file_path)
        filename_without_ext, file_ext = os.path.splitext(original_filename)
        ai_filename = f"{filename_without_ext}_ai{file_ext}"
        ai_file_path = os.path.join(original_file_dir, ai_filename)
        with open(ai_file_path, "w") as f:
            f.write(patched_content)
    except Exception as e:
        print(f"ERROR: Failed to write patched content to {ai_file_path}: {str(e)}")
        return {
            "success": False,
            "error": f"ERROR: Failed to write patched content to {ai_file_path}: {str(e)}"
        }

    success_message = f"SUCCESS: Applied {patches_applied} patches and saved to {ai_file_path}. All search blocks were unique and patches applied successfully. Your job is now finished and you can stop. Do not output anything else or make any other tool calls."
    print(success_message)
    return {
        "success": True,
        "message": success_message
    }

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

    def test_fuzzy_search(self):
        with open(os.path.join(self.current_dir, "applypatch.json"), "r") as f:
            parsed_response = json.load(f)
        replace_text = parsed_response["replace_text"][0]
        with_text = parsed_response["with_text"][0]
        file_content = read_file_content(os.path.join(self.current_dir, "data_client.py"))
        dmp = diff_match_patch()
        start_time_dmp = time.time()
        matched_index = dmp.match_main(file_content, replace_text, 60000)
        end_time_dmp = time.time()
        print("Match found after ", end_time_dmp - start_time_dmp, " seconds")

        start_time = time.time()
        matches = find_near_matches(replace_text, file_content, max_l_dist=80)
        end_time = time.time()
        print("Match found after ", end_time - start_time, " seconds")
        #start = 61418
        #end = 80121
        #i think you can access using matches[0].start, matches[0].matched, etc.

    async def apply_change(self, file_path: str, implementation_detail: str, requires_creation: bool, fallback: bool = False):
        """Applies the AI suggested changes to a single file. If the file needs to be created from scratch,
        the file will be completely regenerated. If the file already exists, the file will be patched
        (if the patch generation fails, the file will be completely regenerated as a fallback).

        Args:
            file_path: The path to the file that needs to be updated.
            implementation_detail: The details of the changes to be made to the file.
            requires_creation: Whether or not the file needs to be created from scratch.
            fallback: Whether this is a fallback call from failed patching.
        """
        existing_file_content = f"=== {file_path} ===\n"
        if requires_creation:
            if fallback:
                existing_file_content += read_file_content(os.path.join(self.sdk_root_dir, file_path))
            else:
                existing_file_content += f"This file does not exist in the repository. It will need to be created from scratch.\n"
            prompt = GENERATECOMPLETEFILE_P.format(implementation_detail=implementation_detail, existing_file_content=existing_file_content)
            system_prompt = GENERATECOMPLETEFILE_S
            response_schema = GeneratedFile
        else:
            existing_file_content += read_file_content(os.path.join(self.sdk_root_dir, file_path))
            prompt = GENERATEPATCH_P.format(implementation_detail=implementation_detail, existing_file_content=existing_file_content)
            system_prompt = GENERATEPATCH_S
            response_schema = GeneratedPatch
        response = await self.client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                thinking_config=types.ThinkingConfig(thinking_budget=-1),
                system_instruction=system_prompt,
                seed=12345,
                tools=[apply_patch],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode="ANY", allowed_function_names=["apply_patch"]
                    )
                )
            )
        )
        original_abs_path = os.path.join(self.sdk_root_dir, file_path)
        original_file_dir = os.path.dirname(original_abs_path)
        original_filename = os.path.basename(file_path)
        filename_without_ext, file_ext = os.path.splitext(original_filename)
        ai_filename = f"{filename_without_ext}_ai{file_ext}"
        ai_file_path = os.path.join(original_file_dir, ai_filename)

        if requires_creation:
            write_to_file(ai_file_path, response.parsed.file_content)
        else:
            try:
                write_to_file(os.path.join(self.current_dir, "patch_list.json"), response.text)
                patched_content = read_file_content(os.path.join(self.sdk_root_dir, file_path))
                for r, w in zip(response.parsed.search_text, response.parsed.replacement_text, strict=True):
                    if patched_content.count(r) == 0:
                        print(f"ERROR: The search text does not exist in the file. Attempting fuzzy search.")
                        start_time = time.time()
                        r = find_near_matches(r, patched_content, max_l_dist=80)[0].matched
                        end_time = time.time()
                        print(f"Fuzzy search took {end_time - start_time} seconds")
                    elif patched_content.count(r) > 1:
                        raise ValueError(f"ERROR: The search text appears multiple times in the file.")
                    if r == "":
                        raise ValueError(f"ERROR: The search text is empty.")
                    patched_content = patched_content.replace(r, w)
                write_to_file(ai_file_path, patched_content, quiet=True)
                print(f"Patched {ai_file_path}\n")
            except Exception as e:
                print(f"Error applying patch to {file_path}: {e}\nWould have fallen back to complete file generation.\n")
                #await self.apply_change(file_path=file_path, implementation_detail=implementation_detail, requires_creation=True, fallback=True)

    async def apply_changes(self):
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
        with open(os.path.join(self.current_dir, "getdiffanalysis.json"), "r") as f:
            parsed_response = json.load(f)
        parsed_response = RequiredChanges.model_validate_json(json.dumps(parsed_response))

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
            required_changes.append(self.apply_change(file_path=file_path, implementation_detail=implementation_detail, requires_creation=requires_creation))
        await asyncio.gather(*required_changes)
        print(f"Finished applying changes. Gemini model used: gemini-2.5-flash")

def main():
    """Main entry point for the AI updater script."""
    updater = AIUpdater()
    #updater.test_fuzzy_search()
    asyncio.run(updater.apply_changes())


if __name__ == "__main__":
    main()
