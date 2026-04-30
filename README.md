# Claude Settings Fix

A small utility that restores Claude settings JSON files from rules in `config.json5`.

## Usage

Run the automatic fixer:

```bat
run_auto.bat
```

Or run it directly with `uv`:

```powershell
uv run python auto_fix.py
```

By default, the tool reads `config.json5` in this directory and applies its rules to:

```text
~/.claude/settings.json
```

On Linux and macOS, `~` resolves to the current home directory. On Windows, `~` resolves to `%USERPROFILE%`, so the default target becomes `%USERPROFILE%\.claude\settings.json`.

## User Overrides

You can create `config.user.json5` next to `config.json5` for machine-specific overrides. Both files are read. When the same top-level key exists in both files, the value from `config.user.json5` wins.

Example `config.user.json5`:

```json5
{
  // Use a test file on this machine, while keeping fix_rules from config.json5.
  default_target: "~/.claude/settings.test.json",

  // Override values referenced by fix_rules in config.json5.
  anthropic_base_url: "http://some_provider",
}
```

If `config.user.json5` defines `fix_rules`, it replaces the `fix_rules` list from `config.json5`.

## Changing `fix_rules`

Edit `config.json5` to change the default restore behavior. Each rule can be written as:

```json5
["action", "json.tree.path", value]
```

Supported actions:

- `add`: writes the value at the path and creates missing parent objects.
- `replace`: writes the value at the path, replacing any existing value.
- `rename`: moves data from the source path to the destination path in `value`, merges with existing destination data, then removes the source key.

Example:

```json5
{
  default_target: "~/.claude/settings.json",

  fix_rules: [
    ["add", "env.ANTHROPIC_AUTH_TOKEN", "some_token"],
    ["add", "env.ANTHROPIC_BASE_URL", "http://some_provider"],
    ["replace", "autoUpdates", false],
    ["replace", "hasCompletedOnboarding", true],
    ["rename", "hooks", "hooks2"],
  ],
}
```

For `add` and `replace`, a string value beginning with `$` references another top-level config key:

```json5
{
  managed_token: "some_token",
  fix_rules: [
    ["add", "env.ANTHROPIC_AUTH_TOKEN", "$managed_token"],
  ],
}
```

After editing `config.json5` or `config.user.json5`, run `run_auto.bat` again.

## Requirements

Install `uv` before running the tool.
