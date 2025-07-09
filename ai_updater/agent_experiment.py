# For this file I am going to try one central reAct agent that will have access to all the necessary tools.

import getpass
import os
import subprocess

from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt.chat_agent_executor import AgentState

from agent_prompts import agent_prompts, agent_system_prompts

def write_file_tool(filepath: str, content: str) -> None:
    """Write content to a file at the specified path. This will overwrite the existing file contents if it already exists.

    Args:
        filepath: Path to the file to write
        content: Content to write to the file
    """
    original_filename = os.path.basename(filepath)
    filename_without_ext, file_ext = os.path.splitext(original_filename)
    ai_filename = f"{filename_without_ext}{file_ext}"
    print(f"Writing to: {ai_filename}")
    with open(ai_filename, 'w') as f:
        f.write(content)
    print(f"Successfully wrote to: {ai_filename} \n")

def read_file_tool(file_path: str) -> str:
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
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

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

def main():
    """Main entry point for the agent experiment."""
    if not os.environ.get("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter API key for Google Gemini: ")

    gemini = init_chat_model("gemini-2.5-flash", temperature=0.0)

    # Get the current directory and SDK root directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sdk_root_dir = os.path.dirname(current_dir)

    # Get SDK tree, tests tree, and git diff
    try:
        # Try to read from files first (for testing scenarios)
        sdk_tree = read_file_content(os.path.join(current_dir, "sdktree.txt"))
        tests_tree = read_file_content(os.path.join(current_dir, "teststree.txt"))
        git_diff = read_file_content(os.path.join(current_dir, "proto_diff.txt"))
    except:
        # If files don't exist, generate the data
        git_diff_dir = os.path.join(sdk_root_dir, "src", "viam", "gen")
        sdk_tree = subprocess.check_output(["tree", os.path.join("src", "viam")], text=True, cwd=sdk_root_dir)
        tests_tree = subprocess.check_output(["tree", "tests"], text=True, cwd=sdk_root_dir)
        git_diff = subprocess.check_output(["git", "diff", "HEAD~1", "HEAD", "--", git_diff_dir, ":!*_pb2.py"],
                                         text=True, cwd=sdk_root_dir)

        # Save the data for future use
        write_file_tool(os.path.join(current_dir, "sdktree.txt"), sdk_tree)
        write_file_tool(os.path.join(current_dir, "teststree.txt"), tests_tree)
        write_file_tool(os.path.join(current_dir, "proto_diff.txt"), git_diff)

    # Format the prompt with the SDK tree, tests tree, and git diff
    system_prompt = agent_system_prompts[0]
    prompt = agent_prompts[0].format(
        sdk_tree=sdk_tree,
        tests_tree=tests_tree,
        git_diff=git_diff
    )

    agent = create_react_agent(
        model=gemini,
        tools=[read_file_tool, write_file_tool],
    )

    agent.invoke(input={"messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]})

if __name__ == "__main__":
    main()
