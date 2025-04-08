# tests/test_github_client.py

import pytest
from unittest.mock import MagicMock # Still use MagicMock for the response object
import requests # Import requests here for exception types

# Import the class we want to test
from src.changelog_generator.github_client import GitHubClient

# Define some constants for testing
TEST_REPO = "test-owner/test-repo"
TEST_TOKEN = "fake_token_123"

# Helper function to create a mock requests.Response object (can be outside class now)
def create_mock_response(status_code=200, json_data=None, headers=None, links=None):
    """Helper function to create a mock requests.Response object."""
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = status_code
    mock_resp.headers = headers if headers else {}
    mock_resp.links = links if links else {}

    # Mock the .json() method
    if json_data is not None:
        mock_resp.json.return_value = json_data
    else:
         # Make .json() raise ValueError if called without data, simulating requests behavior
         mock_resp.json.side_effect = ValueError("No JSON object could be decoded")

    # Configure raise_for_status
    if 400 <= status_code < 600:
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            f"{status_code} Client Error", response=mock_resp
        )
    else:
        mock_resp.raise_for_status.return_value = None

    return mock_resp

# --- Pytest Tests ---

def test_init_success():
    """Test successful initialization."""
    client = GitHubClient(repo=TEST_REPO, token=TEST_TOKEN)
    assert client.owner == "test-owner"
    assert client.repo_name == "test-repo"
    assert client.token == TEST_TOKEN
    assert "Authorization" in client.headers
    assert client.headers["Authorization"] == f"Bearer {TEST_TOKEN}"

def test_init_invalid_repo_format():
    """Test initialization with invalid repo format."""
    with pytest.raises(ValueError, match="Invalid repository format"):
        GitHubClient(repo="invalid-repo-format", token=TEST_TOKEN)
    with pytest.raises(ValueError, match="Invalid repository format"):
        GitHubClient(repo="owner/repo/extra", token=TEST_TOKEN)

def test_get_tags_success_single_page(mocker): # Use mocker fixture
    """Test fetching tags successfully (single page)."""
    mock_response = create_mock_response(
        status_code=200,
        json_data=[
            {"name": "v1.0", "commit": {"sha": "abc"}},
            {"name": "v1.1", "commit": {"sha": "def"}},
        ]
    )
    # Use mocker to patch 'requests.request'
    mock_request = mocker.patch('requests.request', return_value=mock_response)

    client = GitHubClient(repo=TEST_REPO, token=TEST_TOKEN)
    tags = client.get_tags()

    assert len(tags) == 2
    assert tags[0]["name"] == "v1.0"
    assert tags[1]["commit"]["sha"] == "def"
    # Check if the correct API call was made
    expected_url = f"{client.BASE_URL}/repos/{client.owner}/{client.repo_name}/tags"
    mock_request.assert_called_once_with(
        "GET",
        expected_url,
        headers=client.headers,
        params={'per_page': 100}
    )

def test_get_tags_success_multiple_pages(mocker):
    """Test fetching tags successfully across multiple pages."""
    # Response for first page
    page1_response = create_mock_response(
        status_code=200,
        json_data=[{"name": "v1.0", "commit": {"sha": "abc"}}],
        links={'next': {'url': f'{GitHubClient.BASE_URL}/repositories/123/tags?page=2'}}
    )
    # Response for second page
    page2_response = create_mock_response(
        status_code=200,
        json_data=[{"name": "v1.1", "commit": {"sha": "def"}}],
        links={} # No next link
    )

    # Configure the mock to return responses sequentially
    mock_request = mocker.patch('requests.request', side_effect=[page1_response, page2_response])

    client = GitHubClient(repo=TEST_REPO, token=TEST_TOKEN)
    tags = client.get_tags()

    assert len(tags) == 2
    assert tags[0]["name"] == "v1.0"
    assert tags[1]["name"] == "v1.1"
    assert mock_request.call_count == 2

    # Check call arguments (params are None for the second call)
    first_call_args = mock_request.call_args_list[0]
    second_call_args = mock_request.call_args_list[1]

    expected_url_page1 = f"{client.BASE_URL}/repos/{client.owner}/{client.repo_name}/tags"
    expected_url_page2 = f"{client.BASE_URL}/repositories/123/tags?page=2" # From links header

    assert first_call_args.args == ("GET", expected_url_page1)
    assert first_call_args.kwargs['params'] == {'per_page': 100}

    assert second_call_args.args == ("GET", expected_url_page2)
    assert second_call_args.kwargs['params'] is None # Params should be None for paginated calls

def test_compare_commits_success(mocker):
    """Test comparing commits successfully."""
    mock_response = create_mock_response(
        status_code=200,
        json_data={"commits": [{"sha": "sha1"}], "files": [{"filename": "f1", "patch": "diff1"}]}
    )
    mock_request = mocker.patch('requests.request', return_value=mock_response)

    client = GitHubClient(repo=TEST_REPO, token=TEST_TOKEN)
    base, head = "v1.0", "v1.1"
    comparison = client.compare_commits(base, head)

    assert comparison is not None
    assert comparison["commits"][0]["sha"] == "sha1"
    assert comparison["files"][0]["patch"] == "diff1"
    expected_url = f"{client.BASE_URL}/repos/{client.owner}/{client.repo_name}/compare/{base}...{head}"
    mock_request.assert_called_once_with(
        "GET",
        expected_url,
        headers=client.headers,
        timeout=60
    )

def test_get_default_branch_success(mocker):
    """Test getting the default branch successfully."""
    mock_response = create_mock_response(
        status_code=200,
        json_data={"default_branch": "main"}
    )
    mock_request = mocker.patch('requests.request', return_value=mock_response)

    client = GitHubClient(repo=TEST_REPO, token=TEST_TOKEN)
    branch = client.get_default_branch()

    assert branch == "main"
    expected_url = f"{client.BASE_URL}/repos/{client.owner}/{client.repo_name}"
    mock_request.assert_called_once_with(
        "GET",
        expected_url,
        headers=client.headers,
        timeout=10
    )

def test_request_handles_404_error(mocker):
    """Test that a 404 error is handled correctly."""
    mock_response = create_mock_response(status_code=404, json_data={"message": "Not Found"})
    mocker.patch('requests.request', return_value=mock_response)

    client = GitHubClient(repo=TEST_REPO, token=TEST_TOKEN)

    # Assert that the specific HTTPError is raised by _make_request
    with pytest.raises(requests.exceptions.HTTPError) as excinfo:
        client.get_tags() # Try calling any method that uses _make_request

    # Optionally check the status code on the raised exception
    assert excinfo.value.response.status_code == 404

# --- TODO: Add more tests ---
# - get_tags with API errors (401, 403, etc.) -> Check print messages too?
# - compare_commits with API errors
# - get_commit method (success and errors)
# - get_default_branch with API errors
# - Handling network errors (requests.exceptions.RequestException) -> Use side_effect=NetworkError(...)