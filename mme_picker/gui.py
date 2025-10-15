#!/usr/bin/env python3
"""
Simple Tkinter front end for the unified MME picker.

Allows selecting lineup/projection files, adjusting key tuning parameters with
inline tooltips, and running the picker while displaying console output.
"""

from __future__ import annotations

import io
import threading
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Dict, List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .picker_helpers import PickerDefaults, ScoreWeights, get_registered_helpers
from .core import main as picker_main


def _build_tooltips() -> Dict[str, str]:
    return {
        "n": "How many final lineups to select (default 150).",
        "cap": "Max percentage exposure allowed for any single player.",
        "max_repeat": "Initial cap on shared players between two selected lineups.",
        "max_repeat_limit": "Relaxed cap once the greedy selector stalls.",
        "min_usage": "Prune any lineup containing players below this pool usage (%).",
        "breadth": "Penalty applied when a lineup uses players near their exposure cap.",
        "selection_window": "Number of top-scoring candidates evaluated per greedy sweep.",
        "stalled": "Failed sweeps before bumping the overlap limit.",
        "w_proj": "Weight on normalized projection score.",
        "w_corr": "Weight on sport-specific correlation/stack bonus.",
        "w_uniq": "Weight on lineup uniqueness (inverse player frequency).",
        "w_chalk": "Penalty weight for overall chalkiness.",
        "seed": "Optional RNG seed for reproducible ordering.",
        "out_prefix": "Optional file prefix for exported outputs.",
        "out_dir": "Output directory (auto-detected by sport if left blank).",
    }


class ToolTip:
    """Minimal tooltip helper for Tkinter widgets."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tooltip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event: tk.Event) -> None:
        if self.tooltip or not self.text:
            return
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.attributes("-topmost", True)
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tooltip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tooltip,
            text=self.text,
            justify=tk.LEFT,
            background="#2c2c2c",
            foreground="white",
            relief=tk.SOLID,
            borderwidth=1,
            padx=6,
            pady=4,
            font=("TkDefaultFont", 9),
        )
        label.pack()

    def _hide(self, _event: tk.Event) -> None:
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


class PickerGUI:
    def __init__(self) -> None:
        self.helpers = get_registered_helpers()
        self.root = tk.Tk()
        self.root.title("FanDuel MME Picker")
        self.root.geometry("760x640")
        self.root.minsize(700, 600)

        self.tooltips = _build_tooltips()

        self.sport_var = tk.StringVar(value=sorted(self.helpers)[0])
        self.lineup_var = tk.StringVar()
        self.proj_var = tk.StringVar()
        self.prefix_var = tk.StringVar()
        self.outdir_var = tk.StringVar()
        self.seed_var = tk.StringVar()

        self.param_vars: Dict[str, tk.StringVar] = {
            "n": tk.StringVar(),
            "cap": tk.StringVar(),
            "max_repeat": tk.StringVar(),
            "max_repeat_limit": tk.StringVar(),
            "min_usage": tk.StringVar(),
            "breadth": tk.StringVar(),
            "selection_window": tk.StringVar(),
            "stalled": tk.StringVar(),
            "w_proj": tk.StringVar(),
            "w_corr": tk.StringVar(),
            "w_uniq": tk.StringVar(),
            "w_chalk": tk.StringVar(),
        }

        self.output_frame = ttk.Frame(self.root)
        self.output_text = tk.Text(
            self.output_frame,
            height=14,
            state=tk.DISABLED,
            background="#111111",
            foreground="#E8E8E8",
            insertbackground="#E8E8E8",
            wrap=tk.WORD,
        )
        self.output_scroll = ttk.Scrollbar(self.output_frame, orient=tk.VERTICAL, command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=self.output_scroll.set)

        self.run_button = ttk.Button(self.root, text="Run Picker", command=self.run_picker)

        self._build_layout()
        self._populate_defaults()

    def _build_layout(self) -> None:
        main_frame = ttk.Frame(self.root, padding=16)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Sport selector
        sport_frame = ttk.Frame(main_frame)
        sport_frame.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(sport_frame, text="Sport:").pack(side=tk.LEFT)
        sport_menu = ttk.OptionMenu(
            sport_frame, self.sport_var, self.sport_var.get(), *sorted(self.helpers), command=self._on_sport_change
        )
        sport_menu.pack(side=tk.LEFT, padx=(8, 0))

        # File pickers
        file_frame = ttk.LabelFrame(main_frame, text="Input Files")
        file_frame.pack(fill=tk.X, pady=(0, 12))
        self._add_file_picker(file_frame, "Lineup CSV", self.lineup_var, 0)
        self._add_file_picker(file_frame, "Projections CSV", self.proj_var, 1)

        # Parameters grid
        params_frame = ttk.LabelFrame(main_frame, text="Selection Parameters")
        params_frame.pack(fill=tk.X, pady=(0, 12))
        param_rows = [
            ("n_target", "n"),
            ("cap_pct", "cap"),
            ("max_repeat_init", "max_repeat"),
            ("max_repeat_limit", "max_repeat_limit"),
            ("min_usage_pct", "min_usage"),
            ("breadth_penalty", "breadth"),
            ("selection_window", "selection_window"),
            ("stalled_threshold", "stalled"),
        ]
        weight_rows = [
            ("W_PROJ", "w_proj"),
            ("W_CORR", "w_corr"),
            ("W_UNIQ", "w_uniq"),
            ("W_CHALK", "w_chalk"),
        ]

        for idx, (label, key) in enumerate(param_rows):
            self._add_param_row(params_frame, label, key, row=idx)

        weights_label = ttk.LabelFrame(main_frame, text="Score Weights")
        weights_label.pack(fill=tk.X, pady=(0, 12))
        for idx, (label, key) in enumerate(weight_rows):
            self._add_param_row(weights_label, label, key, row=idx)

        # Optional extras
        extras = ttk.LabelFrame(main_frame, text="Optional")
        extras.pack(fill=tk.X, pady=(0, 12))
        self._add_simple_entry(extras, "Output Prefix", self.prefix_var, 0, "out_prefix")
        self._add_simple_entry(extras, "Output Directory", self.outdir_var, 1, "out_dir")
        self._add_simple_entry(extras, "Seed", self.seed_var, 2, "seed")

        # Run + output
        self.run_button.pack(pady=(0, 8))
        ttk.Label(main_frame, text="Picker Output:").pack(anchor="w")
        self.output_frame.pack(fill=tk.BOTH, expand=True)
        self.output_text.grid(row=0, column=0, sticky="nsew")
        self.output_scroll.grid(row=0, column=1, sticky="ns")
        self.output_frame.columnconfigure(0, weight=1)
        self.output_frame.rowconfigure(0, weight=1)

    def _add_file_picker(self, parent: ttk.LabelFrame, label: str, var: tk.StringVar, row: int) -> None:
        lbl = ttk.Label(parent, text=label + ":")
        lbl.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=6)
        entry = ttk.Entry(parent, textvariable=var, width=60)
        entry.grid(row=row, column=1, sticky="we", pady=6)
        ttk.Button(parent, text="Browse…", command=lambda v=var: self._choose_file(v)).grid(
            row=row, column=2, padx=(8, 0), pady=6
        )
        parent.columnconfigure(1, weight=1)

    def _add_param_row(self, parent: ttk.LabelFrame, label: str, key: str, row: int) -> None:
        lbl = ttk.Label(parent, text=f"{label}:")
        lbl.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ToolTip(lbl, self.tooltips.get(key, ""))
        entry = ttk.Entry(parent, textvariable=self.param_vars[key], width=12)
        entry.grid(row=row, column=1, sticky="w", pady=4)

    def _add_simple_entry(self, parent: ttk.LabelFrame, label: str, var: tk.StringVar, row: int, tip_key: str) -> None:
        lbl = ttk.Label(parent, text=label + ":")
        lbl.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ToolTip(lbl, self.tooltips.get(tip_key, ""))
        entry = ttk.Entry(parent, textvariable=var, width=24)
        entry.grid(row=row, column=1, sticky="w", pady=4)

    def _choose_file(self, var: tk.StringVar) -> None:
        initial = Path(var.get()).expanduser()
        initial_dir = initial.parent if initial.exists() else Path.cwd()
        file_path = filedialog.askopenfilename(
            title="Select CSV file",
            initialdir=initial_dir,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if file_path:
            var.set(file_path)

    def _on_sport_change(self, _value: str) -> None:
        self._populate_defaults()

    def _populate_defaults(self) -> None:
        sport = self.sport_var.get()
        helper = self.helpers[sport]
        defaults: PickerDefaults = helper.defaults()
        weights: ScoreWeights = defaults.weights

        self.param_vars["n"].set(str(defaults.n_target))
        self.param_vars["cap"].set(f"{defaults.cap_pct:g}")
        self.param_vars["max_repeat"].set(str(defaults.max_repeat_init))
        self.param_vars["max_repeat_limit"].set(str(defaults.max_repeat_limit))
        self.param_vars["min_usage"].set(f"{defaults.min_usage_pct:g}")
        self.param_vars["breadth"].set(f"{defaults.breadth_penalty:g}")
        self.param_vars["selection_window"].set(str(defaults.selection_window))
        self.param_vars["stalled"].set(str(defaults.stalled_threshold))

        self.param_vars["w_proj"].set(f"{weights.projection:g}")
        self.param_vars["w_corr"].set(f"{weights.correlation:g}")
        self.param_vars["w_uniq"].set(f"{weights.uniqueness:g}")
        self.param_vars["w_chalk"].set(f"{weights.chalk:g}")

        # Suggested default output directory
        self.outdir_var.set("autoNHL" if sport == "nhl" else "autoMME")

    def _collect_args(self) -> Optional[List[str]]:
        lineup = self.lineup_var.get().strip()
        projections = self.proj_var.get().strip()
        if not lineup or not Path(lineup).exists():
            messagebox.showerror("Missing lineup CSV", "Please choose a valid lineup CSV.")
            return None
        if not projections or not Path(projections).exists():
            messagebox.showerror("Missing projections CSV", "Please choose a valid projections CSV.")
            return None

        args: List[str] = ["--sport", self.sport_var.get(), lineup, projections]

        def add_flag(flag: str, key: str, cast=float, fmt="{:g}") -> None:
            value = self.param_vars[key].get().strip()
            if not value:
                return
            try:
                numeric = cast(value)
            except ValueError:
                raise ValueError(f"Invalid value for {flag}: {value}")
            args.extend([flag, fmt.format(numeric)])

        try:
            add_flag("--n", "n", int, "{}")
            add_flag("--cap", "cap", float)
            add_flag("--max-repeat", "max_repeat", int, "{}")
            add_flag("--max-repeat-limit", "max_repeat_limit", int, "{}")
            add_flag("--min-usage-pct", "min_usage", float)
            add_flag("--breadth-penalty", "breadth", float)
            add_flag("--selection-window", "selection_window", int, "{}")
            add_flag("--stalled-threshold", "stalled", int, "{}")
            add_flag("--w-proj", "w_proj", float)
            add_flag("--w-corr", "w_corr", float)
            add_flag("--w-uniq", "w_uniq", float)
            add_flag("--w-chalk", "w_chalk", float)
        except ValueError as exc:
            messagebox.showerror("Invalid parameter", str(exc))
            return None

        if self.prefix_var.get().strip():
            args.extend(["--out-prefix", self.prefix_var.get().strip()])
        if self.outdir_var.get().strip():
            args.extend(["--out-dir", self.outdir_var.get().strip()])
        if self.seed_var.get().strip():
            seed_val = self.seed_var.get().strip()
            if not seed_val.lstrip("-").isdigit():
                messagebox.showerror("Invalid seed", "Seed must be an integer.")
                return None
            args.extend(["--seed", seed_val])
        return args

    def run_picker(self) -> None:
        args = self._collect_args()
        if args is None:
            return

        self._set_run_state(normal=False)
        self._append_output(f"Running picker with arguments: {' '.join(args)}\n")

        def task() -> None:
            redirector = _TextRedirector(self._append_output_threadsafe)
            try:
                with redirect_stdout(redirector), redirect_stderr(redirector):
                    picker_main(args)
            except Exception as exc:
                self._append_output_threadsafe(f"\nERROR: {exc}\n")
                self._show_error("Picker failed", str(exc))
            else:
                self._show_info("Picker complete", "Lineup selection finished.")
            finally:
                self._set_run_state(normal=True)

        threading.Thread(target=task, daemon=True).start()

    def _append_output(self, text: str) -> None:
        self.output_text.configure(state=tk.NORMAL)
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        self.output_text.configure(state=tk.DISABLED)

    def _append_output_threadsafe(self, text: str) -> None:
        self.root.after(0, lambda: self._append_output(text))

    def _show_info(self, title: str, message: str) -> None:
        self.root.after(0, lambda: messagebox.showinfo(title, message))

    def _show_error(self, title: str, message: str) -> None:
        self.root.after(0, lambda: messagebox.showerror(title, message))

    def _set_run_state(self, normal: bool) -> None:
        def update() -> None:
            self.run_button.configure(
                state=tk.NORMAL if normal else tk.DISABLED,
                text="Run Picker" if normal else "Running…",
            )

        self.root.after(0, update)

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    PickerGUI().run()


class _TextRedirector(io.TextIOBase):
    def __init__(self, callback):
        self.callback = callback

    def write(self, data):
        if data:
            self.callback(data)
        return len(data)

    def flush(self):
        return


if __name__ == "__main__":
    main()
