from __future__ import annotations

import argparse
from pathlib import Path

from claude_setting_fix.core import apply_config_file, load_config


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_DIR / "config.json5"


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Claude settings fix rules from config.json5.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to config.json5. Defaults to the config next to auto_fix.py.",
    )
    args = parser.parse_args()

    config_path = args.config.expanduser().resolve()
    config = load_config(config_path)
    apply_config_file(config_path)
    print(f"Applied {len(config.fix_rules)} rules to {config.default_target}")


if __name__ == "__main__":
    main()
