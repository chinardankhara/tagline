import typer
from typing import Optional, Tuple
import os
import sys # For exiting
import re # For sanitizing filename
import requests  # Add requests library
import datetime

# Use relative import again
from .processor import process_repository

app = typer.Typer(
    help="AI Changelog Generator: Creates and deploys changelogs from GitHub repositories using AI."
)

# --- Constants ---
# Replace with your username and the repo where the Action workflow lives
ACTION_REPO_OWNER = "chinardankhara"
ACTION_REPO_NAME = "llm-changelog"
WORKFLOW_ID = "deploy_changelog.yml" # The filename of your workflow
LOCAL_OUTPUT_DIR = "changelogs" # Directory to save local files

def sanitize_filename(name: str) -> str:
    """Removes or replaces characters unsafe for filenames."""
    # Replace slashes commonly found in repo names
    name = name.replace("/", "-")
    # Remove other potentially problematic characters (add more as needed)
    name = re.sub(r'[<>:"\\|?*]', '', name)
    return name

def trigger_deploy_workflow(
    target_repo: str,
    from_tag: str,
    to_tag: str,
    token: str,
    branch: str = "main", # Or the default branch of ACTION_REPO_NAME
):
    """Triggers the GitHub Actions workflow_dispatch event."""
    if not token:
        print("Error: A GitHub token with 'repo' scope is required to trigger the deploy workflow.", file=sys.stderr)
        print("Please provide it via --token or set the GITHUB_TOKEN environment variable.", file=sys.stderr)
        raise typer.Exit(code=1)

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}",
    }
    url = f"https://api.github.com/repos/{ACTION_REPO_OWNER}/{ACTION_REPO_NAME}/actions/workflows/{WORKFLOW_ID}/dispatches"
    data = {
        "ref": branch, # The branch where the workflow file lives
        "inputs": {
            "target_repo": target_repo,
            "from_tag": from_tag,
            "to_tag": to_tag,
        },
    }

    print(f"Triggering deployment workflow for {target_repo} ({from_tag}...{to_tag})...")
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        print(f"Successfully triggered workflow dispatch. Status code: {response.status_code}")
        print(f"Check the Actions tab in {ACTION_REPO_OWNER}/{ACTION_REPO_NAME} for progress.")

    except requests.exceptions.RequestException as e:
        print(f"Error triggering workflow dispatch: {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            try:
                print(f"Response body: {e.response.json()}", file=sys.stderr)
            except ValueError: # If response is not JSON
                 print(f"Response body: {e.response.text}", file=sys.stderr)
        raise typer.Exit(code=1)

@app.command()
def generate(
    repo: str = typer.Argument(
        ..., help="Repository name ('owner/repo') for which to generate/deploy the changelog."
    ),
    from_tag: Optional[str] = typer.Option(
        None, "-f", "--from-tag",
        help="Start tag/ref for the changelog range (required for both modes)."
    ),
    to_tag: Optional[str] = typer.Option(
        None, "-t", "--to-tag",
        help="End tag/ref for the changelog range (required for both modes)."
    ),
    output: Optional[str] = typer.Option(
        None, "-o", "--output",
        help="Local output file path (only used with --local). Overrides AI suggestion."
    ),
    token: Optional[str] = typer.Option(
        lambda: os.environ.get("GITHUB_TOKEN"),
        "--token",
        help="GitHub PAT (repo scope required for deploy, also used for local private/rate limit). Reads from GITHUB_TOKEN env var.",
        show_default="Reads from GITHUB_TOKEN env var",
    ),
    local: bool = typer.Option(
        False,
        "--local",
        help="Generate the changelog locally instead of triggering deployment.",
        is_flag=True,
    ),
):
    """
    Generates and optionally DEPLOYS a changelog for a given tag range.

    Requires --from-tag (-f) and --to-tag (-t) for both deployment and local generation.
    Use --local to generate the file locally in the './changelogs' directory instead of deploying.
    If --local is used and -o/--output is NOT provided, the AI will suggest a filename.
    A GitHub Token is needed for deployment and recommended for local generation.
    """

    # --- Validate common required tags ---
    if not (from_tag and to_tag):
        print("Error: --from-tag (-f) and --to-tag (-t) are required.", file=sys.stderr)
        raise typer.Exit(code=1)

    # --- Action: Trigger Deployment (Default) ---
    if not local:
        if output:
             print("Warning: -o/--output is ignored when deploying (not using --local).", file=sys.stderr)

        # Trigger deployment and exit
        trigger_deploy_workflow(target_repo=repo, from_tag=from_tag, to_tag=to_tag, token=token)
        return

    # --- Action: Local Generation (if --local is used) ---
    else:
        if not token:
             print("Warning: No GitHub token provided (--token or GITHUB_TOKEN env var). Public repos might work, but rate limits apply.")

        tag_range_tuple = (from_tag, to_tag)

        # --- Generate Content and Suggested Filename ---
        changelog_content = None
        suggested_filename = None
        try:
            print(f"Attempting local generation for {repo} ({from_tag}...{to_tag}) using processor...")
            # process_repository now returns a tuple
            changelog_content, suggested_filename = process_repository(
                repo=repo,
                token=token,
                tag_range=tag_range_tuple,
            )

            if not changelog_content or not changelog_content.strip():
                 print("Changelog content was not generated or is empty. Exiting.")
                 raise typer.Exit(code=1)

        except Exception as e:
            print(f"\nAn error occurred during processing: {e}", file=sys.stderr)
            raise typer.Exit(code=1)

        # --- Determine Output Filename --- 
        output_filename = output
        if output_filename:
             print(f"User specified output file: {output_filename}")
             output_dir = os.path.dirname(output_filename)
             if output_dir:
                 os.makedirs(output_dir, exist_ok=True)
             elif not os.path.isabs(output_filename):
                 os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)
                 output_filename = os.path.join(LOCAL_OUTPUT_DIR, output_filename)
        else:
            if suggested_filename:
                safe_suggested_name = sanitize_filename(suggested_filename)
                if not safe_suggested_name.lower().endswith('.md'):
                     safe_suggested_name += ".md"
                output_filename = os.path.join(LOCAL_OUTPUT_DIR, safe_suggested_name)
                print(f"Using AI suggested filename (sanitized): {output_filename}")
            else:
                print("AI did not suggest a filename. Using default naming scheme.")
                sanitized_repo = sanitize_filename(repo)
                # Only tag_range_tuple is possible now
                sanitized_from = sanitize_filename(tag_range_tuple[0])
                sanitized_to = sanitize_filename(tag_range_tuple[1])
                filename = f"{sanitized_repo}_{sanitized_from}_to_{sanitized_to}.md"
                output_filename = os.path.join(LOCAL_OUTPUT_DIR, filename)

            os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)

        # --- Write Output File ---
        print(f"Attempting to write changelog to {output_filename}...")
        try:
            with open(output_filename, "w", encoding='utf-8') as f:
                f.write(changelog_content)
            print(f"Changelog successfully written locally to {output_filename}")
        except IOError as e:
            print(f"Error writing to output file {output_filename}: {e}", file=sys.stderr)
            raise typer.Exit(code=1)


if __name__ == "__main__":
    # No need to check for requests here anymore as it's always needed for deploy (default)
    app()
