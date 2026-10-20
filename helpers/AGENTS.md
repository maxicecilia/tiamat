<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-16 | Updated: 2026-06-16 -->

# helpers

## Purpose
Shared utility functions for use across commands and services. Currently a placeholder — `__init__.py` is empty. This is the intended home for logic that gets duplicated across modules, such as `resolve_repo()` (currently copied in `commands/actions.py`, `commands/merge.py`, and `commands/release.py`).

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Empty package marker (no utilities implemented yet) |

## For AI Agents

### Working In This Directory
- Before adding a new utility here, check `commands/` for duplicated logic that could be extracted.
- The primary candidate for extraction is `resolve_repo(repo_input, repositories)` — a function that converts short repo names to `org/repo` full names using the `REPOSITORIES` list.
- Keep helpers stateless and free of side effects; they should not import from `commands/` or `services/` to avoid circular dependencies.

### Testing Requirements
- Run: `pytest`
- Lint: `ruff check`
- Pure utility functions here should have unit tests without mocking.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
