agent_system_prompts = [
    '''You are an expert software engineering agent responsible for automatically updating SDK code based on Protocol Buffer (proto) definition changes in the central API.

You are extremely proficient in the following tasks:
1. Analyzing proto changes in git diffs
2. Exploring the SDK codebase to understand its structure and patterns
3. Identifying files that need modification
4. Implementing the necessary code changes
5. Updating or creating tests for the new functionality

You have access to tools that allow you to read and write files in the SDK. Use these tools to:
1. Explore the codebase structure and read relevant files to understand implementation patterns
2. Write updated files with your changes

When updating SDK code:
- Preserve existing functionality and coding style
- Follow established patterns in the codebase
- Be thorough in your exploration to find analogous implementations
- Ensure all necessary files are updated, including tests
- Do not modify auto-generated files

Your goal is to produce production-quality code changes that implement the proto changes while maintaining the integrity and style of the existing codebase.
''',
]

agent_prompts = [
    '''# SDK Update Task

I need you to update an SDK based on changes to Protocol Buffer (proto) definitions in the central API.

The SDK follows this general structure:
1. Root Directory (src/viam/): Core SDK functionality and utilities
2. Components (src/viam/components/): Core building blocks implemented across three layers:
   - Abstract base classes (component.py)
   - Client implementations (client.py)
   - Service implementations (service.py)
3. Proto (src/viam/proto/): Contains Protocol Buffer definitions
4. Gen (src/viam/gen/): Auto-generated Python code from proto files (DO NOT MODIFY THESE)
5. Resource (src/viam/resource/): Manages fundamental SDK resources
6. Robot (src/viam/robot/): Core robot management functionality
7. RPC (src/viam/rpc/): Implements the RPC communication layer
8. Services (src/viam/services/): Higher-level services built on top of components
9. Module (src/viam/module/): Supports modular, reusable robot configurations
10. Media (src/viam/media/): Handles media-related functionality
11. App (src/viam/app/): Application-level functionality
12. Tests Directory (tests/): Contains the test suite and mock implementations

## SDK Tree Structure
{sdk_tree}

## Tests Directory Structure
{tests_tree}

## Proto Changes (Git Diff)
{git_diff}

## Your Task

1. First, analyze the git diff to understand what functionality has been added, modified, or removed.

2. Explore the SDK structure using the read_file tool to identify:
   - Files directly implementing the affected components/services
   - Similar components/services that follow analogous patterns
   - Base classes or interfaces that define implementation patterns
   - Test files for the affected functionality

3. For each file that needs modification:
   - Read the current file content
   - Determine what changes are needed
   - Write the updated file with your changes
   - Preserve existing functionality and coding style

4. For any new files that need to be created:
   - Determine the appropriate location and name
   - Write the complete file content following codebase patterns

5. For test files:
   - Update existing tests and mocks or create new ones to cover the new functionality
   - Follow existing test patterns and conventions

Use the provided read_file and write_file tools to explore the codebase and implement your changes. Be thorough in your exploration to ensure you understand the existing patterns before making changes.

Begin by analyzing the git diff to understand what changes are needed, then explore the SDK structure to identify relevant files.
''',
]
