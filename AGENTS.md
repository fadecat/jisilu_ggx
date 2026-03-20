# Repository Guidelines

## Project Structure & Module Organization
This repository is a small Python automation project with script-style entry points at the repo root. `main.py` fetches and formats the dividend report, `cb_main.py` handles convertible bond screening, and `irm_query.py` queries recent investor-relations Q&A for underlying stocks. Lightweight smoke-test scripts live beside them: `test_preview.py`, `test_cb_preview.py`, and `test_irm_preview.py`. CI is defined in `.github/workflows/daily_report.yml`.

## Build, Test, and Development Commands
Use Python 3.12 to match GitHub Actions.

```bash
pip install requests
python main.py
python cb_main.py
python test_preview.py
python test_cb_preview.py
python test_irm_preview.py
```

`python main.py` sends the dividend report, and `python cb_main.py` sends the CB report plus IRM follow-up messages. The `test_*.py` scripts are local preview/smoke tests; they generate `preview.md` or `cb_preview.md`, or print recent IRM query results for manual inspection.

## Coding Style & Naming Conventions
Follow the existing script-oriented Python style: 4-space indentation, `snake_case` for functions and variables, and `UPPER_SNAKE_CASE` for constants such as URLs, headers, and message limits. Keep request payloads and filter rules explicit and near the top of the file. Reuse existing helpers like `send_wechat()` and `send_alert()` instead of duplicating webhook logic. No formatter is configured here, so keep imports tidy and changes minimal.

## Testing Guidelines
There is no formal unit-test suite yet; current validation is smoke-test based and network-dependent. Before opening a PR, run the relevant `test_*.py` script for the module you changed and verify generated Markdown, message splitting, and filter counts. If you change webhook formatting, include a sample snippet or preview artifact in the PR description.

## Commit & Pull Request Guidelines
Recent history uses Conventional Commit prefixes such as `feat:`, `fix:`, and `docs:`. Keep the subject short and specific, for example: `fix: tighten IRM truncation length`. PRs should describe the user-visible behavior change, list any new or changed environment variables, and mention workflow impacts if `.github/workflows/daily_report.yml` is touched.

## Security & Configuration Tips
Store `JISILU_COOKIE`, `WECHAT_WEBHOOK`, `CB_WECHAT_WEBHOOK`, and `IRM_WECHAT_WEBHOOK` in environment variables or GitHub Actions secrets. Do not commit live cookies, webhook URLs, or debug output containing sensitive payloads.
