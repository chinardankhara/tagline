# AI Changelog Generator

This project is an AI-powered tool designed to automatically generate changelogs for software projects hosted on GitHub. It aims to simplify the process for developers by leveraging Large Language Models (LLMs) to summarize commit histories between specified tags or since a specific tag.

This project was developed as part of the Greptile Software Engineer interview process.

## Project Goal

The core challenge this tool addresses is the manual effort involved in:
1.  Reviewing commit histories over days or weeks.
2.  Summarizing relevant changes concisely for end-users (often other developers).

The goal is to provide:
1.  A **developer-facing tool** (this CLI application) to quickly generate changelogs.
2.  A simple **public-facing website** (Future Work) to display these changelogs.

<details>
<summary><strong>🔧 Technical Deep Dive</strong> (Click to Expand)</summary>

---

### Highlights / Features

*   **AI-Powered Summarization:** Uses Google's Gemini models to analyze commit messages and generate human-readable changelog entries.
*   **GitHub Integration:** Fetches commit data, tag information, and file changes directly from GitHub repositories using the GitHub API.
*   **Flexible Range Selection:** Generate changelogs based on commit ranges between two tags (`--from-tag`, `--to-tag`) or since a specific tag (`--since-tag`).
*   **Customizable Prompts:** Leverages detailed system and user prompts stored in external `.md` files (`src/changelog_generator/templates/`) for fine-tuning the LLM's output style and content. Inspired by best practices (e.g., Stripe's changelogs).
*   **Command-Line Interface:** Simple and intuitive CLI built with Typer for ease of use by developers.
*   **Automatic Output File Naming:** Generates a sensible default output filename based on the repository and tag range, reducing command verbosity.

### Tech Stack & Design Decisions

*   **Language:** Python 3.10+
    *   *Why:* Excellent ecosystem for interacting with APIs, data processing, and AI libraries. Widely used and understood.
*   **CLI Framework:** Typer
    *   *Why:* Modern, easy-to-use library for building CLIs with automatic help generation, type hints, and minimal boilerplate. Improves developer experience.
*   **LLM:** Google Gemini (via `google-generativeai`)
    *   *Why:* Powerful and accessible LLM API. Experimented with Flash (for speed/cost) and Pro (for quality), settling on Pro with refined prompts for better structure and technical detail suitable for changelogs. Prompt engineering was key to achieving desired output quality and format.
*   **API Interaction:** Direct `requests` library usage within `GitHubClient`.
    *   *Why:* Sufficient for the specific GitHub API endpoints needed. Focused on clear methods for fetching tags, commits, and comparisons, including basic error handling (rate limits, 404s).
*   **Configuration:** `.env` file for API Keys (`dotenv` library).
    *   *Why:* Standard practice for managing sensitive credentials securely without hardcoding them. The CLI also allows overriding via `--token`.
*   **Modular Structure:** Code is organized into distinct modules:
    *   `cli.py`: Handles user interaction and command-line arguments.
    *   `processor.py`: Orchestrates the workflow (fetches data, calls LLM, formats output).
    *   `github_client.py`: Encapsulates all GitHub API communication.
    *   `llm_handler.py`: Manages interaction with the Gemini API, including prompt loading and formatting.
    *   `templates/`: Stores LLM prompts separately for easy modification.
    *   *Why:* Improves maintainability, testability, and separation of concerns.
*   **Prompt Engineering:** Stored prompts in markdown files and iterated significantly based on output quality and examples like Stripe's changelog format. This allows non-code changes to influence the output style.
*   **Output Handling:** Default to writing to a generated file, removing the need for an `-o` flag in the common case, simplifying the command for developers.

---
</details>

<details>
<summary><strong>🚀 Setup & Usage Guide</strong> (Click to Expand)</summary>

---

### Getting Started

#### Prerequisites

*   Python 3.10 or higher
*   Git
*   GitHub Personal Access Token (PAT) with `repo` scope (or `public_repo` for public repositories only). A classic token is even better.
*   Google AI Gemini API Key.

#### Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd llm-changelog
    ```

2.  **Create and activate a virtual environment (Recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

#### Configuration

1.  Create a `.env` file in the project root directory (`llm-changelog/`).
2.  Add your API keys to the `.env` file:
    ```dotenv
    GITHUB_TOKEN=ghp_YourGitHubTokenHere
    GEMINI_API_KEY=YourGeminiAPIKeyHere
    # Optional: Specify a different Gemini model
    # MODEL=gemini-1.5-pro-latest
    ```
    *Alternatively, you can pass the GitHub token via the `--token` flag.*

### 💻 Usage (CLI Tool)

Run the tool from the project's root directory using `python3 -m src.changelog_generator.cli`.

**Examples:**

1.  **Generate changelog since a specific tag (writes to default file):**
    ```bash
    python3 -m src.changelog_generator.cli owner/repo --since-tag v1.0.0
    # Example output file: owner-repo_since_v1.0.0.md
    ```

2.  **Generate changelog between two tags (writes to default file):**
    ```bash
    python3 -m src.changelog_generator.cli mendableai/firecrawl --from-tag v1.6.0 --to-tag v1.7.0
    # Example output file: mendableai-firecrawl_v1.6.0_to_v1.7.0.md
    ```

3.  **Specify a custom output file:**
    ```bash
    python3 -m src.changelog_generator.cli owner/repo --since-tag v1.1.0 -o my-changelog.md
    ```

4.  **Use a specific branch as the endpoint (instead of default branch) when using `--since-tag`:**
    ```bash
    python3 -m src.changelog_generator.cli owner/repo --since-tag v1.2.0 -b develop
    ```

5.  **Get help:**
    ```bash
    python3 -m src.changelog_generator.cli --help
    python3 -m src.changelog_generator.cli generate --help
    ```

---
</details>

## 🌐 Public-Facing Website

The second part of the project requirement is to create a simple public-facing website to display the generated changelogs. This is **Future Work** and not yet implemented.

## 🤝 Contributing

Contributions are welcome! Please feel free to open an issue or submit a pull request.

## 📜 License

(Placeholder: Add your chosen license, e.g., MIT License)
