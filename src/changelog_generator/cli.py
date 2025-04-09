import typer
from typing import Optional, Tuple
import os
import sys # For exiting
import re # For sanitizing filename

# Use relative import again
from .processor import process_repository

app = typer.Typer(
    help="AI Changelog Generator: Creates changelogs from GitHub repositories using AI."
)

def sanitize_filename(name: str) -> str:
    """Removes or replaces characters unsafe for filenames."""
    # Replace slashes commonly found in repo names
    name = name.replace("/", "-")
    # Remove other potentially problematic characters (add more as needed)
    name = re.sub(r'[<>:"\\|?*]', '', name)
    return name

@app.command()
def generate(
    repo: str = typer.Argument(
        ..., # Ellipsis means required
        help="Repository name in the format 'owner/repo'."
    ),
    since_tag: Optional[str] = typer.Option(
        None,
        "--since-tag",
        help="Generate changelog for commits since this tag.",
        show_default=False,
    ),
    from_tag: Optional[str] = typer.Option(
        None,
        "--from-tag",
        help="Start tag for generating the changelog range (requires --to-tag).",
        show_default=False,
    ),
    to_tag: Optional[str] = typer.Option(
        None,
        "--to-tag",
        help="End tag for generating the changelog range (requires --from-tag).",
        show_default=False,
    ),
    output: Optional[str] = typer.Option(
        None,
        "-o",
        "--output",
        help="Path to the output file (e.g., changelog.md). If omitted, a default filename is generated based on repo and tags.",
        show_default=False, # Show default behavior in help text explicitly
    ),
    branch: Optional[str] = typer.Option(
        None,
        "-b",
        "--branch",
        help="Specify a branch/commit to compare against if --since-tag or no range is given (defaults to repository's default branch).",
        show_default=False,
    ),
    token: Optional[str] = typer.Option(
        lambda: os.environ.get("GITHUB_TOKEN"), # Read from env var by default
        "--token",
        help="GitHub Personal Access Token (PAT). Reads from GITHUB_TOKEN env var if not set.",
        show_default="Reads from GITHUB_TOKEN env var",
    ),
):
    """
    Generates a changelog for the specified GitHub repository and commit range.

    By default, the output is saved to a file named using the repository and tag range
    (e.g., owner-repo_since_v1.0.0.md or owner-repo_v1.0.0_to_v1.1.0.md).
    """
    # Basic validation for tag range options
    tag_options_count = sum(1 for opt in [since_tag, from_tag] if opt is not None) # Count how many tag modes are used

    if from_tag and not to_tag:
        print("Error: Using --from-tag requires --to-tag.")
        raise typer.Exit(code=1)
    if to_tag and not from_tag:
        print("Error: Using --to-tag requires --from-tag.")
        raise typer.Exit(code=1)
    if tag_options_count > 1 :
         print("Error: Please use only one of --since-tag or (--from-tag and --to-tag).")
         raise typer.Exit(code=1)
    if not since_tag and not from_tag:
         print("Error: You must specify a range using --since-tag or --from-tag/--to-tag.")
         raise typer.Exit(code=1)


    if not token:
         print("Warning: No GitHub token provided via --token or GITHUB_TOKEN env var.")
         print("Public repos might work, but you may hit rate limits quickly.")


    tag_range_tuple = (from_tag, to_tag) if from_tag and to_tag else None

    # Determine the output filename if no specific output file is given
    output_filename = output # Use provided filename if exists
    if output_filename is None:
        sanitized_repo = sanitize_filename(repo)
        if since_tag:
            sanitized_tag = sanitize_filename(since_tag)
            output_filename = f"{sanitized_repo}_since_{sanitized_tag}.md"
        elif tag_range_tuple:
            sanitized_from = sanitize_filename(tag_range_tuple[0])
            sanitized_to = sanitize_filename(tag_range_tuple[1])
            output_filename = f"{sanitized_repo}_{sanitized_from}_to_{sanitized_to}.md"
        else:
             # This case should theoretically not be reached due to earlier validation
             print("Error: Could not determine tag range for default filename.", file=sys.stderr)
             raise typer.Exit(code=1)

    try:
        # Call the main processing function from processor.py
        changelog_content = process_repository(
            repo=repo,
            token=token,
            since_tag=since_tag,
            tag_range=tag_range_tuple,
            target_branch=branch,
        )

        if changelog_content:
            # Always write to the output file
            try:
                with open(output_filename, "w") as f:
                    f.write(changelog_content)
                print(f"Changelog successfully written to {output_filename}")
            except IOError as e:
                print(f"Error writing to output file {output_filename}: {e}", file=sys.stderr)
                raise typer.Exit(code=1)
        else:
            print("Could not generate changelog content.")
            # Consider exiting with error? Depends if None means error or no changes found

    except Exception as e:
        # Catch potential exceptions from the processor (e.g., API errors)
        print(f"\nAn error occurred during processing: {e}", file=sys.stderr)
        # Consider adding more specific error handling based on processor exceptions
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
