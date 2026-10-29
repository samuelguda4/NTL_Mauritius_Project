# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.1.0] - 2026-10-29
### Added
- Showcase repository on `main`: bilingual README (EN/FR), methodology and quality documentation, citation file.
- Images and animations generated from the country's own data: night-lights timelapse, before/after wipe,
  shock animation, social preview, banner and one vignette per use case.
- Animated tour and screenshots of the dashboard (optional, Playwright).
- One-call publication now also pushes `main` and sets the repository description, homepage and topics.

### Changed
- Use cases 6 (industrial zones), 7 (summer tourism) and 8 (urbanisation signals) are part of the README, dashboard and AI agent.

### Security
- Notebooks are stripped of outputs and metadata; token-like strings are redacted before any push.

## [2.0.0]
### Added
- Seven use cases, bilingual dashboard on GitHub Pages and AI assistant (Groq, Gemini, Ollama).
