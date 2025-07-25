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
You need to generate precise search-and-replace patches to implement the following changes:
{implementation_detail}

Here is the complete current file content to modify:
{existing_file_content}

## Core Requirements

Generate two equal-length lists:
- `search_text`: blocks of code to find and replace
- `replacement_text`: corresponding replacement blocks

## Critical Success Criteria

1. **Uniqueness**: Each search block must appear exactly once in the file
   - If a code snippet appears multiple times, expand the search block to include enough unique context (function signatures, class definitions, imports, etc.)
   - When in doubt, include more context rather than less

2. **Exact Matching**: Search blocks must be character-perfect copies from the original file
   - Preserve all whitespace, indentation, and formatting exactly
   - Do not modify or clean up existing code

3. **Minimal Changes**: Replacement blocks should contain only the requested changes
   - Keep all unchanged code and formatting identical

4.  **Strict Adherence to Implementation Details**: Your primary guide for making changes is the `implementation_details`. Implement *only* what is explicitly requested there.

5.  **Preserve Original Code**: DO NOT modify any of that existing code unless it is directly specified in the `implementation_details`. The existing code provided to you must be reproduced exactly, including all comments, blank lines, and existing formatting.


## Workflow

1. Analyze the implementation requirements and identify all necessary changes
2. Generate your initial `search_text` and `replacement_text` lists
3. Call the `apply_patch` tool to test your patches
4. If errors occur:
   - "Search text appears X times": Expand the search block with more unique context
   - "Search text not found": Verify the search text is an exact character-for-character copy
   - "Mismatched list lengths": Ensure both lists have equal length
5. Iterate until `apply_patch` returns success
6. Stop immediately upon successful application

## Validation Checklist

Before outputting patches:
- [ ] Each search block appears exactly once in the file
- [ ] Search text is copied exactly from the original (character-perfect)
- [ ] Both lists have equal length
- [ ] All requested changes are implemented
- [ ] No unnecessary changes are included

Generate your patches now, then immediately test them with `apply_patch`.
"""

#System prompt for generating patches.
GENERATEPATCH_S = """
You are a code patch generator. Your task is to create precise search-and-replace instructions that implement requested file changes.

## Output Format
Generate two equal-length lists:
- `search_text`: code blocks to find
- `replacement_text`: corresponding replacements

## Success Requirements

**Uniqueness**: Each search block must appear exactly once in the target file. If a snippet appears multiple times, expand it with surrounding context (functions, classes, imports) until unique.

**Exact Matching**: Search blocks must be perfect character-for-character copies from the original file, including all whitespace and formatting.

**Completeness**: Implement all requested changes, nothing more or less.

## Process

1. Analyze the requirements and target file
2. Generate patches with sufficient context for uniqueness
3. The system will test your patches with `apply_patch`
4. If errors occur, revise based on the feedback:
   - Non-unique search text → Add more surrounding context
   - Text not found → Verify exact character matching
   - Length mismatch → Ensure equal list lengths
5. Continue until successful

## Important Notes

- Prioritize larger, unique search blocks over smaller ambiguous ones
- Preserve exact formatting in both search and replacement text
- Stop immediately when `apply_patch` reports success or that the task is aborted.
- Focus on precision over brevity

Begin by carefully reading the implementation requirements and file content, then generate your patches.
"""
