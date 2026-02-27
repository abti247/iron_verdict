# Project Overview

**Iron Verdict** - a web app for powerlifting competition judging.

The goal of the app is to provide an easy access to a tool for powerlifting judging.

## Project Structure
- Place all application implementation files (code, modules, components) under /src directory.
- Place all application documentation files under /docs directory.
- Place all test files and test-related code under /tests directory.

## GitHub
- Before committing any files, ask the user for confirmation if you're uncertain whether they should be committed, especially for generated files, logs, cache files, or system files.
- Never commit dependency directories, build artifacts, .env files, IDE configs, logs, or cache files; when in doubt about any file, ask before committing.

## Implementation
- Use worktrees to implement new features or fixes
- Create worktrees in the project folder under .worktrees
- If you created a plan (general or implementation plan) for the feature/fix add this to the /docs directory on the worktree so it can later be merged with the PR.

## Changelog
- After any implementation that introduces, fixes, changes, or removes behavior, add a precise one-liner to the `[Unreleased]` section of `CHANGELOG.md` under the appropriate subsection (`Added`, `Fixed`, `Changed`, or `Removed`).
- One-liner style: short, specific, no trailing period — match the tone of existing entries.

## Security
- When adding or modifying features, always evaluate whether the change could introduce XSS, injection, or other OWASP Top 10 vulnerabilities.
- Flag any change that would render unsanitized user input as HTML.

## Plan Mode
- Make the plan extremely concise. Sacrifice grammar for the sake of concision.
- At the end of each plan, give me a list of unresolved questions to answer, if any.