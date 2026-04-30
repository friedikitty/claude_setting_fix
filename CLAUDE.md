# CLAUDE.md

This is an isolated Python utility project. Do not add it as a member of the parent `PythonTools` uv workspace.

## Project

`claude_setting_fix` restores Claude settings JSON files from rules in `config.json5`.

Main entry points:

- `run_auto.bat` applies all rules from `config.json5` to the configured `default_target`.
- `main_gui.py` opens the Tk GUI for manual editing and applying rules.
- `auto_fix.py` is the CLI implementation used by the batch file.

## Commands

Run from this directory:

```powershell
uv run pytest
uv run python auto_fix.py
uv run python main_gui.py
```

## Behavior

Rule actions:

- `add`: writes a value at a JSON tree path, creating missing parent objects.
- `replace`: writes a value at a JSON tree path, replacing any existing value.
- `rename`: moves the source path to the destination path in `value`, merges with existing destination data, then removes the source key.

Keep tests isolated. Do not touch the real `%USERPROFILE%/.claude/settings.json` from tests.
