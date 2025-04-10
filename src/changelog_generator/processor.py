from typing import Optional, Tuple, List, Dict, Any
import requests # For exception types
import traceback # Add this import

from .github_client import GitHubClient
from .llm_handler import LLMHandler
# from .utils import some_utility_function # We might add utils later

def format_commit_data_for_llm(commits: List[Dict[str, Any]], files: List[Dict[str, Any]]) -> str:
    """
    Formats the collected commit messages and file diffs into a single string
    suitable for prompting an LLM.

    Args:
        commits: List of commit objects from the GitHub API compare endpoint.
        files: List of file objects from the GitHub API compare endpoint.

    Returns:
        A formatted string containing commit messages and diffs.
    """
    # Basic formatting - can be significantly improved later
    # Consider filtering commits (e.g., merge commits, specific patterns)
    # Consider summarizing diffs if they are too long

    prompt_content = "Relevant Commits:\n"
    if not commits:
        prompt_content += "- No individual commits found in range (perhaps a single merge commit?).\n"
    else:
        for commit in commits:
            sha_short = commit.get('sha', 'N/A')[:7]
            commit_details = commit.get('commit', {})
            message = commit_details.get('message', 'No commit message').strip()
            author_info = commit_details.get('author', {})
            author = author_info.get('name', 'Unknown Author')
            date = author_info.get('date', 'Unknown Date')
            prompt_content += f"- {sha_short} by {author} ({date}):\n"
            # Indent message lines
            message_lines = message.split('\n')
            for line in message_lines:
                 prompt_content += f"    {line}\n"
            prompt_content += "\n"

    prompt_content += "\nChanged Files Summary (Patches/Diffs):\n"
    if not files:
        prompt_content += "- No file changes detected in this range.\n"
    else:
        # Limit the number of files/diff length included in the prompt?
        MAX_FILES_IN_PROMPT = 50
        MAX_PATCH_LENGTH = 1000 # Characters per file patch
        included_files = 0
        for file_data in files:
            if included_files >= MAX_FILES_IN_PROMPT:
                 prompt_content += f"- ... (truncated {len(files) - included_files} more files)\n"
                 break

            filename = file_data.get('filename', 'Unknown file')
            status = file_data.get('status', 'unknown')
            patch = file_data.get('patch', '')

            prompt_content += f"- {filename} ({status})"
            if patch:
                # Simple truncation - better approach might involve summarizing diffs
                truncated_patch = patch[:MAX_PATCH_LENGTH]
                if len(patch) > MAX_PATCH_LENGTH:
                    truncated_patch += "\n... (diff truncated)"
                prompt_content += f"\n```diff\n{truncated_patch}\n```\n"
            else:
                prompt_content += " (No diff provided)\n"
            prompt_content += "\n"
            included_files += 1


    return prompt_content


def process_repository(
    repo: str,
    token: Optional[str],
    since_tag: Optional[str],
    tag_range: Optional[Tuple[str, str]],
    target_branch: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetches repository data, generates a changelog, and suggests a filename using LLM.

    Args:
        repo: Repository name ('owner/repo').
        token: GitHub PAT.
        since_tag: Generate changelog since this tag.
        tag_range: Tuple of (from_tag, to_tag).
        target_branch: Specific branch to compare against.

    Returns:
        A tuple containing (changelog_content, suggested_filename).
        Both can be None on failure.
    Raises:
        requests.exceptions.RequestException: If GitHub API call fails.
        Exception: For other unexpected errors.
    """
    print(f"Processing repository: {repo}")
    client = GitHubClient(repo=repo, token=token)

    base_ref = None
    head_ref = None

    try:
        if tag_range:
            base_ref = tag_range[0]
            head_ref = tag_range[1]
            print(f"Comparing tags: {base_ref}...{head_ref}")
        elif since_tag:
            base_ref = since_tag
            head_ref = target_branch or client.get_default_branch()
            if not head_ref:
                 print("Error: Could not determine the head reference (default branch or specified branch).")
                 return None, None # Return None for both
            print(f"Comparing since tag: {base_ref} up to {head_ref}")
        else:
            print("Error: No valid tag range specified.")
            return None, None # Return None for both

        print(f"Fetching comparison data between {base_ref} and {head_ref}...")
        comparison_data = client.compare_commits(base=base_ref, head=head_ref)

        if comparison_data is None:
            print(f"Failed to get comparison data for {base_ref}...{head_ref}.")
            return None, None # Return None for both

        commits = comparison_data.get('commits', [])
        files = comparison_data.get('files', [])
        total_commits = comparison_data.get('total_commits', len(commits))

        print(f"Found {total_commits} total commits and {len(files)} changed files in range.")
        if total_commits > len(commits):
            print(f"Warning: API returned details for only {len(commits)} commits (limit is 250).")

        # --- Call LLM Handler ---
        print("Generating changelog and suggesting filename with LLM...")
        llm = LLMHandler()  # Assumes GEMINI_API_KEY is set in env

        # Call LLMHandler which now returns a tuple
        changelog_content, suggested_filename = llm.generate_changelog(
            commits=commits,
            files_changed=files,
            from_ref=base_ref,
            to_ref=head_ref,
            repo=repo
        )

        # Optionally print the content (or a snippet) here for debugging
        if changelog_content:
            print(f"\n--- Generated Changelog Content (length: {len(changelog_content)}) ---")
        else:
             print("\n--- LLM did not return changelog content ---")
        if suggested_filename:
            print(f"--- Suggested Filename: {suggested_filename} ---")
        else:
            print("--- LLM did not suggest a filename ---")

        # Return the tuple received from LLMHandler
        return changelog_content, suggested_filename

    except requests.exceptions.RequestException as e:
         print(f"GitHub API Error during processing: {e}")
         raise # Re-raise to be caught by the CLI
    except Exception as e:
         print(f"An unexpected error occurred in processor: {type(e).__name__} - {e}")
         traceback.print_exc()
         raise # Re-raise to be caught by the CLI
