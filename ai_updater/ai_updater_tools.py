import os

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
    sdk_root_dir = os.getenv('SDK_ROOT_DIR')
    file_path = os.path.join(sdk_root_dir, file_path)

    # Define maximum number of attempts before giving up
    MAX_ATTEMPTS = 10
    max_attempts_message = f"STOP_TRYING: Maximum attempts ({MAX_ATTEMPTS}) exceeded. The AI should stop trying to apply patches to this file and respond with TASK ABORTED: PATCHING FAILED."
    max_attempts_return = {
        "success": False,
        "error": max_attempts_message,
        "stop_trying": True
    }

    if len(search_text) != len(replacement_text):
        if attempt_number > MAX_ATTEMPTS:
            print(max_attempts_message)
            return max_attempts_return
        return {
            "success": False,
            "error": f"ERROR: Mismatched list lengths - {len(search_text)} search blocks but {len(replacement_text)} replacement blocks"
        }
    if not os.path.exists(file_path):
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
            if attempt_number > MAX_ATTEMPTS:
                print(max_attempts_message)
                return max_attempts_return
            return {
                "success": False,
                "error": f"ERROR: Patch {i+1}: Search text is empty"
            }
        search_count = file_content.count(search)
        if search_count == 0:
            if attempt_number > MAX_ATTEMPTS:
                print(max_attempts_message)
                return max_attempts_return
            return {
                "success": False,
                "error": f"ERROR: Patch {i+1}: Search text not found in file. The AI needs to generate a search block that exists in the file exactly as written."
            }
        elif search_count > 1:
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
            patched_content = patched_content.replace(search, replace)
            patches_applied += 1
        else:
            # This shouldn't happen due to validation above, but handle it just in case
            if attempt_number > MAX_ATTEMPTS:
                print(max_attempts_message)
                return max_attempts_return
            return {
                "success": False,
                "error": f"ERROR: Patch {i+1}: Search text uniqueness changed during patching process (applied {patches_applied} patches successfully before failure)"
            }

    success_message = f"SUCCESS: Applied {patches_applied} patches. All search blocks were unique and patches applied successfully!"
    return {
        "success": True,
        "message": success_message,
        "attempt_number": attempt_number
    }
