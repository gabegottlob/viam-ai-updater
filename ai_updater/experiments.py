import os
import argparse
import subprocess
import asyncio
import json
import tempfile
import time

import anthropic
from google import genai
from google.genai import types
from pydantic import BaseModel
from anthropic import Anthropic

from ai_updater_utils import read_file_content, write_to_file, calculate_cost

from patches_experiment_prompts import GENERATEPATCH_P, GENERATEPATCH_S, CLAUDE_GENERATECOMPLETEFILE_P, CLAUDE_GENERATECOMPLETEFILE_S

from fuzzysearch import find_near_matches, find_near_matches_in_file

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

def apply_patch(file_path: str, search_text: list[str], replacement_text: list[str], attempt_number: int) -> dict:
    """Applies a list of patches to a file sequentially.

    Args:
        file_path: Path to the file to patch
        search_text: List of text blocks to search for
        replacement_text: List of text blocks to replace with (corresponds to search_text)
        attempt_number: The number of the attempt to apply the patch.

    Returns:
        dict: Status with success/failure and detailed messages.
    """
    # Define maximum number of attempts before giving up
    MAX_ATTEMPTS = 10
    max_attempts_message = f"STOP_TRYING: Maximum attempts ({MAX_ATTEMPTS}) exceeded. The AI should stop trying to apply patches to this file and respond with TASK ABORTED: PATCHING FAILED."
    max_attempts_return = {
        "success": False,
        "error": max_attempts_message,
        "stop_trying": True
    }

    if len(search_text) != len(replacement_text):
        print(f"ERROR: Mismatched list lengths - {len(search_text)} search blocks but {len(replacement_text)} replacement blocks")
        if attempt_number > MAX_ATTEMPTS:
            print(max_attempts_message)
            return max_attempts_return
        return {
            "success": False,
            "error": f"ERROR: Mismatched list lengths - {len(search_text)} search blocks but {len(replacement_text)} replacement blocks"
        }
    if not os.path.exists(file_path):
        print(f"ERROR: File {file_path} does not exist")
        if attempt_number > MAX_ATTEMPTS:
            print(max_attempts_message)
            return max_attempts_return
        return {
            "success": False,
            "error": f"ERROR: File {file_path} does not exist"
        }
    try:
        with open(file_path, "r") as f:
            file_content = f.read()
    except Exception as e:
        print(f"ERROR: Failed to read file {file_path}: {str(e)}")
        if attempt_number > MAX_ATTEMPTS:
            print(max_attempts_message)
            return max_attempts_return
        return {
            "success": False,
            "error": f"ERROR: Failed to read file {file_path}: {str(e)}"
        }
    # Validate all patches before applying any
    for i, (search, replace) in enumerate(zip(search_text, replacement_text)):
        if not search:
            print(f"ERROR: Patch {i+1}: Search text is empty")
            if attempt_number > MAX_ATTEMPTS:
                print(max_attempts_message)
                return max_attempts_return
            return {
                "success": False,
                "error": f"ERROR: Patch {i+1}: Search text is empty"
            }
        search_count = file_content.count(search)
        if search_count == 0:
            print(f"ERROR: Patch {i+1}: Search text not found in file. The AI needs to generate a search block that exists in the file exactly as written.")
            if attempt_number > MAX_ATTEMPTS:
                print(max_attempts_message)
                return max_attempts_return
            return {
                "success": False,
                "error": f"ERROR: Patch {i+1}: Search text not found in file. The AI needs to generate a search block that exists in the file exactly as written."
            }
        elif search_count > 1:
            print(f"ERROR: Patch {i+1}: Search text appears {search_count} times in file. The AI must include more surrounding context to make the search block unique.")
            if attempt_number > MAX_ATTEMPTS:
                print(max_attempts_message)
                return max_attempts_return
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
            if attempt_number > MAX_ATTEMPTS:
                print(max_attempts_message)
                return max_attempts_return
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
        if attempt_number > MAX_ATTEMPTS:
            print(max_attempts_message)
            return max_attempts_return
        return {
            "success": False,
            "error": f"ERROR: Failed to write patched content to {ai_file_path}: {str(e)}"
        }

    success_message = f"SUCCESS: Applied {patches_applied} patches and saved to {ai_file_path}. All search blocks were unique and patches applied successfully."
    print(success_message)
    return {
        "success": True,
        "message": success_message
    }

# Define the function declaration for apply_patch
apply_patch_declaration = {
    "name": "apply_patch",
    "description": "Applies a list of patches to a file sequentially.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to patch"
            },
            "search_text": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of text blocks to search for"
            },
            "replacement_text": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of text blocks to replace with (corresponds to search_text)"
            },
        },
        "required": ["file_path", "search_text", "replacement_text"],
    },
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
            print("this is where a new file would usually be created")
        else:
            existing_file_content += read_file_content(os.path.join(self.sdk_root_dir, file_path))
            initial_prompt_text = GENERATEPATCH_P.format(implementation_detail=implementation_detail, existing_file_content=existing_file_content)
            system_prompt = GENERATEPATCH_S

            # Initialize conversation history
            contents = [types.Content(role="user", parts=[types.Part(text=initial_prompt_text)])]
            patch_success = False
            stop_trying = False
            attempt_count = 0

            while not patch_success and not stop_trying:
                attempt_count += 1
                response = await self.client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        thinking_config=types.ThinkingConfig(thinking_budget=-1),
                        system_instruction=system_prompt,
                        seed=12345,
                        tools=[types.Tool(function_declarations=[apply_patch_declaration])],
                        tool_config = types.ToolConfig(
                            function_calling_config=types.FunctionCallingConfig(
                                mode="ANY", allowed_function_names=["apply_patch"]
                            )
                        )
                    )
                )

                # Append model's response to history
                if response.candidates and response.candidates[0].content:
                    contents.append(response.candidates[0].content)

                    if response.candidates[0].content.parts and response.candidates[0].content.parts[0].function_call:
                        function_call = response.candidates[0].content.parts[0].function_call
                        if function_call.name == "apply_patch":
                            # Manually execute the function, passing attempt_count from python logic
                            tool_result = apply_patch(file_path=function_call.args['file_path'],
                                                        search_text=function_call.args['search_text'],
                                                        replacement_text=function_call.args['replacement_text'],
                                                        attempt_number=attempt_count)
                            patch_success = tool_result['success']
                            stop_trying = tool_result.get('stop_trying', False)

                            # Append function response to history
                            function_response_part = types.Part.from_function_response(
                                name=function_call.name,
                                response={"result": tool_result},
                            )
                            contents.append(types.Content(role="user", parts=[function_response_part]))
                        else:
                            print(f"Unexpected function call: {function_call.name}. Aborting patch attempts.")
                            patch_success = False
                            stop_trying = True
                    else:
                        print("No function call was made by the AI. Aborting patch attempts.")
                        patch_success = False
                        stop_trying = True
                else:
                    print("No response candidates or content found from AI. Aborting patch attempts.")
                    patch_success = False
                    stop_trying = True


        if patch_success:
            print("patch success")
        else:
            print("patch failed")

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

    def generate_file_gemini(self):
        with open(os.path.join(self.current_dir, "getdiffanalysis.json"), "r") as f:
            parsed_response = json.load(f)
        parsed_response = RequiredChanges.model_validate_json(json.dumps(parsed_response))
        file_path = parsed_response.files_to_update[0]
        implementation_detail = parsed_response.implementation_details[0]
        existing_file_content = read_file_content(os.path.join(self.sdk_root_dir, file_path))
        prompt = CLAUDE_GENERATECOMPLETEFILE_P.format(implementation_detail=implementation_detail, existing_file_content=existing_file_content)
        system_prompt = CLAUDE_GENERATECOMPLETEFILE_S

        start_time = time.time()

        response2 = self.client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                system_instruction=system_prompt
            )
        )
        end_time = time.time()
        print(f"Time taken: {end_time - start_time} seconds")

        original_file_dir = os.path.dirname(file_path)
        original_filename = os.path.basename(file_path)
        filename_without_ext, file_ext = os.path.splitext(original_filename)
        ai_filename = f"{filename_without_ext}_ai2{file_ext}"
        ai_file_path = os.path.join(original_file_dir, ai_filename)
        # Remove markdown code block formatting if present
        cleaned_response = response2.text.strip()
        if cleaned_response.startswith("```") and cleaned_response.endswith("```"):
            # Remove the first line (```python or ```) and the last line (```)
            cleaned_response = "\n".join(cleaned_response.splitlines()[1:-1]) + "\n"
        with open(ai_file_path, "w") as f:
            f.write(cleaned_response)
        print(f"Flash Lite Response written to: {ai_file_path}")


    async def generate_file_claude(self):
        api_key = os.getenv("ANTRHOPIC_API_KEY")
        claude = anthropic.AsyncAnthropic(api_key=api_key)
        claude.models.list(limit=20)
        #'claude-sonnet-4-20250514'
        #'claude-3-5-haiku-20241022'

        with open(os.path.join(self.current_dir, "getdiffanalysis.json"), "r") as f:
            parsed_response = json.load(f)
        parsed_response = RequiredChanges.model_validate_json(json.dumps(parsed_response))
        file_path = parsed_response.files_to_update[0]
        implementation_detail = parsed_response.implementation_details[0]
        existing_file_content = read_file_content(os.path.join(self.sdk_root_dir, file_path))
        prompt = CLAUDE_GENERATECOMPLETEFILE_P.format(implementation_detail=implementation_detail, existing_file_content=existing_file_content)
        system_prompt = CLAUDE_GENERATECOMPLETEFILE_S

        # Count tokens first
        tokens = await claude.messages.count_tokens(
            model="claude-sonnet-4-20250514",
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": prompt
            }],
        )
        print(f"Token count: {tokens.input_tokens}")

        # Stream the response
        full_response = ""
        async with claude.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=50000,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": prompt
            }],
        ) as stream:
            async for text in stream.text_stream:
                full_response += text
                #print(text, end="", flush=True)  # Print as it streams

        print("\n\nStreaming completed!")

        # Write to file
        original_file_dir = os.path.dirname(file_path)
        original_filename = os.path.basename(file_path)
        filename_without_ext, file_ext = os.path.splitext(original_filename)
        ai_filename = f"{filename_without_ext}_ai{file_ext}"
        ai_file_path = os.path.join(original_file_dir, ai_filename)

        with open(ai_file_path, "w") as f:
            f.write(full_response)

        print(f"Response written to: {ai_file_path}")


def main():
    """Main entry point for the AI updater script."""
    updater = AIUpdater()
    #updater.test_fuzzy_search()
    #asyncio.run(updater.generate_file_claude())
    updater.generate_file_gemini()
    # asyncio.run(updater.apply_changes())


if __name__ == "__main__":
    main()
