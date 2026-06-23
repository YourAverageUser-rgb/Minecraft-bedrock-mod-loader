"""Tkinter GUI for bedrock-mod-loader.

Pure-stdlib by default (no extra dependency needed to get a working window); if the
optional `sv_ttk` package is installed (`pip install "bedrock-mod-loader[gui]"`) the
window picks up its modern Sun Valley theme automatically, otherwise it falls back to
a hand-styled dark/light ttk theme.
"""
from __future__ import annotations

import queue
import shutil
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from . import config, discovery, doctor, installer, loadout, watcher, world_config
from .cli import _format_version, _install_one
from .packs import PackError, discover_sources, is_world_save, read_pack_info

APP_TITLE = "Bedrock Mod Loader"

DARK_PALETTE = {
    "bg": "#1e1f29",
    "fg": "#e6e6e6",
    "field_bg": "#2a2b3a",
    "tree_bg": "#23242f",
}


def _apply_theme(root: tk.Tk, dark: bool) -> None:
    style = ttk.Style(root)
    try:
        import sv_ttk  # type: ignore

        sv_ttk.set_theme("dark" if dark else "light")
        return
    except ImportError:
        pass

    style.theme_use("clam")
    if not dark:
        return
    palette = DARK_PALETTE
    root.configure(bg=palette["bg"])
    style.configure(".", background=palette["bg"], foreground=palette["fg"], fieldbackground=palette["field_bg"])
    style.configure("TFrame", background=palette["bg"])
    style.configure("TLabel", background=palette["bg"], foreground=palette["fg"])
    style.configure("TButton", background=palette["field_bg"], foreground=palette["fg"])
    style.configure("TNotebook", background=palette["bg"])
    style.configure("TNotebook.Tab", background=palette["field_bg"], foreground=palette["fg"])
    style.configure("Treeview", background=palette["tree_bg"], fieldbackground=palette["tree_bg"], foreground=palette["fg"])
    style.configure("TEntry", fieldbackground=palette["field_bg"], foreground=palette["fg"])
    style.configure("TCombobox", fieldbackground=palette["field_bg"], foreground=palette["fg"])
    style.configure("TCheckbutton", background=palette["bg"], foreground=palette["fg"])
    style.configure("TLabelframe", background=palette["bg"], foreground=palette["fg"])
    style.configure("TLabelframe.Label", background=palette["bg"], foreground=palette["fg"])


class App(tk.Tk):
    def __init__(self, game_dir: Optional[Path] = None):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("920x640")
        self.minsize(760, 520)

        saved = config.load_config()
        self._dark = saved.get("theme", "dark") == "dark"
        _apply_theme(self, self._dark)

        self.game_dir_var = tk.StringVar(value=str(game_dir) if game_dir else saved.get("game_dir", ""))
        self.world_var = tk.StringVar(value=saved.get("last_world", ""))
        self._log_queue: queue.Queue = queue.Queue()
        self._watch_stop = threading.Event()
        self._watch_thread: Optional[threading.Thread] = None

        self._build_top_bar()
        self._build_notebook()
        self._build_status_bar()

        if self.game_dir_var.get():
            self._refresh_worlds()
            self._refresh_packs()
        else:
            self._auto_detect_game_dir(silent=True)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self._drain_log_queue)

    # -- layout ---------------------------------------------------------
    def _build_top_bar(self) -> None:
        bar = ttk.Frame(self, padding=10)
        bar.pack(fill="x")

        ttk.Label(bar, text="Game directory (com.mojang):").pack(side="left")
        ttk.Entry(bar, textvariable=self.game_dir_var, width=50).pack(side="left", padx=6, fill="x", expand=True)
        ttk.Button(bar, text="Browse...", command=self._browse_game_dir).pack(side="left", padx=2)
        ttk.Button(bar, text="Auto-detect", command=self._auto_detect_game_dir).pack(side="left", padx=2)
        ttk.Button(bar, text="Toggle theme", command=self._toggle_theme).pack(side="right", padx=2)

    def _build_notebook(self) -> None:
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.install_tab = ttk.Frame(self.notebook, padding=10)
        self.library_tab = ttk.Frame(self.notebook, padding=10)
        self.watch_tab = ttk.Frame(self.notebook, padding=10)
        self.doctor_tab = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.install_tab, text="Install")
        self.notebook.add(self.library_tab, text="Library")
        self.notebook.add(self.watch_tab, text="Watch Folder")
        self.notebook.add(self.doctor_tab, text="Doctor")

        self._build_install_tab()
        self._build_library_tab()
        self._build_watch_tab()
        self._build_doctor_tab()

    def _build_status_bar(self) -> None:
        self.status_var = tk.StringVar(value="Ready.")
        bar = ttk.Frame(self, padding=(10, 2))
        bar.pack(fill="x")
        ttk.Label(bar, textvariable=self.status_var).pack(side="left")

    # -- Install tab ------------------------------------------------------
    def _build_install_tab(self) -> None:
        frame = self.install_tab

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=4)
        self.source_var = tk.StringVar()
        ttk.Label(row, text="Pack / addon / world:").pack(side="left")
        ttk.Entry(row, textvariable=self.source_var, width=50).pack(side="left", padx=6, fill="x", expand=True)
        ttk.Button(row, text="Browse file...", command=self._browse_source_file).pack(side="left", padx=2)
        ttk.Button(row, text="Browse folder...", command=self._browse_source_dir).pack(side="left", padx=2)

        row2 = ttk.Frame(frame)
        row2.pack(fill="x", pady=4)
        ttk.Label(row2, text="World:").pack(side="left")
        self.install_world_combo = ttk.Combobox(row2, textvariable=self.world_var, width=30)
        self.install_world_combo.pack(side="left", padx=6)
        ttk.Button(row2, text="Refresh worlds", command=self._refresh_worlds).pack(side="left", padx=2)

        self.prod_var = tk.BooleanVar(value=False)
        self.enable_var = tk.BooleanVar(value=True)
        self.force_var = tk.BooleanVar(value=False)
        opts = ttk.Frame(frame)
        opts.pack(fill="x", pady=4)
        ttk.Checkbutton(opts, text="Install into production folders", variable=self.prod_var).pack(side="left", padx=4)
        ttk.Checkbutton(opts, text="Enable in selected world", variable=self.enable_var).pack(side="left", padx=4)
        ttk.Checkbutton(opts, text="Force reinstall", variable=self.force_var).pack(side="left", padx=4)

        ttk.Button(frame, text="Install", command=self._do_install).pack(anchor="w", pady=6)

        self.install_log = tk.Text(frame, height=16, wrap="word")
        self.install_log.pack(fill="both", expand=True, pady=4)
        self.install_log.configure(state="disabled")

    def _browse_source_file(self) -> None:
        path = filedialog.askopenfilename(title="Choose a pack/addon/world file")
        if path:
            self.source_var.set(path)

    def _browse_source_dir(self) -> None:
        path = filedialog.askdirectory(title="Choose a pack folder")
        if path:
            self.source_var.set(path)

    def _do_install(self) -> None:
        source = self.source_var.get().strip()
        if not source:
            messagebox.showwarning(APP_TITLE, "Choose a pack, addon, or world to install first.")
            return
        game_dir = self._require_game_dir()
        if game_dir is None:
            return

        world_name = self.world_var.get().strip()
        dev = not self.prod_var.get()
        force = self.force_var.get()
        enable = self.enable_var.get()
        log = lambda message: self._log(self.install_log, message)

        def work() -> None:
            log(f"Installing {source} ...")
            try:
                world_dir = discovery.find_world_by_name(game_dir, world_name) if world_name else None
                if world_name and world_dir is None:
                    log(f"warning: world '{world_name}' not found; packs will install but won't be enabled.")

                scratch = Path(tempfile.mkdtemp(prefix="bedrock-mod-loader-gui-"))
                try:
                    _install_one(Path(source), game_dir, scratch, dev=dev, force=force, world_dir=world_dir, enable=enable, log=log)
                finally:
                    shutil.rmtree(scratch, ignore_errors=True)

                if world_name:
                    config.update_config(last_world=world_name)
            except PackError as exc:
                log(f"error: {exc}")
            log("Done.")
            self.after(0, self._refresh_packs)

        threading.Thread(target=work, daemon=True).start()

    # -- Library tab ------------------------------------------------------
    def _build_library_tab(self) -> None:
        frame = self.library_tab

        columns = ("kind", "name", "version", "uuid")
        self.pack_tree = ttk.Treeview(frame, columns=columns, show="headings", height=14, selectmode="browse")
        for col, label, width in (("kind", "Kind", 110), ("name", "Name", 220), ("version", "Version", 80), ("uuid", "UUID", 260)):
            self.pack_tree.heading(col, text=label)
            self.pack_tree.column(col, width=width, anchor="w")
        self.pack_tree.pack(fill="both", expand=True, pady=4)

        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=4)
        ttk.Button(btns, text="Refresh", command=self._refresh_packs).pack(side="left", padx=2)
        ttk.Button(btns, text="Enable in world", command=self._enable_selected).pack(side="left", padx=2)
        ttk.Button(btns, text="Disable in world", command=self._disable_selected).pack(side="left", padx=2)
        ttk.Button(btns, text="Uninstall", command=self._uninstall_selected).pack(side="left", padx=2)
        ttk.Button(btns, text="Export world loadout...", command=self._export_loadout).pack(side="left", padx=12)
        ttk.Button(btns, text="Apply loadout...", command=self._apply_loadout).pack(side="left", padx=2)

    def _refresh_packs(self) -> None:
        self.pack_tree.delete(*self.pack_tree.get_children())
        game_dir = self._optional_game_dir()
        if game_dir is None or not game_dir.is_dir():
            return
        for info in installer.iter_installed_packs(game_dir):
            self.pack_tree.insert("", "end", iid=info.uuid, values=(info.kind, info.name, _format_version(info.version), info.uuid))
        self.status_var.set(f"{len(self.pack_tree.get_children())} pack(s) found under {game_dir}")

    def _selected_pack(self):
        selection = self.pack_tree.selection()
        if not selection:
            messagebox.showinfo(APP_TITLE, "Select a pack in the list first.")
            return None
        game_dir = self._optional_game_dir()
        if game_dir is None:
            return None
        try:
            return installer.find_installed_pack(game_dir, selection[0])
        except PackError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return None

    def _selected_world_dir(self):
        game_dir = self._optional_game_dir()
        world_name = self.world_var.get().strip()
        if game_dir is None or not world_name:
            messagebox.showinfo(APP_TITLE, "Pick a world in the Install tab's World field first.")
            return None
        world_dir = discovery.find_world_by_name(game_dir, world_name)
        if world_dir is None:
            messagebox.showerror(APP_TITLE, f"World '{world_name}' not found.")
        return world_dir

    def _enable_selected(self) -> None:
        info = self._selected_pack()
        world_dir = self._selected_world_dir() if info is not None else None
        if info is None or world_dir is None:
            return
        changed = world_config.enable_pack_in_world(world_dir, info.kind, info.uuid, info.version)
        self.status_var.set(f"{'Enabled' if changed else 'Already enabled'}: {info.name} in '{world_dir.name}'")

    def _disable_selected(self) -> None:
        info = self._selected_pack()
        world_dir = self._selected_world_dir() if info is not None else None
        if info is None or world_dir is None:
            return
        changed = world_config.disable_pack_in_world(world_dir, info.kind, info.uuid)
        self.status_var.set(f"{'Disabled' if changed else 'Was not enabled'}: {info.name} in '{world_dir.name}'")

    def _uninstall_selected(self) -> None:
        info = self._selected_pack()
        if info is None:
            return
        if not messagebox.askyesno(APP_TITLE, f"Remove '{info.name}' from disk and from any world that enables it?"):
            return
        game_dir = self._optional_game_dir()
        for world_dir in discovery.list_worlds(game_dir):
            world_config.disable_pack_in_world(world_dir, info.kind, info.uuid)
        installer.uninstall_pack(info)
        self._refresh_packs()
        self.status_var.set(f"Removed {info.name}.")

    def _export_loadout(self) -> None:
        game_dir = self._optional_game_dir()
        world_dir = self._selected_world_dir()
        if game_dir is None or world_dir is None:
            return
        dest = filedialog.asksaveasfilename(title="Save loadout as", defaultextension=".json", initialfile=f"{world_dir.name}-loadout.json")
        if not dest:
            return
        installed_by_uuid = {p.uuid: p for p in installer.iter_installed_packs(game_dir)}
        data = loadout.build_loadout(world_dir, installed_by_uuid)
        loadout.write_loadout(data, Path(dest))
        self.status_var.set(f"Exported {len(data['packs'])} pack(s) to {dest}")

    def _apply_loadout(self) -> None:
        game_dir = self._optional_game_dir()
        world_dir = self._selected_world_dir()
        if game_dir is None or world_dir is None:
            return
        src = filedialog.askopenfilename(title="Choose a loadout JSON file")
        if not src:
            return
        data = loadout.read_loadout(Path(src))
        installed_by_uuid = {p.uuid: p for p in installer.iter_installed_packs(game_dir)}
        result = loadout.apply_loadout(data, world_dir, installed_by_uuid)
        if result.missing:
            names = ", ".join(entry.name or entry.uuid for entry in result.missing)
            messagebox.showwarning(APP_TITLE, f"Applied {len(result.applied)} pack(s). Missing (install these first): {names}")
        else:
            messagebox.showinfo(APP_TITLE, f"Applied {len(result.applied)} pack(s).")
        self._refresh_packs()

    # -- Watch tab --------------------------------------------------------
    def _build_watch_tab(self) -> None:
        frame = self.watch_tab

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=4)
        self.watch_dir_var = tk.StringVar()
        ttk.Label(row, text="Drop folder:").pack(side="left")
        ttk.Entry(row, textvariable=self.watch_dir_var, width=50).pack(side="left", padx=6, fill="x", expand=True)
        ttk.Button(row, text="Browse...", command=self._browse_watch_dir).pack(side="left")

        row2 = ttk.Frame(frame)
        row2.pack(fill="x", pady=4)
        self.watch_start_btn = ttk.Button(row2, text="Start watching", command=self._start_watch)
        self.watch_start_btn.pack(side="left", padx=2)
        self.watch_stop_btn = ttk.Button(row2, text="Stop", command=self._stop_watch, state="disabled")
        self.watch_stop_btn.pack(side="left", padx=2)
        ttk.Label(row2, text="Uses the World/options from the Install tab.").pack(side="left", padx=10)

        self.watch_log = tk.Text(frame, height=18, wrap="word")
        self.watch_log.pack(fill="both", expand=True, pady=4)
        self.watch_log.configure(state="disabled")

    def _browse_watch_dir(self) -> None:
        path = filedialog.askdirectory(title="Choose a drop folder to watch")
        if path:
            self.watch_dir_var.set(path)

    def _start_watch(self) -> None:
        drop_dir = self.watch_dir_var.get().strip()
        if not drop_dir:
            messagebox.showwarning(APP_TITLE, "Choose a folder to watch first.")
            return
        game_dir = self._require_game_dir()
        if game_dir is None:
            return
        Path(drop_dir).mkdir(parents=True, exist_ok=True)

        world_name = self.world_var.get().strip()
        dev = not self.prod_var.get()
        force = self.force_var.get()
        enable = self.enable_var.get()
        log = lambda message: self._log(self.watch_log, message)

        self._watch_stop.clear()
        self.watch_start_btn.config(state="disabled")
        self.watch_stop_btn.config(state="normal")
        log(f"Watching {drop_dir} ...")

        def handle(entry: Path) -> None:
            world_dir = discovery.find_world_by_name(game_dir, world_name) if world_name else None
            scratch = Path(tempfile.mkdtemp(prefix="bedrock-mod-loader-gui-watch-"))
            try:
                _install_one(entry, game_dir, scratch, dev=dev, force=force, world_dir=world_dir, enable=enable, log=log)
            except PackError as exc:
                log(f"  skipped {entry.name}: {exc}")
            finally:
                shutil.rmtree(scratch, ignore_errors=True)
            self.after(0, self._refresh_packs)

        def run() -> None:
            watcher.watch_forever(Path(drop_dir), handle, poll_interval=2.0, stop=self._watch_stop.is_set)
            log("Stopped watching.")

        self._watch_thread = threading.Thread(target=run, daemon=True)
        self._watch_thread.start()

    def _stop_watch(self) -> None:
        self._watch_stop.set()
        self.watch_start_btn.config(state="normal")
        self.watch_stop_btn.config(state="disabled")

    # -- Doctor tab -------------------------------------------------------
    def _build_doctor_tab(self) -> None:
        frame = self.doctor_tab
        ttk.Button(frame, text="Run diagnostics", command=self._run_doctor).pack(anchor="w", pady=4)
        self.doctor_text = tk.Text(frame, height=20, wrap="word")
        self.doctor_text.pack(fill="both", expand=True, pady=4)
        self.doctor_text.tag_configure(doctor.OK, foreground="#4caf50")
        self.doctor_text.tag_configure(doctor.WARN, foreground="#ffb300")
        self.doctor_text.tag_configure(doctor.ERROR, foreground="#f44336")
        self.doctor_text.configure(state="disabled")

    def _run_doctor(self) -> None:
        game_dir = self._optional_game_dir()
        results = doctor.run_diagnostics(game_dir)
        self.doctor_text.configure(state="normal")
        self.doctor_text.delete("1.0", "end")
        for result in results:
            self.doctor_text.insert("end", f"[{result.level}] {result.message}\n", result.level)
        self.doctor_text.configure(state="disabled")

    # -- shared helpers ----------------------------------------------------
    def _browse_game_dir(self) -> None:
        path = filedialog.askdirectory(title="Choose your com.mojang folder")
        if path:
            self.game_dir_var.set(path)
            self._refresh_worlds()
            self._refresh_packs()

    def _auto_detect_game_dir(self, silent: bool = False) -> None:
        found = discovery.find_game_dirs()
        if found:
            self.game_dir_var.set(str(found[0]))
            self._refresh_worlds()
            self._refresh_packs()
        elif not silent:
            messagebox.showinfo(APP_TITLE, "Couldn't auto-detect a com.mojang folder. Browse for it manually.")

    def _optional_game_dir(self) -> Optional[Path]:
        text = self.game_dir_var.get().strip()
        return Path(text) if text else None

    def _require_game_dir(self) -> Optional[Path]:
        game_dir = self._optional_game_dir()
        if game_dir is None:
            messagebox.showwarning(APP_TITLE, "Set a game directory first.")
            return None
        game_dir.mkdir(parents=True, exist_ok=True)
        return game_dir

    def _refresh_worlds(self) -> None:
        game_dir = self._optional_game_dir()
        if game_dir is None or not game_dir.is_dir():
            return
        names = [installer.world_display_name(w) for w in discovery.list_worlds(game_dir)]
        self.install_world_combo["values"] = names

    def _toggle_theme(self) -> None:
        self._dark = not self._dark
        _apply_theme(self, self._dark)

    def _log(self, widget: tk.Text, message: str) -> None:
        self._log_queue.put((widget, message))

    def _drain_log_queue(self) -> None:
        try:
            while True:
                widget, message = self._log_queue.get_nowait()
                widget.configure(state="normal")
                widget.insert("end", message + "\n")
                widget.see("end")
                widget.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(150, self._drain_log_queue)

    def _on_close(self) -> None:
        self._watch_stop.set()
        config.update_config(
            game_dir=self.game_dir_var.get().strip() or None,
            last_world=self.world_var.get().strip() or None,
            theme="dark" if self._dark else "light",
        )
        self.destroy()


def launch(game_dir: Optional[Path] = None) -> None:
    App(game_dir=game_dir).mainloop()
