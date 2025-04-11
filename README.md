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

## 🌐 Public-Facing Website

The project includes a simple, static website built with [MkDocs](https://www.mkdocs.org/) and the [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) theme to display the generated changelogs. It is deployed automatically via GitHub Actions to GitHub Pages.

*   **Live Demo Site:** [https://chinardankhara.github.io/llm-changelog-website/](https://chinardankhara.github.io/llm-changelog-website/)
*   **How it works:**
    1.  The `tagline` deployment workflow generates a changelog as a Markdown (`.md`) file.
    2.  This `.md` file is committed to the `changelogs/` directory in the separate website repository (e.g., `llm-changelog-website`).
    3.  A GitHub Actions workflow within the *website repository* is triggered by this commit.
    4.  The website workflow uses MkDocs to build the static HTML site from the Markdown files.
    5.  The built HTML site is deployed to the `gh-pages` branch.
    6.  The `index.html` on the live site uses JavaScript (`script.js`) to fetch the list of `.html` files from the `changelogs/` directory on the `gh-pages` branch via the GitHub API and dynamically displays links to them.

*   **Setting up your Website Repository Fork:**
    If you fork the companion `llm-changelog-website` repository (or set up your own), you need to configure it:
    1.  **Ensure the Repository is Public:** The `script.js` uses the public GitHub API to list changelogs. For this to work without authentication, your website repository **must be public**.
    2.  **Enable GitHub Pages:** Go to your website repository's `Settings` > `Pages`. Under "Build and deployment", select `Deploy from a branch` as the source, and choose the `gh-pages` branch with the `/ (root)` folder. Save the changes.
    3.  **Add `GITHUB_TOKEN` Secret:** Add your `GITHUB_TOKEN` (the same PAT used in the `tagline` repo secrets) as an Actions secret named `GITHUB_TOKEN` in the website repository's settings (`Settings` > `Secrets and variables` > `Actions`). This is often **not required** for a standard MkDocs deployment.

<details>
<summary><strong>🔧 Technical Deep Dive</strong></summary>

---

### Highlights / Features

*   **AI-Powered Summarization:** Uses Google's Gemini models to analyze commit messages and generate human-readable changelog entries.
*   **GitHub Integration:** Fetches commit data, tag information, and file changes directly from GitHub repositories using the GitHub API.
*   **Flexible Range Selection:** Generate changelogs based on commit ranges between two tags (`--from-tag`, `--to-tag`) or since a specific tag (`--since-tag`).
*   **Command-Line Interface:** Simple and intuitive CLI built with Typer for ease of use by developers.
*   **Automatic Output File Naming:** Generates a sensible default output filename based on the repository and tag range, reducing command verbosity.
*   **Prompt Engineering:** Stored prompts in markdown files and iterated significantly based on output quality and examples like Stripe's changelog format. This allows non-code changes to influence the output style.
*   **Website:** MkDocs (with Material theme), basic HTML/CSS/JavaScript, GitHub Pages.
    *   *Why:* MkDocs is excellent for generating static sites from Markdown, integrating well with the changelog format. GitHub Pages provides free and simple hosting. The custom HTML/JS allows for dynamic listing of changelogs without complex backend logic, keeping dependencies minimal and build times fast (~10s).

### Tech Stack & Design Decisions

*   **Language:** Python 3.10+
    *   *Why:* It has the best support in the AI tooling world. And it is the language I am most comfortable working in. 
*   **CLI Framework:** Typer
    *   *Why:* Modern, easy-to-use library for building CLIs with automatic help generation, type hints, and minimal boilerplate. Deverloper Experience is key for a dev tools company and typer interfaces look better and contain more features than inbuilt argparse. 
*   **LLM:** Google Gemini
    *   *Why:* Powerful and accessible LLM API. Experimented with Flash (for speed/cost) and Pro (for quality), settling on Pro with refined prompts for better structure and technical detail suitable for changelogs. Changelogs have a lower token burn compared to PR review and are seen by more people. This is why using frontier models makes sense. In my experience, Gemini models are currently the king in coding (even beyond Sonnet) and offer the best latency for their size. 
*   **Modular Structure:** Code is organized into distinct modules:
    *   `cli.py`: Handles user interaction and command-line arguments.
    *   `processor.py`: Orchestrates the workflow (fetches data, calls LLM, formats output).
    *   `github_client.py`: Encapsulates all GitHub API communication.
    *   `llm_handler.py`: Manages interaction with the Gemini API, including prompt loading and formatting.
    *   `templates/`: Stores LLM prompts separately for easy modification.
    *   *Why:* Improves maintainability, testability, and separation of concerns.

---
</details>

<details>
<summary><strong>🚀 Setup & Usage Guide</strong></summary>

---

### Getting Started

#### Prerequisites

*   Python 3.10 or higher
*   Git
*   GitHub Personal Access Token (PAT) with `repo` scope. A classic token is even better.
*   Google AI Gemini API Key.

#### Installation

1.  **Fork and Clone the repository:**
    *   First, fork this repository on GitHub.
    *   Then, clone your fork to your local machine:
    ```bash
    git clone https://github.com/YOUR_USERNAME/tagline.git # Replace YOUR_USERNAME
    cd tagline
    ```

2.  **Install `uv` (a fast Python package installer):** (because uv is awesome and the answer to python package management turf wars)
    ```bash
    pip install uv
    ```

3.  **Create and activate a virtual environment using `uv`:**
    ```bash
    uv venv
    source .venv/bin/activate # On Windows use `.venv\Scripts\activate`
    ```

4.  **Install dependencies using `uv`:**
    ```bash
    uv pip install -r requirements.txt
    ```

5.  **Install the `tagline` package locally:** (Requires `pyproject.toml` to be set up)
    ```bash
    uv pip install -e .
    ```

#### Configuration

1.  Create a `.env` file in the project root directory (`tagline/`).
2.  Add your API keys and GitHub details to the `.env` file:
    ```
    GITHUB_TOKEN=YourGithubTokenHere # Required for deployment and private repos
    GEMINI_API_KEY=YourGeminiAPIKeyHere # Required for AI generation
    ACTION_REPO_OWNER=YourGitHubUsername # Your GitHub username

    # Optional: In `llm_handler.py`, you can change the model constant to change to a Google model of your choice
    MODEL=gemini-1.5-flash-latest
    ```
    *Alternatively, you can pass the GitHub token via the `--token` flag when running the CLI.*

#### Configuring GitHub Actions Secrets (for Deployment)

If you intend to use the deployment feature (running `tagline` without `--local`), the GitHub Actions workflow will run in *your fork* of the `tagline` repository. This workflow requires several secrets to function correctly. These are configured on GitHub, **not** in your local `.env` file.

1.  Go to your forked `tagline` repository on GitHub.
2.  Navigate to `Settings` > `Secrets and variables` > `Actions`.
3.  Click `New repository secret` and add the following secrets:
    *   `GITHUB_TOKEN`: Your GitHub Personal Access Token (PAT) with `repo` scope (or `public_repo` if only targeting public repos). This is used by the workflow internally to fetch commit data from the *target* repository (the one you specify in the `tagline` command, e.g., `owner/repo`).
    *   `GEMINI_API_KEY`: Your Google AI Gemini API key. This is used by the workflow internally to generate the changelog content using the LLM.
    *   `WEBSITE_DEPLOY_TOKEN`: A *separate* GitHub PAT that has **write permissions** to the source branch (e.g., `main`) of the repository where your MkDocs website source files are hosted (e.g., your fork of `llm-changelog-website`). This specific token is used by the `tagline` workflow to commit the generated **Markdown changelog file** *to* the website source repository. This commit typically triggers another workflow *within the website repository* to build and deploy the site using MkDocs.

**Important:** Without these secrets configured in your fork's Actions settings, the deployment workflow triggered by the CLI will fail.

### Usage (CLI Tool)

Once installed, you can run the tool directly using the `tagline` command.

**Examples:**

1.  **Generate changelog between two tags (triggers deployment by default):**
    ```bash
    tagline mendableai/firecrawl -f v1.6.0 -t v1.7.0
    # Triggers deployment workflow, auto-generate filename from tags
    ```

2.  **Generate changelog locally with AI-suggested filename:**
    ```bash
    tagline owner/repo -f v1.0.0 -t v1.1.0 --local
    # Example output file saved in ./changelogs/: owner-repo_v1.0.0_to_v1.1.0_ai_suggested.md (or similar)
    ```

3.  **Generate changelog locally with a specific output file:**
    ```bash
    tagline owner/repo -f v1.1.0 -t v1.2.0 --local -o my-changelog.md
    ```

4.  **Get help:**
    ```bash
    tagline --help
    ```

---
</details>

**Note**: It takes a few minutes after running CLI to update the website due to LLM and yaml pipelines needing time. 