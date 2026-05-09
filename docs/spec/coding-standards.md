# Coding Standards Spec

## 1. Python Standards

Tooling:

- `uv` for dependency management.
- `ruff` for linting and formatting.
- `pytest` for tests.
- `mypy` for type checking.

Rules:

- Use type hints for public functions and service boundaries.
- Use Pydantic for API, config, and agent schemas.
- Keep provider-specific LLM code behind the adapter.
- Keep persistence behind repository/service interfaces.
- Do not place prompt strings inline in business logic when they should be versioned prompts.
- Do not swallow parser, retrieval, model, or gate warnings.

## 2. TypeScript Standards

Tooling:

- `pnpm`.
- Next.js.
- React.
- TypeScript strict mode.
- ESLint.
- Prettier.

Rules:

- API response types should be generated or mirrored from backend schemas where practical.
- UI components must render backend evidence and gate status without inventing content.
- Evidence links, issue severity, and gate warnings must remain visible.

## 3. Naming

- Python modules use snake_case.
- TypeScript files use kebab-case or component PascalCase consistently by directory convention.
- IDs use prefixes: `job_`, `paper_`, `claim_`, `ev_`, `issue_`, `run_`, `report_`.
- Enum values use snake_case.

## 4. Logging and Errors

- Log job id, stage, agent name, and run id where available.
- Do not log full manuscript text by default.
- Errors crossing API boundaries must use documented error codes.
- Warnings that affect report reliability must be stored and surfaced.

## 5. Comments

- Add comments for non-obvious reasoning, numeric checks, and gate logic.
- Avoid comments that restate simple code.
- Document public service interfaces with concise docstrings.

