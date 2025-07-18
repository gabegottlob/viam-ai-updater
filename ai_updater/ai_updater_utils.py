def write_to_file(filepath: str, content: str, quiet: bool = False) -> None:
    """Write content to a file at the specified path. This will overwrite the existing file contents if it already exists.

    Args:
        filepath: Path to the file to write
        content: Content to write to the file
    """
    if not quiet:
        print(f"Writing to: {filepath}")
    with open(filepath, 'w') as f:
        f.write(content)
    if not quiet:
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
        print(f"Error reading file: {str(e)}")
        return f"Error reading file: {str(e)}"

def calculate_cost(usage_metadata, model: str) -> float:
    """Calculates the estimated cost of a Gemini response.

    Args:
        usage_metadata: The usage_metadata object from the Gemini response.
        model: The name of the Gemini model used to generate the response.

    Returns:
        float: The estimated cost of the response.
    """
    if model == "gemini-2.5-flash":
        INPUT_COST_PER_MILLION_TOKENS = 0.30
        OUTPUT_COST_PER_MILLION_TOKENS = 2.50
    else:
        print(f"WARNING: {model} is not a supported model for cost calculation")
        return 0.0

    input_tokens = usage_metadata.prompt_token_count
    output_tokens = usage_metadata.candidates_token_count

    cost = (input_tokens / 1_000_000) * INPUT_COST_PER_MILLION_TOKENS + (output_tokens / 1_000_000) * OUTPUT_COST_PER_MILLION_TOKENS
    return cost
