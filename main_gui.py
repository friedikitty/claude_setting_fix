from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from claude_setting_fix.core import (
    FixRule,
    copy_user_settings_to_test,
    expand_config_path,
    format_value,
    load_config,
    parse_gui_value,
    restore_settings,
)


PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_DIR / "config.json5"


class SettingsFixApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Claude Settings Restore")
        self.geometry("860x560")
        self.minsize(760, 460)

        self.target_var = tk.StringVar()
        self.action_var = tk.StringVar(value="add")
        self.path_var = tk.StringVar()
        self.value_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")

        self._build_ui()
        self._load_config()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        target_frame = ttk.LabelFrame(root, text="Target settings.json", padding=8)
        target_frame.grid(row=0, column=0, sticky="ew")
        target_frame.columnconfigure(0, weight=1)
        ttk.Entry(target_frame, textvariable=self.target_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(target_frame, text="Browse", command=self._browse_target).grid(row=0, column=1)

        table_frame = ttk.LabelFrame(root, text="Fix rules", padding=8)
        table_frame.grid(row=1, column=0, sticky="nsew", pady=10)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("action", "path", "value")
        self.rules_table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.rules_table.heading("action", text="Action")
        self.rules_table.heading("path", text="JSON tree path")
        self.rules_table.heading("value", text="Value")
        self.rules_table.column("action", width=120, stretch=False)
        self.rules_table.column("path", width=280)
        self.rules_table.column("value", width=360)
        self.rules_table.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.rules_table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.rules_table.configure(yscrollcommand=scrollbar.set)
        self.rules_table.bind("<<TreeviewSelect>>", self._select_rule)

        editor = ttk.Frame(root)
        editor.grid(row=2, column=0, sticky="ew")
        editor.columnconfigure(1, weight=1)
        editor.columnconfigure(3, weight=2)
        ttk.Combobox(editor, textvariable=self.action_var, values=("add", "replace", "rename"), width=10, state="readonly").grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        ttk.Entry(editor, textvariable=self.path_var).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Entry(editor, textvariable=self.value_var).grid(row=0, column=3, sticky="ew", padx=(0, 8))
        ttk.Label(editor, text="Path").grid(row=1, column=1, sticky="w")
        ttk.Label(editor, text="Value / destination path").grid(row=1, column=3, sticky="w")
        ttk.Button(editor, text="Add / Update", command=self._upsert_rule).grid(row=0, column=4, padx=(0, 8))
        ttk.Button(editor, text="Remove", command=self._remove_rule).grid(row=0, column=5)

        buttons = ttk.Frame(root)
        buttons.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(buttons, text="Reload Config", command=self._load_config).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Copy User Files To .test", command=self._copy_to_test).pack(side=tk.LEFT, padx=8)
        ttk.Button(buttons, text="Apply Restore", command=self._apply_restore).pack(side=tk.RIGHT)

        ttk.Label(root, textvariable=self.status_var).grid(row=4, column=0, sticky="ew", pady=(8, 0))

    def _load_config(self) -> None:
        try:
            config = load_config(CONFIG_PATH)
        except Exception as exc:
            messagebox.showerror("Config error", str(exc))
            return
        self.target_var.set(str(config.default_target))
        self._replace_rules(config.fix_rules)
        self.status_var.set(f"Loaded {CONFIG_PATH}")

    def _replace_rules(self, rules: list[FixRule]) -> None:
        self.rules_table.delete(*self.rules_table.get_children())
        for rule in rules:
            self.rules_table.insert("", tk.END, values=(rule.action, rule.path, format_value(rule.value)))

    def _rules_from_table(self) -> list[FixRule]:
        rules: list[FixRule] = []
        for item in self.rules_table.get_children():
            action, path, value = self.rules_table.item(item, "values")
            rules.append(FixRule(str(action), str(path), parse_gui_value(str(value))))
        return rules

    def _browse_target(self) -> None:
        selected = filedialog.askopenfilename(
            title="Choose settings.json",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if selected:
            self.target_var.set(selected)

    def _select_rule(self, _event: tk.Event) -> None:
        selected = self.rules_table.selection()
        if not selected:
            return
        action, path, value = self.rules_table.item(selected[0], "values")
        self.action_var.set(action)
        self.path_var.set(path)
        self.value_var.set(value)

    def _upsert_rule(self) -> None:
        values = (self.action_var.get(), self.path_var.get().strip(), self.value_var.get().strip())
        if not values[1]:
            messagebox.showwarning("Missing path", "Enter a JSON tree path.")
            return
        selected = self.rules_table.selection()
        if selected:
            self.rules_table.item(selected[0], values=values)
        else:
            self.rules_table.insert("", tk.END, values=values)

    def _remove_rule(self) -> None:
        selected = self.rules_table.selection()
        if selected:
            self.rules_table.delete(selected[0])

    def _copy_to_test(self) -> None:
        copied = copy_user_settings_to_test(PROJECT_DIR)
        if copied:
            self.status_var.set("Copied: " + ", ".join(str(path) for path in copied))
        else:
            self.status_var.set("No %USERPROFILE% settings files were found to copy.")

    def _apply_restore(self) -> None:
        target = expand_config_path(self.target_var.get())
        try:
            restore_settings(target, self._rules_from_table())
        except Exception as exc:
            messagebox.showerror("Restore failed", str(exc))
            return
        self.status_var.set(f"Restored {target}")
        messagebox.showinfo("Restore complete", f"Updated {target}")


def main() -> None:
    app = SettingsFixApp()
    app.mainloop()


if __name__ == "__main__":
    main()
