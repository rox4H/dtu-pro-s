# Contributing

Thanks for helping improve Hoymiles DTU Reader. This project is licensed under the [MIT License](LICENSE); by contributing you agree that your contribution is released under it.

## Set up

Python 3.11 or later and Node.js 22 or later are required for the full test suite.

```bash
git clone https://github.com/rox4H/dtu-pro-s.git
cd dtu-pro-s
python -m venv .venv
source .venv/bin/activate    # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Before you open a pull request

```bash
ruff check .
pytest
(cd packages/npm-client && npm test)
(cd packages/npm-client && npm run pack:check)
```

The tests need no hardware or network. New behavior needs a test; bug fixes need a test that fails without the fix. Use the `FakeDTU` server and the register builders in `tests/conftest.py`.

## Rules of the repository

- **English only**, in code, comments, log messages, documentation and commit messages.
- **No secrets or real installation data.** Never commit `.env`, logs, real serial numbers, host names or private IP addresses.
- **Keep the invariants** listed in [AGENTS.md](AGENTS.md): local-only, read-only, no cloud services and `None` for unmeasured values.
- **Document public changes.** New or changed settings go in `.env.example` and [the configuration guide](docs/configuration.md); API changes in [the API reference](docs/api.md); breaking changes in `CHANGELOG.md` with a version bump.
- **Write for the reader.** The README and guides in `docs/` are for people who install and run the reader. Design notes for contributors go in `docs/development/`.
- **Commits** follow Conventional Commits (`feat:`, `fix:`, `docs:`, `build:`, `test:`, `refactor:`, `chore:`), imperative mood, one logical change each.

## Working with AI coding agents

The repository follows the [AGENTS.md](AGENTS.md) convention. [AGENTS.md](AGENTS.md) describes the architecture, the rules that must not be broken and the commands to run. Most coding agents read it automatically; Claude Code reads `CLAUDE.md`, which imports `AGENTS.md`. If your tool does not pick it up, ask it to read `AGENTS.md` first. Changes written by an agent follow the same rules and review as any other contribution.

## Reporting hardware compatibility

If your DTU or meter behaves differently, open an issue with the DTU model and firmware, the meter model, the output of `hoymiles-dtu-reader scan-meter` (read-only) with serial numbers removed, and the relevant log lines.

## Security issues

Please do not open public issues for vulnerabilities. See [SECURITY.md](SECURITY.md).
