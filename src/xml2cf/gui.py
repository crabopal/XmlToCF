"""Minimal Tk GUI for xml2cf (portable .exe double-click entry)."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext

from .compiler import compile_dump, inspect_dump, unpack_cf
from .types import supported_type_names

_FIXTURE_HINTS = [
    "tests/fixtures/cf-empty-infobase",
    "tests/fixtures/cf-small",
    "portable/fixtures/cf-empty-infobase",
    "portable/fixtures/cf-small",
]


def _find_fixture(name: str) -> Path | None:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "tests" / "fixtures" / name,
        here.parents[2] / "portable" / "fixtures" / name,
        Path.cwd() / "tests" / "fixtures" / name,
        Path.cwd() / "portable" / "fixtures" / name,
    ]
    for c in candidates:
        if (c / "Configuration.xml").is_file():
            return c
    return None


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("xml2cf — XML dump → .cf")
        self.geometry("720x480")
        self.dump_var = tk.StringVar()
        self.out_var = tk.StringVar(value=str(Path.cwd() / "out.cf"))

        frm = tk.Frame(self, padx=10, pady=10)
        frm.pack(fill=tk.BOTH, expand=True)

        tk.Label(frm, text="Dump folder (Configuration.xml):").grid(row=0, column=0, sticky="w")
        tk.Entry(frm, textvariable=self.dump_var, width=60).grid(row=1, column=0, sticky="we")
        tk.Button(frm, text="Browse…", command=self._browse_dump).grid(row=1, column=1, padx=4)

        tk.Label(frm, text="Output .cf:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        tk.Entry(frm, textvariable=self.out_var, width=60).grid(row=3, column=0, sticky="we")
        tk.Button(frm, text="Browse…", command=self._browse_out).grid(row=3, column=1, padx=4)

        btns = tk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=2, sticky="w", pady=10)
        tk.Button(btns, text="Inspect", command=self._inspect).pack(side=tk.LEFT, padx=2)
        tk.Button(btns, text="Compile", command=self._compile).pack(side=tk.LEFT, padx=2)
        tk.Button(btns, text="Unpack…", command=self._unpack).pack(side=tk.LEFT, padx=2)
        tk.Button(btns, text="Fixture: empty", command=lambda: self._load_fixture("cf-empty-infobase")).pack(
            side=tk.LEFT, padx=2
        )
        tk.Button(btns, text="Fixture: small", command=lambda: self._load_fixture("cf-small")).pack(
            side=tk.LEFT, padx=2
        )

        tk.Label(frm, text=f"Supported: {', '.join(supported_type_names())}").grid(
            row=5, column=0, columnspan=2, sticky="w"
        )
        self.log = scrolledtext.ScrolledText(frm, height=18)
        self.log.grid(row=6, column=0, columnspan=2, sticky="nsew", pady=8)
        frm.rowconfigure(6, weight=1)
        frm.columnconfigure(0, weight=1)

    def _log(self, msg: str) -> None:
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)

    def _browse_dump(self) -> None:
        path = filedialog.askdirectory(title="XML dump folder")
        if path:
            self.dump_var.set(path)

    def _browse_out(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Output .cf",
            defaultextension=".cf",
            filetypes=[("1C configuration", "*.cf"), ("All", "*.*")],
        )
        if path:
            self.out_var.set(path)

    def _load_fixture(self, name: str) -> None:
        found = _find_fixture(name)
        if not found:
            messagebox.showwarning("Fixture", f"{name} not found")
            return
        self.dump_var.set(str(found))
        self._log(f"Fixture: {found}")

    def _inspect(self) -> None:
        dump = self.dump_var.get().strip()
        if not dump:
            return
        try:
            info = inspect_dump(dump)
            self._log(json_dumps(info))
        except Exception as exc:
            self._log(f"ERROR: {exc}")

    def _compile(self) -> None:
        dump = self.dump_var.get().strip()
        out = self.out_var.get().strip()
        if not dump or not out:
            return

        def work() -> None:
            report = compile_dump(dump, out, allow_unsupported=False)
            self.after(0, lambda: self._log(report.to_json()))
            if report.ok:
                self.after(0, lambda: messagebox.showinfo("Compile", f"OK\n{report.output}"))
            else:
                self.after(0, lambda: messagebox.showerror("Compile", report.error or "failed"))

        threading.Thread(target=work, daemon=True).start()
        self._log("Compiling…")

    def _unpack(self) -> None:
        cf = filedialog.askopenfilename(filetypes=[("CF", "*.cf"), ("All", "*.*")])
        if not cf:
            return
        dest = filedialog.askdirectory(title="Unpack destination")
        if not dest:
            return
        try:
            path = unpack_cf(cf, dest)
            self._log(f"Unpacked → {path}")
        except Exception as exc:
            self._log(f"ERROR: {exc}")


def json_dumps(obj: object) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, indent=2)


def run_gui() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    run_gui()
