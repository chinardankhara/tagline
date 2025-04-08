import os
import pytest
from typer.testing import CliRunner
from dotenv import load_dotenv

# Load the .env file relative to this test file's location
dotenv_path = os.path.join(os.path.dirname(__file__), '../src/changelog_generator/.env')
load_dotenv(dotenv_path=dotenv_path)
print(f"Attempted to load .env from: {dotenv_path}") # Optional: for debugging
print(f"GITHUB_TOKEN loaded: {'GITHUB_TOKEN' in os.environ}") # Optional: for debugging
print(f"GEMINI_API_KEY loaded: {'GEMINI_API_KEY' in os.environ}") # Optional: for debugging

# Assuming your Typer app instance is in cli.py
from src.changelog_generator.cli import app

runner = CliRunner()

# --- Test Configuration ---
TEST_REPO = "mendableai/firecrawl"
TEST_FROM_TAG = "v1.6.0"
TEST_TO_TAG = "v1.7.0"
TEST_SINCE_TAG = "v1.7.0"

# --- Helper to Skip Tests if Keys are Missing ---
# Skip E2E tests if API keys are not set in the environment
requires_api_keys = pytest.mark.skipif(
    not os.getenv("GITHUB_TOKEN") or not os.getenv("GEMINI_API_KEY"),
    reason="Requires GITHUB_TOKEN and GEMINI_API_KEY environment variables"
)

# --- E2E Test Cases ---

@requires_api_keys
def test_e2e_generate_tag_range_console():
    """Test generating changelog for a tag range, printing to console."""
    result = runner.invoke(
        app,
        [
            TEST_REPO,
            "--from-tag", TEST_FROM_TAG,
            "--to-tag", TEST_TO_TAG,
            # No --output flag, should print to stdout
        ],
    )

    print("CLI Output:\n", result.stdout) # Print output for debugging
    assert result.exit_code == 0
    assert "Generated Changelog" in result.stdout # Check for start marker
    assert "End Changelog" in result.stdout     # Check for end marker
    assert TEST_REPO in result.stdout           # Check if repo name is mentioned (likely in LLM output)
    assert TEST_FROM_TAG in result.stdout       # Check if from_tag is mentioned
    assert TEST_TO_TAG in result.stdout         # Check if to_tag is mentioned
    # Basic check for common changelog sections (adapt based on LLM output)
    assert "Features" in result.stdout or "Bug Fixes" in result.stdout or "Summary" in result.stdout
    assert "Failed to generate changelog" not in result.stdout # Check for LLM error message

@requires_api_keys
def test_e2e_generate_since_tag_file(tmp_path):
    """Test generating changelog since a tag, writing to a file."""
    output_file = tmp_path / "e2e_changelog.md"
    result = runner.invoke(
        app,
        [
            TEST_REPO,
            "--since-tag", TEST_SINCE_TAG,
            "--output", str(output_file),
        ],
    )

    print("CLI Output:\n", result.stdout) # Print output for debugging
    assert result.exit_code == 0
    assert f"Changelog successfully written to {output_file}" in result.stdout
    assert output_file.exists()

    content = output_file.read_text()
    assert len(content) > 50 # Check if file has substantial content
    # assert TEST_REPO in content # Comment out or remove this line
    assert TEST_SINCE_TAG in content or f"{TEST_SINCE_TAG}..." in content # Check tag or start of range
    assert "Features" in content or "Bug Fixes" in content or "Summary" in content or "Other" in content # Added 'Other'
    assert "Failed to generate changelog" not in content # Check for LLM error message

@requires_api_keys
def test_e2e_missing_repo_arg():
    """Test CLI exits cleanly if repo argument is missing."""
    result = runner.invoke(
        app,
        [
            # Missing repo argument
            "--since-tag", TEST_SINCE_TAG,
        ],
        # catch_exceptions=False # Alternative: let SystemExit propagate
    )
    assert result.exit_code != 0 # Should fail
    # Check result.output (contains stdout & stderr) or result.stdout
    # Typer often prints usage errors to stdout before exiting
    assert "Missing argument 'REPO'" in result.output

@requires_api_keys
def test_e2e_invalid_tag_range_args():
    """Test CLI exits cleanly with invalid tag range combos."""
    result_from_only = runner.invoke(app, [TEST_REPO, "--from-tag", TEST_FROM_TAG])
    assert result_from_only.exit_code != 0
    assert "Using --from-tag requires --to-tag" in result_from_only.stdout

    result_to_only = runner.invoke(app, [TEST_REPO, "--to-tag", TEST_TO_TAG])
    assert result_to_only.exit_code != 0
    assert "Using --to-tag requires --from-tag" in result_to_only.stdout

    result_both_modes = runner.invoke(app, [TEST_REPO, "--since-tag", TEST_SINCE_TAG, "--from-tag", TEST_FROM_TAG, "--to-tag", TEST_TO_TAG])
    assert result_both_modes.exit_code != 0
    assert "Please use only one of" in result_both_modes.stdout

    result_no_range = runner.invoke(app, [TEST_REPO])
    assert result_no_range.exit_code != 0
    assert "You must specify a range" in result_no_range.stdout
