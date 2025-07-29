'''
Proto update hashes to use as test cases:
    1. Added new method to component: 8d6b63a0fade65b8054cafb849d844bcdb089761
        Merged Implementation: 11dab7c500de784a431ea771709c6adbef69e06b
    2. Added new field to app client: ef8ae496df44a8e881836e76e7e953ed5e6bbd4c
        Merged Implementation: 8c0fc88a80c1ac5d61acc7d523c0bb9443acf0b4
    3. Added entire new components (Button and Switch): e8818bce81be520a740bf3da725c8d816fe2aa4b
        Merged Implementation (Button): dee3547b0c98c2c2fd7fbdd2b239899e5d031795
        Merged Implementation (Switch): 096a5083f0d2c8b1152e8aa3b6ed233b1af60623
    4. Updated a version number: cd8765e9b2d6adcdeb7ecda6c2b72940d4439d0a
        No merged implementation because no changes need to be made.
'''

'''
NOTE: The AI updater is inherently nondeterministic and hard to quantitatively test with a testing suite.
While the following tests have basic assertions to ensure the AI generated certain files, they do not ensure that the AI generated the correct code.
The recommended method of testing is to run these tests and manually inspect the AI generated results compared to the expected human implementation.

To run the tests via pytest, run the following command:
pytest test_ai_updater.py
or to specify specific scenarios, run the following command:
pytest test_ai_updater.py -k "scenario-1 or scenario-2"
'''

import os
import sys
import subprocess
import tempfile
import shutil
import pytest

SCENARIOS = [
    {
        "name": "scenario-1",
        "description": "Added new method to component",
        "pre_implementation_commit": "8d6b63a0fade65b8054cafb849d844bcdb089761",
        "specific_proto_diff_file": True,
        "sdk": "python",
        "repo_url": "git@github.com:viamrobotics/viam-python-sdk.git"
    },
    {
        "name": "scenario-2",
        "description": "Added new field to app client",
        "pre_implementation_commit": "ef8ae496df44a8e881836e76e7e953ed5e6bbd4c",
        "specific_proto_diff_file": False,
        "sdk": "python",
        "repo_url": "git@github.com:viamrobotics/viam-python-sdk.git"
    },
    {
        "name": "scenario-3",
        "description": "Added entire new components (Button and Switch)",
        "pre_implementation_commit": "e8818bce81be520a740bf3da725c8d816fe2aa4b",
        "specific_proto_diff_file": False,
        "sdk": "python",
        "repo_url": "git@github.com:viamrobotics/viam-python-sdk.git"
    },
    {
        "name": "scenario-4",
        "description": "Updated a version number (no changes needed)",
        "pre_implementation_commit": "cd8765e9b2d6adcdeb7ecda6c2b72940d4439d0a",
        "specific_proto_diff_file": True,
        "sdk": "python",
        "repo_url": "git@github.com:viamrobotics/viam-python-sdk.git"
    },
    {
        "name": "scenario-5",
        "description": "Single field update that leads to many small changes in long file",
        "pre_implementation_commit": "7e92b134e5440f5aed861d1117ec31de118a70c9",
        "specific_proto_diff_file": True,
        "sdk": "python",
        "repo_url": "git@github.com:viamrobotics/viam-python-sdk.git"
    },
    {
        "name": "scenario-6",
        "description": "Typescript Gripper get_kinematics",
        "pre_implementation_commit": "c3bb320c32384f09da161dff2fc188127c5661f2",
        "specific_proto_diff_file": False,
        "sdk": "typescript",
        "repo_url": "git@github.com:viamrobotics/viam-typescript-sdk.git"
    },
    {
        "name": "scenario-7",
        "description": "C++ Gripper get_kinematics",
        "pre_implementation_commit": "e834a64f4341f10c37a974c86c8ef37a9f334a60",
        "specific_proto_diff_file": False,
        "sdk": "cpp",
        "repo_url": "git@github.com:viamrobotics/viam-cpp-sdk.git"
    },
    {
        "name": "scenario-8",
        "description": "Flutter Gripper get_kinematics",
        "pre_implementation_commit": "834b5d2c49eae812cf91e94fc39f72ed46597f5f",
        "specific_proto_diff_file": True,
        "sdk": "flutter",
        "repo_url": "git@github.com:viamrobotics/viam-flutter-sdk.git"
    }
]

@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS])
def test_ai_updater(scenario):
    """Test the AI updater against a specific scenario."""
    _run_test_scenario(scenario, skip_comparison=False)

def _run_test_scenario(scenario, skip_comparison=True):
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    current_scenario_dir = os.path.join(tests_dir, scenario["name"])

    # Create a temporary directory for this test
    with tempfile.TemporaryDirectory(dir=current_scenario_dir) as temp_dir:
        # Clone the repository and checkout the pre-update commit
        subprocess.run(["git", "clone", scenario["repo_url"], temp_dir], check=True, cwd=current_scenario_dir)
        subprocess.run(["git", "checkout", scenario["pre_implementation_commit"]], check=True, cwd=temp_dir)

        # Clean and recreate the ai_generated directory for this scenario
        ai_generated_dir = os.path.join(tests_dir, scenario["name"], "ai_generated")
        if os.path.exists(ai_generated_dir):
            shutil.rmtree(ai_generated_dir)
        os.makedirs(ai_generated_dir)

        # Runs AI updater with test flag
        python_path = sys.executable
        sdk = scenario['sdk']
        subprocess.run([python_path, "../ai_updater.py", "--debug", "--sdk", sdk, "--test", temp_dir],
                       check=True,
                       env=os.environ.copy(),
                       cwd=tests_dir)

        if not skip_comparison:
            # Get the human implementation for comparison
            human_output_dir = os.path.join(tests_dir, scenario["name"], "expected")

            # Check if AI generated the expected files
            for root, _, files in os.walk(human_output_dir):
                for file in files:
                    human_file = os.path.join(root, file)
                    rel_path = os.path.relpath(human_file, human_output_dir)
                    if "__pycache__" in rel_path.split(os.sep):
                        continue
                    ai_file = os.path.join(ai_generated_dir, rel_path)
                    assert os.path.exists(ai_file), f"AI did not generate expected file: {rel_path}"

if __name__ == "__main__":
    print("Running all scenarios for debugging...")
    for scenario in SCENARIOS[5:]: #change this to run specific scenarios if desired
        print(f"Running scenario: {scenario['name']}")
        _run_test_scenario(scenario) # skip_comparison defaults to True for standalone run
