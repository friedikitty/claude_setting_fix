import json

from claude_setting_fix.core import (
    FixRule,
    apply_config_file,
    apply_fix_rules,
    load_config,
)


def test_load_config_expands_tilde_to_home_directory(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("USERPROFILE", str(home))
    config_path = tmp_path / "config.json5"
    config_path.write_text(
        """
        {
          default_target: "~/.claude/settings.json",
          fix_rules: [],
        }
        """,
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.default_target == home / ".claude" / "settings.json"


def test_config_user_json5_overrides_config_json5_keys(tmp_path):
    base_target = tmp_path / "base-settings.json"
    user_target = tmp_path / "user-settings.json"
    config_path = tmp_path / "config.json5"
    user_config_path = tmp_path / "config.user.json5"
    config_path.write_text(
        f"""
        {{
          default_target: {json.dumps(str(base_target))},
          env_value: "base",
          fix_rules: [
            ["add", "env.FROM_BASE", "$env_value"],
          ],
        }}
        """,
        encoding="utf-8",
    )
    user_config_path.write_text(
        f"""
        {{
          default_target: {json.dumps(str(user_target))},
          env_value: "user",
        }}
        """,
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.default_target == user_target
    assert config.fix_rules == [FixRule("add", "env.FROM_BASE", "user")]


def test_apply_fix_rules_adds_nested_env_and_replaces_top_level_values():
    settings = {
        "env": {"EXISTING": "keep"},
        "skipDangerousModePermissionPrompt": False,
        "autoUpdates": True,
    }
    rules = [
        FixRule("add", "env.ANTHROPIC_AUTH_TOKEN", "some_token"),
        FixRule("replace", "skipDangerousModePermissionPrompt", True),
        FixRule("replace", "autoUpdates", False),
    ]

    fixed = apply_fix_rules(settings, rules)

    assert fixed == {
        "env": {
            "EXISTING": "keep",
            "ANTHROPIC_AUTH_TOKEN": "some_token",
        },
        "skipDangerousModePermissionPrompt": True,
        "autoUpdates": False,
    }
    assert "ANTHROPIC_AUTH_TOKEN" not in settings["env"]


def test_add_rule_creates_missing_json_tree():
    fixed = apply_fix_rules(
        {}, [FixRule("add", "env.ANTHROPIC_BASE_URL", "http://127.0.0.1:15011")]
    )

    assert fixed == {"env": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:15011"}}


def test_replace_hooks_from_named_config_value(tmp_path):
    config_path = tmp_path / "config.json5"
    config_path.write_text(
        """
        {
          hooks2: {
            Stop: [{ matcher: "", hooks: [{ type: "command", command: "done" }] }]
          },
          fix_rules: [
            ["replace", "hooks", "$hooks2"],
          ],
        }
        """,
        encoding="utf-8",
    )

    config = load_config(config_path)
    fixed = apply_fix_rules({"hooks": {"old": True}}, config.fix_rules)

    assert fixed["hooks"] == {
        "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "done"}]}]
    }


def test_rename_moves_source_key_to_destination_key_and_removes_source():
    settings = {
        "hooks": {"Stop": [{"matcher": "old"}]},
        "other": True,
    }

    fixed = apply_fix_rules(settings, [FixRule("rename", "hooks", "hooks2")])

    assert fixed == {
        "hooks2": {"Stop": [{"matcher": "old"}]},
        "other": True,
    }
    assert "hooks" in settings


def test_rename_merges_with_existing_destination_without_losing_data():
    settings = {
        "hooks": {
            "Stop": [{"matcher": "from-hooks"}],
            "PreToolUse": [{"matcher": "from-hooks"}],
        },
        "hooks2": {
            "Stop": [{"matcher": "from-hooks2"}],
            "Notification": [{"matcher": "from-hooks2"}],
        },
    }

    fixed = apply_fix_rules(settings, [FixRule("rename", "hooks", "hooks2")])

    assert "hooks" not in fixed
    assert fixed["hooks2"] == {
        "Stop": [{"matcher": "from-hooks2"}, {"matcher": "from-hooks"}],
        "Notification": [{"matcher": "from-hooks2"}],
        "PreToolUse": [{"matcher": "from-hooks"}],
    }


def test_rename_rule_value_is_destination_path_not_config_reference(tmp_path):
    config_path = tmp_path / "config.json5"
    config_path.write_text(
        """
        {
          hooks2: { existing: true },
          fix_rules: [
            ["rename", "hooks", "hooks2"],
          ],
        }
        """,
        encoding="utf-8",
    )

    config = load_config(config_path)
    fixed = apply_fix_rules({"hooks": {"Stop": []}}, config.fix_rules)

    assert fixed == {"hooks2": {"Stop": []}}


def test_fixed_settings_matches_expected_backup_with_rules(tmp_path):
    source = {
        "env": {"EXISTING": "keep"},
        "skipDangerousModePermissionPrompt": False,
        "autoUpdates": True,
        "hasCompletedOnboarding": False,
        "hooks": {"managed": True},
    }
    expected = {
        "env": {
            "EXISTING": "keep",
            "ANTHROPIC_AUTH_TOKEN": "some_token",
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:15011",
            "CLAUDE_CODE_ATTRIBUTION_HEADER": "0",
        },
        "skipDangerousModePermissionPrompt": True,
        "autoUpdates": False,
        "hasCompletedOnboarding": True,
        "hooks2": {"managed": True},
    }
    source_path = tmp_path / "settings.json"
    expected_path = tmp_path / "settings.back.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    expected_path.write_text(json.dumps(expected), encoding="utf-8")

    rules = [
        FixRule("add", "env.ANTHROPIC_AUTH_TOKEN", "some_token"),
        FixRule("add", "env.ANTHROPIC_BASE_URL", "http://127.0.0.1:15011"),
        FixRule("add", "env.CLAUDE_CODE_ATTRIBUTION_HEADER", "0"),
        FixRule("replace", "skipDangerousModePermissionPrompt", True),
        FixRule("replace", "autoUpdates", False),
        FixRule("replace", "hasCompletedOnboarding", True),
        FixRule("rename", "hooks", "hooks2"),
    ]

    fixed = apply_fix_rules(json.loads(source_path.read_text(encoding="utf-8")), rules)

    assert fixed == json.loads(expected_path.read_text(encoding="utf-8"))


def test_apply_config_file_uses_config_target_and_rules(tmp_path):
    target_path = tmp_path / "settings.json"
    config_path = tmp_path / "config.json5"
    target_path.write_text(
        json.dumps(
            {
                "env": {"EXISTING": "keep"},
                "autoUpdates": True,
                "hooks": {"Stop": [{"matcher": "old"}]},
            }
        ),
        encoding="utf-8",
    )
    config_path.write_text(
        f"""
        {{
          default_target: {json.dumps(str(target_path))},
          fix_rules: [
            ["add", "env.ANTHROPIC_AUTH_TOKEN", "some_token"],
            ["replace", "autoUpdates", false],
            ["rename", "hooks", "hooks2"],
          ],
        }}
        """,
        encoding="utf-8",
    )

    fixed = apply_config_file(config_path)

    expected = {
        "env": {
            "EXISTING": "keep",
            "ANTHROPIC_AUTH_TOKEN": "some_token",
        },
        "autoUpdates": False,
        "hooks2": {"Stop": [{"matcher": "old"}]},
    }
    assert fixed == expected
    assert json.loads(target_path.read_text(encoding="utf-8")) == expected
