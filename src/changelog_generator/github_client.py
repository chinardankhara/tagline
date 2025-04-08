import requests
from typing import List, Dict, Any, Optional, Tuple

class GitHubClient:
    """
    A client for interacting with the GitHub REST API.
    """
    BASE_URL = "https://api.github.com"

    def __init__(self, repo: str, token: Optional[str]):
        """
        Initializes the GitHub Client.

        Args:
            repo: The repository name in 'owner/repo' format.
            token: A GitHub Personal Access Token (PAT) for authentication.
        """
        if '/' not in repo or len(repo.split('/')) != 2:
            raise ValueError("Invalid repository format. Expected 'owner/repo'.")
        self.owner, self.repo_name = repo.split('/')
        self.token = token
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Makes a request to the GitHub API and handles basic errors.

        Args:
            method: HTTP method (e.g., 'GET', 'POST').
            endpoint: API endpoint path (e.g., f'/repos/{self.owner}/{self.repo_name}/tags').
            **kwargs: Additional arguments passed to requests.request.

        Returns:
            The requests.Response object.

        Raises:
            requests.exceptions.RequestException: For connection errors or timeouts.
            requests.exceptions.HTTPError: For HTTP errors (4xx, 5xx).
        """
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
            return response
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e.response.status_code} for URL {url}")
            # Provide more specific feedback
            if e.response.status_code == 401:
                print("Error: Unauthorized. Check your GitHub token (permissions?).")
            elif e.response.status_code == 403:
                print("Error: Forbidden. Check token permissions or rate limits.")
                if 'rate limit exceeded' in e.response.text.lower():
                     print("Rate limit likely exceeded. Authenticate with a token or wait.")
            elif e.response.status_code == 404:
                print(f"Error: Not Found. Check repository 'owner/repo' name: {self.owner}/{self.repo_name}")
            else:
                print(f"Response body: {e.response.text}")
            raise # Re-raise the exception after printing info
        except requests.exceptions.RequestException as e:
            print(f"Network Error making request to {url}: {e}")
            raise

    def get_tags(self) -> List[Dict[str, Any]]:
        """
        Fetches all tags for the repository.

        Returns:
            A list of tag objects, each containing 'name' and 'commit' {'sha': ...}.
            Returns an empty list if the request fails or no tags are found.
        Raises:
            requests.exceptions.RequestException: For network or HTTP errors during fetch.
        """
        endpoint = f"/repos/{self.owner}/{self.repo_name}/tags"
        tags = []
        params = {'per_page': 100}

        while endpoint:
            try:
                response = self._make_request("GET", endpoint, params=params)
                page_tags = response.json()
                if not page_tags:
                    break
                tags.extend(page_tags)

                if 'next' in response.links:
                    next_url = response.links['next']['url']
                    if next_url.startswith(self.BASE_URL):
                        endpoint = next_url[len(self.BASE_URL):]
                    else:
                         print(f"Warning: Unexpected next page URL format: {next_url}")
                         endpoint = None
                    params = None
                else:
                    endpoint = None

            except (requests.exceptions.RequestException, ValueError) as e:
                # Removed the print here as _make_request already prints details
                # Let the exception propagate up
                raise e # <<< Re-raise the exception

        print(f"Fetched {len(tags)} tags for {self.owner}/{self.repo_name}")
        return tags

    def compare_commits(self, base: str, head: str) -> Optional[Dict[str, Any]]:
        """
        Compares two commits (can be tags, branch names, or SHAs).

        Args:
            base: The base commit/tag/branch.
            head: The head commit/tag/branch.

        Returns:
            A dictionary containing comparison details, including 'commits' list
            and 'files' list (with 'patch' data for diffs).
            Returns None if the request fails.
        Raises:
            requests.exceptions.RequestException: For network or HTTP errors during comparison.
        """
        endpoint = f"/repos/{self.owner}/{self.repo_name}/compare/{base}...{head}"
        try:
            response = self._make_request("GET", endpoint, timeout=60)
            return response.json()
        except (requests.exceptions.RequestException, ValueError) as e:
             # Removed the print here as _make_request already prints details
             raise e # <<< Re-raise the exception

    def get_commit(self, ref: str) -> Optional[Dict[str, Any]]:
        """
        Fetches details for a specific commit, branch, or tag.

        Args:
            ref: The commit SHA, branch name, or tag name.

        Returns:
            A dictionary containing the commit details, including files and patches.
            Returns None if the request fails.
        Raises:
            requests.exceptions.RequestException: For network or HTTP errors during fetch.
        """
        endpoint = f"/repos/{self.owner}/{self.repo_name}/commits/{ref}"
        try:
            response = self._make_request("GET", endpoint, timeout=30)
            return response.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            # Removed the print here as _make_request already prints details
            raise e # <<< Re-raise the exception

    def get_default_branch(self) -> Optional[str]:
        """
        Fetches the default branch name for the repository.

        Returns:
            The name of the default branch (e.g., 'main', 'master') or None on error.
        Raises:
            requests.exceptions.RequestException: For network or HTTP errors during fetch.
        """
        endpoint = f"/repos/{self.owner}/{self.repo_name}"
        try:
            response = self._make_request("GET", endpoint, timeout=10)
            repo_info = response.json()
            # Handle case where default_branch key might be missing in rare cases
            if "default_branch" not in repo_info:
                 print(f"Warning: 'default_branch' key not found in repository info for {self.owner}/{self.repo_name}")
                 return None # Or raise a specific error? Returning None seems safer for now.
            return repo_info.get("default_branch")
        except (requests.exceptions.RequestException, ValueError, KeyError) as e: # Keep KeyError here for safety
            # Removed the print here as _make_request already prints details for RequestException
            if not isinstance(e, requests.exceptions.RequestException):
                 # Print details for other exceptions like KeyError or Value Error from json parsing
                 print(f"Error fetching repository info or default branch: {e}")
            raise e # <<< Re-raise the exception
