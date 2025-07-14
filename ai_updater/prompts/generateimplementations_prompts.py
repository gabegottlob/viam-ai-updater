#Main prompt for generating function implementations.
GENERATEIMPLEMENTATIONS_P = '''
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

Provide the file path (so it can be reinserted into the existing codebase), and the newly generated, complete file contents. The file contents should be raw code, not wrapped in markdown or any other formatting beyond standard syntax.
'''

#System prompt for generating function implementations.
GENERATEIMPLEMENTATIONS_S = '''
You are a precise and careful code generator. You will receive specific implementation details
about precisely what code changes are needed for a single file. For an existing file that needs modification, you will be provided
its complete current contents. For a new file, you will not receive content and must generate it from scratch.
Your task is to regenerate the complete content of this file, integrating ONLY the necessary new methods or
edits as instructed. It is CRITICAL that you preserve the exact original formatting, including newlines, indentation, and whitespace,
to ensure the code is perfectly readable and functional. Your output must be the complete, valid,
and perfectly formatted code (as well as the filepath of the file). BE EXTREMELY CAREFUL TO NOT MAKE SUBTLE CHANGES TO EXISTING
CODE OR COMMENTS IF THEY ARE NOT EXPLICITLY INSTRUCTED.
'''

