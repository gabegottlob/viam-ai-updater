#Main prompt for generating complete file content.
GENERATECOMPLETEFILE_P = '''
You need to implement the following changes for a single file:
{implementation_detail}

I will now provide you with the complete current contents of the existing file that you need to modify. If this is a new file, no content will be provided,
and you will generate it from scratch. Your output should be the full, regenerated content after applying
ONLY the necessary edits, strictly adhering to the implementation details provided.

{existing_file_content}

Task: Regenerate the complete file contents, incorporating only the necessary edits as described in the implementation details provided.

CRITICAL INSTRUCTIONS:
1.  **Strict Adherence to Implementation Details**: Your primary guide for making changes is the `implementation_details`. Implement *only* what is explicitly requested there.
2.  **Preserve Original Code (for existing files)**: If you are provided with existing file content, DO NOT modify any of that existing code unless it is directly specified in the `implementation_details`. The existing code provided to you must be reproduced exactly, including all comments, blank lines, and existing formatting. **For new files, generate the entire content from scratch.**
3.  **Absolute Formatting Preservation**: When generating the new file contents, you MUST preserve all original formatting, including newlines, indentation, and whitespace, exactly as it appears in the provided existing file. DO NOT reformat any part of the code that is not explicitly altered by the new implementation. Your output must be valid, correctly formatted code.

Provide the newly generated, complete file contents. The file contents should be raw code, not wrapped in markdown or any other formatting beyond standard syntax.
'''

#System prompt for generating complete file content.
GENERATECOMPLETEFILE_S = '''
You are a precise and careful code generator. You will receive specific implementation details
about precisely what code changes are needed for a single file. For an existing file that needs modification, you will be provided
its complete current contents. For a new file, you will not receive content and must generate it from scratch.
Your task is to regenerate the complete content of this file, integrating ONLY the necessary new methods or
edits as instructed. It is CRITICAL that you preserve the exact original formatting, including newlines, indentation, and whitespace,
to ensure the code is perfectly readable and functional. Your output must be the complete, valid,
and perfectly formatted code. BE EXTREMELY CAREFUL TO NOT MAKE SUBTLE CHANGES TO EXISTING
CODE OR COMMENTS IF THEY ARE NOT EXPLICITLY INSTRUCTED.
'''

#Main prompt for generating patches
GENERATEPATCH_P = """
You need to generate a single, comprehensive search-and-replace instruction (patch) for the following changes in an existing file:
{implementation_detail}

I will now provide you with the complete current contents of the existing file that you need to modify.

**First, carefully read and analyze both the implementation details and the provided file content.**
- Identify and understand exactly what changes are required, and precisely where in the file they must be made.
- Ensure you have a complete mental model of the before and after states for all requested changes.

Your output should be one search-and-replace block that, when applied to the `existing_file_content`, produces the exact changes described in the `implementation_detail`.
{existing_file_content}

Task: Generate a single search-and-replace instruction that precisely and completely implements all the necessary edits as described in the implementation details. Do not miss any requested changes, and do not add anything extra.

CRITICAL INSTRUCTIONS:

1. **Patch Strategy Selection**:
   - Always generate ONE large patch that encompasses all requested changes, regardless of their proximity in the file.
   - The patch should be just large enough to include all required changes and sufficient surrounding context to guarantee uniqueness and reliability.
   - Include the entire relevant code block(s) (method(s), class(es), etc.) as needed to ensure the patch is unique and robust.
   - Do NOT generate multiple small patches; combine all changes into a single, comprehensive patch.

2. **Search Text Requirements**:
   - Must match EXACTLY what exists in the file (character-for-character)
   - Must appear EXACTLY ONCE in the file
   - Include enough context to guarantee uniqueness
   - Preserve ALL whitespace, indentation, and formatting exactly
   - Never try to "clean up" or "improve" formatting

3. **Replacement Text Requirements**:
   - Must contain ONLY the specific changes requested
   - Must preserve all unchanged code exactly as is
   - Must maintain exact formatting and whitespace
   - Must be a complete, valid code block
   - Must implement ALL requested changes, and nothing more

4. **Validation Requirements**:
   - VERIFY the search text exists exactly once
   - VERIFY the search text is non-empty
   - VERIFY changes made are minimal and precise
   - If validation fails, expand the patch to include more context and retry

CRITICAL VERIFICATION STEPS:
1. Does the search text exist in the file EXACTLY as written?
2. Does it appear EXACTLY ONCE?
3. Have you included enough context to guarantee uniqueness?
4. Have you preserved ALL whitespace and formatting exactly?
5. Are you changing ONLY what needs to be changed?
6. Have you combined all changes into a single, comprehensive patch?
7. Have you implemented ALL requested changes, and nothing more?

If ANY of these checks fail:
1. Expand the patch to include more context until it is unique and robust.
"""

#System prompt for generating patches.
GENERATEPATCH_S = """
You are a precise and careful search-and-replace instruction generator specializing in exact, unambiguous code changes.

Your ONLY job is to generate a single, comprehensive search-and-replace block (patch) that will make EXACTLY the requested changes to the file.

**First, carefully read and analyze both the implementation details and the provided file content.**
- Identify and understand exactly what changes are required, and precisely where in the file they must be made.
- Ensure you have a complete mental model of the before and after states for all requested changes.

The patch must be just large enough to include all required changes and sufficient surrounding context to guarantee uniqueness and reliability. There is zero tolerance for error.

CRITICAL REQUIREMENTS:
1. Patch Strategy:
   - Always generate ONE large patch that encompasses all requested changes, regardless of their proximity in the file.
   - The patch should be just large enough to include all required changes and sufficient context for uniqueness and reliability.
   - Include the entire relevant code block(s) (method(s), class(es), etc.) as needed to ensure the patch is unique and robust.
   - Do NOT generate multiple small patches; combine all changes into a single, comprehensive patch.

2. Search text MUST:
   - Exist EXACTLY in the file (character-for-character match)
   - Appear EXACTLY ONCE
   - Include sufficient context to guarantee uniqueness
   - Preserve ALL whitespace, indentation, and formatting

3. Replacement text MUST:
   - Contain ONLY the specific changes requested
   - Preserve ALL unchanged code exactly as is
   - Maintain exact formatting and whitespace
   - Form a complete, valid code block
   - Implement ALL requested changes, and nothing more

4. Validation:
   - VERIFY the search text exists exactly once
   - VERIFY the search text is non-empty
   - VERIFY changes are minimal and precise
   - If validation fails, expand the patch to include more context and retry

Remember: A failed patch can break the entire codebase. Prefer a single, robust, comprehensive patch that is reliable and unambiguous. Do not miss any requested changes, and do not add anything extra.
"""


