from typing import Dict, List, Optional
import os
import google.generativeai as genai
from dotenv import load_dotenv
import pathlib
import datetime

load_dotenv()

def load_template(filename: str) -> str:
    """Load a template from the templates directory."""
    template_dir = pathlib.Path(__file__).parent / "templates"
    template_path = template_dir / filename
    
    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")
    
    return template_path.read_text()

class LLMHandler:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the LLM handler with Google's Gemini API."""
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("No API key provided. Set GEMINI_API_KEY env var or pass key.")

        # Configure the SDK
        genai.configure(api_key=self.api_key)

        # Load system prompts from template files
        changelog_system_prompt = load_template("changelog_system_prompt.md")
        formatter_system_prompt = """You are an expert commit message formatter.
Make the provided message clear, concise, and suitable for a changelog entry, while preserving its core meaning.
Remove conversational filler or unnecessary details, but *keep* any mentioned Pull Request (e.g., #123) or Issue numbers."""

        # --- Model for Changelog Generation ---
        changelog_model_name = os.getenv("MODEL")  # Or "gemini-1.5-pro-latest" if needed
        changelog_generation_config = {
            "temperature": 0.2,
            "max_output_tokens": 8192,  # Allow more tokens for full changelog
        }
        changelog_safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        self.changelog_model = genai.GenerativeModel(
            model_name=changelog_model_name,
            generation_config=changelog_generation_config,
            system_instruction=changelog_system_prompt,
            safety_settings=changelog_safety_settings
        )
        print(f"Initialized changelog model: {changelog_model_name}")

        # --- Model for Commit Formatting ---
        formatter_model_name = os.getenv("MODEL")  # Flash is suitable here
        formatter_generation_config = {
            "temperature": 0.1,
            "max_output_tokens": 150,  # Shorter output needed
        }
        formatter_safety_settings = changelog_safety_settings

        self.formatter_model = genai.GenerativeModel(
            model_name=formatter_model_name,
            generation_config=formatter_generation_config,
            system_instruction=formatter_system_prompt,
            safety_settings=formatter_safety_settings
        )
        print(f"Initialized formatter model: {formatter_model_name}")

    def _safe_generate_content(self, model: genai.GenerativeModel, prompt: str) -> str:
        """Helper to call generate_content and handle response/errors safely."""
        try:
            response = model.generate_content(prompt)

            # Check for blocks or empty responses
            if not response.candidates:
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    block_reason_str = str(response.prompt_feedback.block_reason)
                    raise ValueError(f"LLM Response Blocked: {block_reason_str}")
                else:
                    # Check if parts exist but are empty (might indicate other issues)
                    try:
                        # Attempt to access text to see if it fails in a specific way
                        _ = response.text
                        raise ValueError("Empty response from LLM (No candidates returned, but no block reason)")
                    except Exception as inner_ex:
                        # Catch potential errors accessing .text if structure is unexpected
                        raise ValueError(f"Empty or invalid response structure from LLM. Inner error: {inner_ex}")

            # Extract text safely using response.text property
            generated_text = response.text.strip()
            if not generated_text:
                raise ValueError("Empty text content in LLM response")

            return generated_text

        except Exception as e:
            # Catch API errors, config errors, ValueErrors from checks above, etc.
            print(f"LLM API Error ({model.model_name}): {type(e).__name__} - {e}")
            # Re-raise the exception to be handled by the calling method's try-except block
            raise e

    def generate_changelog(
        self,
        commits: List[Dict],
        files_changed: List[Dict],
        from_ref: str,
        to_ref: str,
        repo: str,
    ) -> str:
        """Generate a changelog using the configured model."""
        # Format commits (optionally clean them first)
        cleaned_commits = []
        for commit in commits:
            sha_short = commit.get('sha', '')[:7]
            message = commit.get('commit', {}).get('message', '').strip()
            author = commit.get('commit', {}).get('author', {}).get('name', '')
            date = commit.get('commit', {}).get('author', {}).get('date', '')
            
            # Format the commit details with more information
            cleaned_commits.append(f"- {sha_short}: {message} (by {author} on {date})")
            
        commit_details = "\n".join(cleaned_commits)

        # Format file changes
        file_changes = "\n".join([
            f"- {file.get('filename', '')}: {file.get('status', '')} "
            f"({file.get('additions', 0)} additions, {file.get('deletions', 0)} deletions)"
            for file in files_changed
        ])

        # Get the current date for the changelog
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")

        # Load and format the user prompt template
        user_prompt_template = load_template("changelog_user_prompt.md")
        user_prompt = user_prompt_template.format(
            repo=repo,
            from_ref=from_ref,
            to_ref=to_ref,
            commit_details=commit_details,
            file_changes=file_changes,
            current_date=current_date
        )

        try:
            # Use the helper method with the dedicated changelog model
            return self._safe_generate_content(self.changelog_model, user_prompt)

        except Exception as e:
            # Format a fallback message including the raw data
            error_msg = f"""Failed to generate changelog due to an error: {str(e)}

Raw commit data has been included below:

# Commits between {from_ref} and {to_ref}

{commit_details}

# Files Changed

{file_changes}
"""
            return error_msg

    def format_commit_message(self, message: str) -> str:
        """Clean and format a single commit message using the configured formatter model."""
        if not message:  # Handle empty messages
            return ""

        # Construct the prompt for the formatter model
        user_prompt = f"Format this commit message clearly and concisely for a changelog:\n\n```\n{message}\n```"

        try:
            # Use the helper method with the dedicated formatter model
            return self._safe_generate_content(self.formatter_model, user_prompt)
        except Exception as e:
            # On error, return the original message (already printed error in helper)
            return message.strip()  # Return original message on failure
