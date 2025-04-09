# Generate a Changelog

Create a modern, visually appealing changelog for repository '{repo}' comparing '{from_ref}' to '{to_ref}'.

## Input Data
- **Commit History**: {commit_details}
- **Files Changed**: {file_changes}

## Styling Guidelines

1. Create a clean, modern changelog that:
   - Starts with a **bold headline** including version numbers and date
   - Includes a brief 2-3 sentence executive summary highlighting major changes
   - Uses emoji icons to visually distinguish categories (📈 New, 🔧 Improved, 🐛 Fixed, etc.)
   - Organizes entries with consistent bullet formatting
   - Places issue/PR references at the end of entries (#123)
   - Makes breaking changes highly visible with ⚠️ warning symbols

2. For each entry:
   - Focus on user-facing impact and value
   - Use imperative, present tense verbs (Add, Fix, Improve)
   - Keep descriptions concise but informative
   - Include "why" for significant changes

3. Organize content for quick scanning:
   - Most important changes at the top of each section
   - Group related changes together
   - Omit trivial changes (typo fixes, minor internal refactoring)
   - Keep similar formatting for all entries

4. Include these sections (as relevant):
   - ⚠️ Breaking Changes
   - 📈 New Features
   - 🔧 Improvements
   - 🐛 Bug Fixes
   - 🚀 Performance
   - 🔒 Security
   - 📚 Documentation 