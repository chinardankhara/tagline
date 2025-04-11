import typer
from typing import Optional, Tuple
import os
import sys # For exiting
import re # For sanitizing filename
import requests  # Add requests library
import datetime
import traceback # Import traceback

# Use relative import again
from .processor import process_repository
# Need these for the pre-run
from .github_client import GitHubClient
from .llm_handler import LLMHandler

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
    # Remove leading/trailing whitespace and dots
    name = name.strip('. ')
    # Handle empty or dot-only names after sanitization
    if not name or name == '.':
        return "invalid_filename"
    return name

def trigger_deploy_workflow(
    target_repo: str,
    from_tag: str,
    to_tag: str,
    token: str,
    suggested_filename: Optional[str] = None, # Add suggested_filename
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
            # Conditionally add suggested_filename
            **({"suggested_filename": suggested_filename} if suggested_filename else {}),
        },
    }

    print(f"Triggering deployment workflow for {target_repo} ({from_tag}...{to_tag})...")
    if suggested_filename:
         print(f"  with suggested filename: {suggested_filename}")
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
    For BOTH modes, an AI-suggested filename is generated unless -o/--output is used with --local.
    A GitHub Token is needed for deployment and recommended for local generation.
    """

    # --- Validate common required tags ---
    if not (from_tag and to_tag):
        print("Error: --from-tag (-f) and --to-tag (-t) are required.", file=sys.stderr)
        raise typer.Exit(code=1)

    # --- Common setup for both modes: Get AI suggestion ---
    # We need the AI suggestion *before* triggering the workflow, even if not local.
    # However, if --local and --output are specified, we skip this.
    suggested_filename: Optional[str] = None
    changelog_content: Optional[str] = None # Store content if generated locally
    tag_range_tuple = (from_tag, to_tag)

    if not (local and output): # Only run processor if not doing local with specified output
        if not token:
             print("Warning: No GitHub token provided (--token or GITHUB_TOKEN env var). Needed for AI filename suggestion and required for deployment. Public repos might work, but rate limits apply.", file=sys.stderr)
             if not local:
                print("Error: Cannot trigger deployment without a GitHub token.", file=sys.stderr)
                raise typer.Exit(code=1)
             # Allow proceeding for local without token, but filename suggestion will likely fail if repo is private

        try:
            print(f"Attempting to generate changelog/suggest filename for {repo} ({from_tag}...{to_tag})...")
            # We need the content if we are generating locally, otherwise just the filename
            changelog_content, suggested_filename = process_repository(
                repo=repo,
                token=token,
                tag_range=tag_range_tuple,
            )
            if suggested_filename:
                print(f"AI suggested filename: {suggested_filename}")
            else:
                print("Warning: AI did not suggest a filename.")

            # If generating locally, ensure content exists
            if local and (not changelog_content or not changelog_content.strip()):
                 print("Changelog content was not generated or is empty. Exiting.")
                 raise typer.Exit(code=1)

        except Exception as e:
            print(f"\nAn error occurred during initial processing: {e}", file=sys.stderr)
            traceback.print_exc() # Print detailed traceback
            raise typer.Exit(code=1)
    else:
         print("Skipping AI filename suggestion because --local and --output were specified.")

    # --- Action: Trigger Deployment ---
    if not local:
        if output:
             print("Warning: -o/--output is ignored when deploying (not using --local).", file=sys.stderr)

        # Trigger deployment and pass the suggested filename
        trigger_deploy_workflow(
            target_repo=repo,
            from_tag=from_tag,
            to_tag=to_tag,
            token=token,
            suggested_filename=suggested_filename
        )
        return

    # --- Action: Local Generation (if --local is used) ---
    else:
        # Content and suggested_filename were potentially fetched above
        # If output was specified, content/suggestion were skipped, so we need to run processor now
        if output:
             if not token:
                 print("Warning: No GitHub token provided (--token or GITHUB_TOKEN env var). Public repos might work, but rate limits apply.", file=sys.stderr)
             try:
                 print(f"Generating local changelog content for {repo} ({from_tag}...{to_tag}) with specified output...")
                 changelog_content, _ = process_repository( # Discard suggested filename here
                     repo=repo,
                     token=token,
                     tag_range=tag_range_tuple,
                 )
                 if not changelog_content or not changelog_content.strip():
                     print("Changelog content was not generated or is empty. Exiting.")
                     raise typer.Exit(code=1)
             except Exception as e:
                 print(f"\nAn error occurred during local processing with -o: {e}", file=sys.stderr)
                 traceback.print_exc()
                 raise typer.Exit(code=1)

        # --- Determine Output Filename ---
        output_filename = output # Start with user-provided output
        if output_filename:
             print(f"User specified output file: {output_filename}")
             output_dir = os.path.dirname(output_filename)
             if output_dir:
                 os.makedirs(output_dir, exist_ok=True)
             elif not os.path.isabs(output_filename):
                 # If relative path with no dir, put in default dir
                 os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)
                 output_filename = os.path.join(LOCAL_OUTPUT_DIR, output_filename)
             # If absolute path, use it as is
        else:
            # No output specified, use AI suggestion or fallback
            if suggested_filename:
                safe_suggested_name = sanitize_filename(suggested_filename)
                if not safe_suggested_name.lower().endswith('.md'):
                     safe_suggested_name += ".md"
                output_filename = os.path.join(LOCAL_OUTPUT_DIR, safe_suggested_name)
                print(f"Using AI suggested filename (sanitized): {output_filename}")
            else:
                print("AI did not suggest a filename. Using default naming scheme.")
                sanitized_repo = sanitize_filename(repo)
                sanitized_from = sanitize_filename(tag_range_tuple[0])
                sanitized_to = sanitize_filename(tag_range_tuple[1])
                filename = f"{sanitized_repo}_{sanitized_from}_to_{sanitized_to}.md"
                output_filename = os.path.join(LOCAL_OUTPUT_DIR, filename)

            os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)

        # --- Write Output File ---
        print(f"Attempting to write changelog to {output_filename}...")
        try:
            with open(output_filename, "w", encoding='utf-8') as f:
                # Ensure changelog_content exists (should be guaranteed by checks above)
                if changelog_content is None:
                     print("Error: Cannot write file, changelog content is missing.", file=sys.stderr)
                     raise typer.Exit(code=1)
                f.write(changelog_content)
            print(f"Changelog successfully written locally to {output_filename}")
        except IOError as e:
            print(f"Error writing to output file {output_filename}: {e}", file=sys.stderr)
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

