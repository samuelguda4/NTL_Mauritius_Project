# Contributing

Thank you for helping improve this project! Contributions in **English or French** are welcome.

## Ways to contribute
- **Report a bug** or a wrong figure: open an issue with the *Bug report* template (country, period, notebook
  section, what you expected, what you got).
- **Suggest a use case or a data source**: use the *Feature request* template.
- **Improve the code or docs**: open a pull request.

## Development workflow
1. Fork the repository and create a branch: `git checkout -b feature/my-change`.
2. Work in the notebook (`notebooks/`) or in the analysis packages (`src/`, `src_en/`). Language-neutral
   modules keep their user-facing strings in `{"fr": ..., "en": ...}` dictionaries: please update both.
3. Run the notebook end to end with `SYNTHETIC_TEST = True` (no Earth Engine needed) and check the dashboard
   locally: `python -m http.server -d dashboard 8000`.
4. Never commit outputs, caches, `.env` files, tokens or API keys. Clear notebook outputs before committing.
5. Open a pull request describing the change and how you tested it.

## Statistical standards
Changes to methods must document their assumptions, uncertainty and limits (see `docs/methodology.md`) and
keep the *experimental statistics* labelling of estimates derived from night-time lights.

## Code of conduct
Be respectful and constructive. Harassment or discrimination of any kind is not tolerated.
