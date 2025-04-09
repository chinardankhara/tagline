import typer
from typing import Optional, Tuple
import os
import sys # For exiting
import re # For sanitizing filename
import requests  # Add requests library

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
    since_tag: Optional[str] = typer.Option(None, "--since-tag", help="Generate locally for commits since this tag (requires --local)."),
    from_tag: Optional[str] = typer.Option(None, "--from-tag", help="Start tag for the changelog range (required for deploy)."),
    to_tag: Optional[str] = typer.Option(None, "--to-tag", help="End tag for the changelog range (required for deploy)."),
    output: Optional[str] = typer.Option(None, "-o", "--output", help="Local output file path (requires --local). Overrides default naming."),
    branch: Optional[str] = typer.Option(None, "-b", "--branch", help="Specify a branch/commit for local comparison (requires --local)."),
    token: Optional[str] = typer.Option(
        lambda: os.environ.get("GITHUB_TOKEN"), # Read from GITHUB_TOKEN now
        "--token",
        # Adjusted help text: Token is primarily for deployment trigger, but also needed for local private repo access.
        help="GitHub PAT (repo scope required for deploy). Reads from GITHUB_TOKEN env var.",
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
    Generates and DEPLOYS a changelog by triggering a GitHub Action by default.

    Requires --from-tag and --to-tag for deployment.
    Use --local to generate the file locally in the './changelogs' directory instead.
    A GitHub Token (repo scope) is required for deployment.
    """

    # --- Action: Trigger Deployment (Default) ---
    if not local:
        if not (from_tag and to_tag):
             print("Error: --from-tag and --to-tag are required to trigger deployment.", file=sys.stderr)
             raise typer.Exit(code=1)
        if since_tag or output or branch:
             print("Warning: --since-tag, -o/--output, and -b/--branch are ignored when deploying.", file=sys.stderr)

        # Trigger deployment and exit
        # Pass the token read from env/option
        trigger_deploy_workflow(target_repo=repo, from_tag=from_tag, to_tag=to_tag, token=token)
        return # Exit CLI after triggering

    # --- Action: Local Generation (if --local is used) ---
    else:
        # Validation for local generation
        range_defined = since_tag or (from_tag and to_tag)
        if not range_defined:
            print("Error: For local generation (--local), specify a range using --since-tag or --from-tag/--to-tag.")
            raise typer.Exit(code=1)
        if from_tag and not to_tag:
            print("Error: Using --from-tag requires --to-tag.")
            raise typer.Exit(code=1)
        if to_tag and not from_tag:
            print("Error: Using --to-tag requires --from-tag.")
            raise typer.Exit(code=1)
        if since_tag and (from_tag or to_tag):
             print("Error: Use only one of --since-tag or (--from-tag and --to-tag) for local generation.")
             raise typer.Exit(code=1)

        if not token:
             print("Warning: No GitHub token provided. Public repos might work, but rate limits apply.")

        tag_range_tuple = (from_tag, to_tag) if from_tag and to_tag else None

        # Determine default output filename if needed, placing it in LOCAL_OUTPUT_DIR
        output_filename = output
        if output_filename is None:
            sanitized_repo = sanitize_filename(repo)
            if since_tag:
                sanitized_tag = sanitize_filename(since_tag)
                filename = f"{sanitized_repo}_since_{sanitized_tag}.md"
            elif tag_range_tuple:
                sanitized_from = sanitize_filename(tag_range_tuple[0])
                sanitized_to = sanitize_filename(tag_range_tuple[1])
                filename = f"{sanitized_repo}_{sanitized_from}_to_{sanitized_to}.md"
            else:
                 print("Error: Could not determine tag range for default filename.", file=sys.stderr)
                 raise typer.Exit(code=1)
            # Ensure the local output directory exists
            os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)
            output_filename = os.path.join(LOCAL_OUTPUT_DIR, filename)
        elif not os.path.dirname(output_filename):
            # If user provided just a filename, prepend the directory
             os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)
             output_filename = os.path.join(LOCAL_OUTPUT_DIR, output_filename)


        try:
            print(f"Attempting to generate changelog locally via process_repository for {repo}...")
            changelog_content = process_repository(
                repo=repo,
                token=token, # Token might be needed for private repo access
                since_tag=since_tag,
                tag_range=tag_range_tuple,
                target_branch=branch,
            )

            if changelog_content:
                # Check if content is just whitespace
                if not changelog_content.strip():
                     print("Changelog content generated but is empty or whitespace. File not written.")
                else:
                    print(f"Changelog content generated (length: {len(changelog_content)}). Attempting to write to {output_filename}...")
                    try:
                        with open(output_filename, "w") as f:
                            f.write(changelog_content)
                        print(f"Changelog successfully written locally to {output_filename}")
                    except IOError as e:
                        print(f"Error writing to output file {output_filename}: {e}", file=sys.stderr)
                        raise typer.Exit(code=1)
            else:
                # This executes if process_repository returns None or ""
                print("process_repository returned None or empty string. File not written.")

        except Exception as e:
            print(f"\nAn error occurred during local processing: {e}", file=sys.stderr)
            raise typer.Exit(code=1)


if __name__ == "__main__":
    # No need to check for requests here anymore as it's always needed for deploy (default)
    app()
