from typing import Dict, List, Optional
import os
from google import genai
# from google.generativeai import types # <- Remove this or comment out
from dotenv import load_dotenv

load_dotenv()

class LLMHandler:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the LLM handler with Google's Gemini API.
        
        Args:
            api_key: Optional Google API key. If not provided, will look for GEMINI_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No API key provided. Set GEMINI_API_KEY environment variable or pass key to constructor."
            )
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.0-flash"  # Using the fast model for better latency

    def generate_changelog(
        self,
        commits: List[Dict],
        files_changed: List[Dict],
        from_ref: str,
        to_ref: str,
        repo: str,
    ) -> str:
        """Generate a changelog from the given commits and file changes.
        
        Args:
            commits: List of commit objects from GitHub API
            files_changed: List of file changes from GitHub API
            from_ref: Starting reference (tag/commit)
            to_ref: Ending reference (tag/commit)
            repo: Repository name (owner/repo)
            
        Returns:
            A formatted changelog string
        """
        # Construct the prompt with clear instructions
        system_prompt = """You are a skilled technical writer specializing in changelog generation.
        Your task is to create a clear, well-organized changelog from Git commit history.
        Follow these guidelines:
        1. Group related changes into categories (e.g., Features, Bug Fixes, Documentation, etc.)
        2. Use clear, concise language
        3. Maintain a professional tone
        4. Highlight breaking changes or important updates
        5. Include relevant PR/Issue numbers if mentioned in commits
        6. Summarize technical changes in user-friendly terms
        """

        # Format the commit data for the model
        commit_details = "\n".join([
            f"- {commit.get('sha', '')[:7]}: {commit.get('commit', {}).get('message', '').strip()}"
            for commit in commits
        ])

        file_changes = "\n".join([
            f"- {file.get('filename', '')}: {file.get('status', '')} "
            f"({file.get('additions', 0)} additions, {file.get('deletions', 0)} deletions)"
            for file in files_changed
        ])

        user_prompt = f"""Generate a changelog for {repo} from {from_ref} to {to_ref}.

Commit History:
{commit_details}

Files Changed:
{file_changes}

Format the changelog with the following sections:
- Summary (brief overview of major changes)
- Breaking Changes (if any)
- Features
- Bug Fixes
- Performance Improvements
- Documentation
- Other Changes

Focus on user-facing changes and their impact."""

        # Define generation config as a dictionary
        generation_config = {
            "temperature": 0.2,
            "max_output_tokens": 1000,
        }
        # Define safety settings if needed (optional, but good practice)
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        try:
            # Call generate_content using the generation_config dictionary
            response = self.client.models.generate_content(
                model=self.model,
                # Pass config dictionary to generation_config
                generation_config=generation_config,
                # Pass system instruction separately if supported or combine into contents
                system_instruction=system_prompt, # Keep this if it works, otherwise integrate into user_prompt
                contents=user_prompt,
                safety_settings=safety_settings # Add safety settings
            )

            # Handle potential lack of text even without error
            if not response.candidates or not response.candidates[0].content.parts:
                 # Check if the response was blocked due to safety settings
                 if response.prompt_feedback.block_reason:
                     raise ValueError(f"LLM Response Blocked: {response.prompt_feedback.block_reason}")
                 else:
                     raise ValueError("Empty response from LLM (No candidates or parts)")

            # Extract text safely
            generated_text = "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text'))
            if not generated_text:
                 raise ValueError("Empty text content in LLM response parts")


            return generated_text # Use the safely extracted text

        except Exception as e:
            # Log the error and return a formatted error message
            print(f"LLM API Error: {e}") # Print the specific error
            error_msg = f"""Failed to generate changelog due to an error: {str(e)}

Raw commit data has been included below:

# Commits between {from_ref} and {to_ref}

{commit_details}

# Files Changed

{file_changes}
"""
            return error_msg

    def format_commit_message(self, message: str) -> str:
        """Clean and format a single commit message.
        
        Args:
            message: Raw commit message
            
        Returns:
            Formatted commit message
        """
        generation_config = {
            "temperature": 0.1,
            "max_output_tokens": 100,
        }
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            # ... other categories ...
        ]
        system_instruction_formatter = """You are a commit message formatter.
                    Make the message clear and concise while preserving its meaning.
                    Remove unnecessary details but keep PR numbers and issue references."""

        try:
            response = self.client.models.generate_content(
                model=self.model,
                generation_config=generation_config,
                system_instruction=system_instruction_formatter,
                contents=f"Format this commit message clearly and concisely:\n{message}",
                safety_settings=safety_settings
            )
            # Safe text extraction as above
            if not response.candidates or not response.candidates[0].content.parts:
                 if response.prompt_feedback.block_reason:
                     print(f"LLM format_commit_message Blocked: {response.prompt_feedback.block_reason}")
                 return message.strip() # Fallback to original on empty response/block
            
            formatted_text = "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text')).strip()
            return formatted_text if formatted_text else message.strip() # Fallback if text is empty

        except Exception as e:
            print(f"LLM format_commit_message Error: {e}")
            # On error, return the original message
            return message.strip()
