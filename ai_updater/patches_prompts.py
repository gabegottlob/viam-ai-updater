#Main prompt for generating patches
GENERATEPATCHES_P = """
You need to generate search-and-replace instructions for the following changes in an existing file:
{implementation_detail}

I will now provide you with the complete current contents of the existing file that you need to modify.
Your output should be search-and-replace blocks that, when applied to the `existing_file_content`,
produces the exact changes described in the `implementation_detail`.
{existing_file_content}

Task: Generate search-and-replace instructions that precisely reflect the necessary edits as described in the implementation details.

CRITICAL INSTRUCTIONS:
1.  **Search-and-Replace Format**: Your output MUST use the following format:
    *   Use `REPLACE:` followed by the exact text to find, then `WITH:` followed by the replacement text.
    *   Each block must contain exact whitespace, indentation, and line breaks.
2.  **Exact Text Matching**: The text after `REPLACE:` must match exactly what exists in the file - character for character, including all whitespace and indentation.
3.  **Unique Matches**: Choose search text that appears only once in the file to avoid ambiguity. Include enough context to make the match unique.
4.  **Preserve Unchanged Code**: The replacement text should include all the original code plus your additions/modifications.
5.  **No Additional Content**: Your output should contain *only* the search-and-replace blocks. Do not include any introductory or concluding remarks, explanations, or code wrappers.

Provide the search-and-replace instructions.

Here are some examples of correctly formatted search-and-replace blocks:

Example 1: Adding a new method
Implementation Detail: "Add a new method `calculate_area(self)` that returns `self.width * self.height` to the Rectangle class in `shapes.py`."
Existing File Content:
```python
class Rectangle:
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def get_perimeter(self):
        return 2 * (self.width + self.height)
Expected Output:
REPLACE:
    def get_perimeter(self):
        return 2 * (self.width + self.height)
WITH:
    def get_perimeter(self):
        return 2 * (self.width + self.height)

    def calculate_area(self):
        return self.width * self.height
Example 2: Modifying an existing function
Implementation Detail: "Update the greet function to accept an optional title parameter and include it in the greeting."
Existing File Content:
pythondef greet(name):
    return f"Hello, {{name}}!"

def farewell(name):
    return f"Goodbye, {{name}}!"
Expected Output:
REPLACE:
def greet(name):
    return f"Hello, {{name}}!"
WITH:
def greet(name, title=None):
    if title:
        return f"Hello, {{title}} {{name}}!"
    return f"Hello, {{name}}!"
Example 3: Multiple changes in existing file
Implementation Detail: "In utils.py, add import statement import json at the top after existing imports, and add a new function save_to_json(data, filename) at the end of the file."
Existing File Content:
pythonimport os
import sys

def load_file(filename):
    with open(filename, 'r') as f:
        return f.read()

def process_text(text):
    return text.strip().upper()
Expected Output:
REPLACE:
import os
import sys
WITH:
import os
import sys
import json

REPLACE:
def process_text(text):
    return text.strip().upper()
WITH:
def process_text(text):
    return text.strip().upper()

def save_to_json(data, filename):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
"""

#System prompt for generating patches.
GENERATEPATCHES_S = """
You are a precise and careful search-and-replace instruction generator. You will receive specific implementation details
about precisely what code changes are needed for an existing file, along with its complete current contents.
Your task is to generate search-and-replace blocks that integrate ONLY the necessary new methods or
edits as instructed. It is CRITICAL that your search text matches exactly what exists in the file.
Use REPLACE: and WITH: blocks with exact text matching.
BE EXTREMELY CAREFUL TO MATCH EXISTING CODE EXACTLY - including all whitespace, indentation, and formatting.
The search text must be unique (appear only once) and the replacement text should preserve all original code while adding the requested changes.
Choose search patterns that include enough context to be unambiguous but not so much that they're fragile.
"""
