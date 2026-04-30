from __future__ import annotations

import copy
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import json5

DEFAULT_TARGET = "~/.claude/settings.json"


@dataclass(frozen=True)
class FixRule:
    action: str
    path: str
    value: Any


@dataclass(frozen=True)
class AppConfig:
    default_target: Path
    fix_rules: list[FixRule]


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def save_json_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.write("\n")


def load_config(path: Path) -> AppConfig:
    raw = _load_merged_config(path)

    default_target = expand_config_path(str(raw.get("default_target", DEFAULT_TARGET)))
    rules = [_parse_rule(rule, raw) for rule in raw.get("fix_rules", [])]
    return AppConfig(default_target=default_target, fix_rules=rules)


def expand_config_path(path: str) -> Path:
    expanded = os.path.expandvars(path)
    if expanded == "~" or expanded.startswith(("~/", "~\\")):
        home = _home_path_for_config()
        suffix = expanded[1:].lstrip("/\\")
        return home / suffix if suffix else home
    return Path(expanded)


def _load_merged_config(path: Path) -> dict[str, Any]:
    raw = _load_json5_object(path)
    user_path = _user_config_path(path)
    if user_path.exists():
        raw.update(_load_json5_object(user_path))
    return raw


def _load_json5_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        raw = json5.load(file)
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain an object")
    return raw


def _user_config_path(path: Path) -> Path:
    if path.name == "config.json5":
        return path.with_name("config.user.json5")
    return path.with_suffix(".user" + path.suffix)


def _home_path_for_config() -> Path:
    if sys.platform == "win32" and os.environ.get("USERPROFILE"):
        return Path(os.environ["USERPROFILE"])
    return Path.home()


def apply_fix_rules(settings: dict[str, Any], rules: list[FixRule]) -> dict[str, Any]:
    fixed = copy.deepcopy(settings)
    for rule in rules:
        action = rule.action.lower()
        if action in {"add", "replace"}:
            _set_tree_value(fixed, rule.path, copy.deepcopy(rule.value))
        elif action == "rename":
            if not isinstance(rule.value, str):
                raise ValueError(
                    "Rename rule value must be the destination JSON tree path"
                )
            _rename_tree_value(fixed, rule.path, rule.value)
        else:
            raise ValueError(f"Unsupported fix rule action: {rule.action}")
    return fixed


def restore_settings(target_path: Path, rules: list[FixRule]) -> dict[str, Any]:
    settings = load_json_file(target_path)
    fixed = apply_fix_rules(settings, rules)
    save_json_file(target_path, fixed)
    return fixed


def apply_config_file(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    return restore_settings(config.default_target, config.fix_rules)


def copy_user_settings_to_test(project_dir: Path) -> list[Path]:
    test_dir = project_dir / ".test"
    test_dir.mkdir(exist_ok=True)
    copied: list[Path] = []
    for filename in ("settings.json", "settings.back.json"):
        source = (
            _home_path_for_config() / ".claude" / filename
        )
        if source.exists():
            destination = test_dir / filename
            shutil.copy2(source, destination)
            copied.append(destination)
    return copied


def parse_gui_value(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        return ""
    try:
        return json5.loads(stripped)
    except Exception:
        return text


def format_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _parse_rule(rule: Any, config: dict[str, Any]) -> FixRule:
    if isinstance(rule, dict):
        action = str(rule["action"])
        path = str(rule["path"])
        value = rule["value"]
    elif isinstance(rule, list | tuple) and len(rule) == 3:
        action = str(rule[0])
        path = str(rule[1])
        value = rule[2]
    else:
        raise ValueError(f"Invalid fix rule: {rule!r}")

    if action.lower() != "rename" and isinstance(value, str) and value.startswith("$"):
        key = value[1:]
        if key not in config:
            raise ValueError(f"Config value reference not found: {value}")
        value = config[key]
    return FixRule(action=action, path=path, value=value)


def _set_tree_value(root: dict[str, Any], dotted_path: str, value: Any) -> None:
    parts = _path_parts(dotted_path)
    cursor: dict[str, Any] = root
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[part] = next_value
        cursor = next_value
    cursor[parts[-1]] = value


def _rename_tree_value(
    root: dict[str, Any], source_path: str, destination_path: str
) -> None:
    source = _pop_tree_value(root, source_path)
    if source is _MISSING:
        return

    destination = _get_tree_value(root, destination_path)
    if destination is _MISSING:
        _set_tree_value(root, destination_path, source)
        return
    _set_tree_value(root, destination_path, _merge_values(destination, source))


def _get_tree_value(root: dict[str, Any], dotted_path: str) -> Any:
    parts = _path_parts(dotted_path)
    cursor: Any = root
    for part in parts:
        if not isinstance(cursor, dict) or part not in cursor:
            return _MISSING
        cursor = cursor[part]
    return cursor


def _pop_tree_value(root: dict[str, Any], dotted_path: str) -> Any:
    parts = _path_parts(dotted_path)
    cursor: Any = root
    for part in parts[:-1]:
        if not isinstance(cursor, dict) or part not in cursor:
            return _MISSING
        cursor = cursor[part]
    if not isinstance(cursor, dict) or parts[-1] not in cursor:
        return _MISSING
    return cursor.pop(parts[-1])


def _merge_values(destination: Any, source: Any) -> Any:
    if isinstance(destination, dict) and isinstance(source, dict):
        merged = copy.deepcopy(destination)
        for key, source_value in source.items():
            if key in merged:
                merged[key] = _merge_values(merged[key], source_value)
            else:
                merged[key] = copy.deepcopy(source_value)
        return merged

    if isinstance(destination, list) and isinstance(source, list):
        merged = copy.deepcopy(destination)
        for item in source:
            if item not in merged:
                merged.append(copy.deepcopy(item))
        return merged

    return copy.deepcopy(source)


def _path_parts(dotted_path: str) -> list[str]:
    parts = [part for part in dotted_path.split(".") if part]
    if not parts:
        raise ValueError("Fix rule path cannot be empty")
    return parts


_MISSING = object()
