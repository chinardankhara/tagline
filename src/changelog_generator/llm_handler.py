from typing import Dict, List, Optional
import os
import google.generativeai as genai # Use the main import
from dotenv import load_dotenv

load_dotenv()

class LLMHandler:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the LLM handler with Google's Gemini API."""
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("No API key provided. Set GEMINI_API_KEY env var or pass key.")

        # Configure the SDK
        genai.configure(api_key=self.api_key)

        # --- Model for Changelog Generation ---
        changelog_model_name = "gemini-2.0-flash"
        changelog_system_prompt = """You are a skilled technical writer specializing in changelog generation.
Your task is to create a clear, concise, and well-organized changelog from Git commit history.
Focus on user-facing changes and their impact. Group related changes into logical categories (e.g., Features, Bug Fixes, Performance, Documentation, Refactoring, Other).
Include relevant PR/Issue numbers if mentioned in commits. Highlight any Breaking Changes prominently."""

        changelog_generation_config = {
            "temperature": 0.2,
            "max_output_tokens": 8192, # Allow more tokens for full changelog
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
        formatter_model_name = "gemini-2.0-flash" # Flash is suitable here
        formatter_system_prompt = """You are an expert commit message formatter.
Make the provided message clear, concise, and suitable for a changelog entry, while preserving its core meaning.
Remove conversational filler or unnecessary details, but *keep* any mentioned Pull Request (e.g., #123) or Issue numbers."""

        formatter_generation_config = {
            "temperature": 0.1,
            "max_output_tokens": 150, # Shorter output needed
        }
        # Safety settings can often be reused
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
                if response.prompt_feedback.block_reason:
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
        # Format the commit data for the prompt
        commit_details = "\n".join([
            # Maybe format individual messages first for clarity? Optional.
            # f"- {commit.get('sha', '')[:7]}: {self.format_commit_message(commit.get('commit', {}).get('message', ''))}"
            f"- {commit.get('sha', '')[:7]}: {commit.get('commit', {}).get('message', '').strip()}"
            for commit in commits
        ])

        file_changes = "\n".join([
            f"- {file.get('filename', '')}: {file.get('status', '')} "
            f"({file.get('additions', 0)} additions, {file.get('deletions', 0)} deletions)"
            for file in files_changed
        ])

        # Construct the user prompt (system prompt is now set on the model)
        user_prompt = f"""Generate a changelog for repository '{repo}' comparing versions '{from_ref}' and '{to_ref}'.

Use the following commit history and file changes:

### Commit History:
{commit_details}

### Files Changed Summary:
{file_changes}

### Instructions:
Create a changelog summarizing the key changes. Group related items logically (Features, Bug Fixes, etc.). Ensure BREAKING CHANGES are clearly marked if any are apparent."""

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
        if not message: # Handle empty messages
            return ""

        # Construct the prompt for the formatter model
        user_prompt = f"Format this commit message clearly and concisely for a changelog:\n\n```\n{message}\n```"

        try:
             # Use the helper method with the dedicated formatter model
            return self._safe_generate_content(self.formatter_model, user_prompt)
        except Exception as e:
            # On error, return the original message (already printed error in helper)
            return message.strip() # Return original message on failure
