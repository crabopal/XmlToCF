"""Command-line interface for xml2cf."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .compiler import compile_dump, inspect_dump, supported_types, unpack_cf
from .layout import current_layout


def _cmd_inspect(args: argparse.Namespace) -> int:
    info = inspect_dump(args.dump)
    info["layout_target"] = current_layout().id
    info["supported_types"] = supported_types()
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def _cmd_compile(args: argparse.Namespace) -> int:
    report = compile_dump(
        args.dump,
        args.output,
        allow_unsupported=args.allow_unsupported,
    )
    if args.json:
        print(report.to_json())
    else:
        if report.ok:
            print(f"OK → {report.output}")
            print(f"layout={report.layout} name={report.configuration_name} uuid={report.configuration_uuid}")
            print(f"objects={len(report.objects)}")
            for w in report.warnings:
                print(f"warning: {w}", file=sys.stderr)
        else:
            print(f"ERROR: {report.error}", file=sys.stderr)
            if report.unsupported:
                print(f"unsupported: {', '.join(report.unsupported)}", file=sys.stderr)
    return 0 if report.ok else 1


def _cmd_unpack(args: argparse.Namespace) -> int:
    dest = unpack_cf(args.cf, args.dest)
    print(f"Unpacked → {dest}")
    return 0


def _cmd_types(_: argparse.Namespace) -> int:
    print(json.dumps({"supported": supported_types(), "layout": current_layout().id}, indent=2))
    return 0


def _cmd_gui(_: argparse.Namespace) -> int:
    from .gui import run_gui

    run_gui()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="xml2cf",
        description="Compile 1C Designer XML dumps to .cf without the platform",
    )
    p.add_argument("--version", action="version", version=f"xml2cf {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("inspect", help="Inspect a dump (JSON)")
    s.add_argument("dump", type=Path)
    s.set_defaults(func=_cmd_inspect)

    s = sub.add_parser("compile", help="Compile dump → .cf")
    s.add_argument("dump", type=Path)
    s.add_argument("output", type=Path)
    s.add_argument(
        "--allow-unsupported",
        action="store_true",
        help="Skip unsupported types instead of failing",
    )
    s.add_argument("--json", action="store_true", help="Emit CompileReport JSON")
    s.set_defaults(func=_cmd_compile)

    s = sub.add_parser("unpack", help="Unpack .cf to brace files")
    s.add_argument("cf", type=Path)
    s.add_argument("dest", type=Path)
    s.set_defaults(func=_cmd_unpack)

    s = sub.add_parser("types", help="List supported metadata types")
    s.set_defaults(func=_cmd_types)

    s = sub.add_parser("gui", help="Open Tk GUI")
    s.set_defaults(func=_cmd_gui)

    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Double-click / no args → GUI on Windows-style usage
    if not argv:
        argv = ["gui"]
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
