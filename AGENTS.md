# Repository Guidelines

## Project Structure & Module Organization
- `app.py` hosts the Flask app factory (`create_app`), registers routes, and boots the database; `models.py` defines the SQLAlchemy models `Client`, `ProposalTemplate`, and `Proposal`.
- `proposal_engine.py` renders proposal bodies with Jinja templates; keep template variables aligned with the function docstring.
- `templates/` contains Jinja views for lists, forms, and proposal detail pages; `static/style.css` holds shared styling.
- `crm.db` is the default SQLite database file; override via `DATABASE_URL` in `.env` when pointing to another database.

## Setup, Build & Run
- Python 3.11+ recommended; create a virtualenv: `python -m venv .venv && source .venv/bin/activate`.
- Install dependencies: `pip install -r requirements.txt`.
- Start locally: `FLASK_APP=app FLASK_ENV=development flask run` (or `python app.py`); tables auto-create on startup.
- Configuration lives in `.env` (e.g., `SECRET_KEY`, `DATABASE_URL`); keep `.env` and `crm.db` out of commits.

## Coding Style & Naming Conventions
- Follow PEP 8: 4-space indents, snake_case for functions/routes, PascalCase for models, and f-strings for interpolation.
- Prefer small view helpers over large route handlers; keep type hints consistent with the existing modules.
- Jinja templates use snake_case filenames and Spanish UI copy—maintain tone and terminology when editing views.

## Testing Guidelines
- Add tests under `tests/` named `test_*.py` using `pytest` with Flask’s `app.test_client()`.
- Run with `pytest`; set `DATABASE_URL=sqlite:///:memory:` during tests to avoid mutating `crm.db`.
- Cover route happy/edge paths, template rendering, and `render_proposal_body` context handling.

## Commit & Pull Request Guidelines
- Use concise, imperative commit messages; prefer Conventional Commit prefixes (e.g., `feat: add proposal draft view`, `fix: validate client name`).
- Keep PRs focused; include a short summary, reproduction/fix steps, and screenshots or GIFs for UI changes.
- Call out configuration or data implications (new env vars, database path changes, schema impacts) in the PR description.

## Security & Configuration Tips
- Never commit real secrets; rotate `SECRET_KEY` outside development defaults.
- When switching databases, confirm `SQLALCHEMY_DATABASE_URI` targets the intended file/instance and back up `crm.db` before destructive work.
