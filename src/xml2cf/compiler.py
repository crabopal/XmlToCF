"""Compile Designer XML dump → .cf (MVP, 32-bit skeleton layout)."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any

from v8unpack import helper

from . import container
from .dump_parser import ConfigurationDump, inspect_dump, parse_dump
from .header import patch_header
from .layout import current_layout, skeleton_cf_bytes
from .serializers import serialize_object
from .types import SUPPORTED, supported_type_names


@contextmanager
def _quiet_v8unpack():
    """Suppress v8unpack/tqdm console noise during compile/unpack."""
    os.environ.setdefault("TQDM_DISABLE", "1")
    buf = StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        yield


@dataclass
class CompileReport:
    ok: bool
    output: str
    layout: str
    configuration_uuid: str
    configuration_name: str
    objects: list[dict[str, Any]] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


class UnsupportedTypeError(ValueError):
    pass


def supported_types() -> list[str]:
    return supported_type_names()


def _write_serialized(folder: Path, files: dict[str, Any]) -> None:
    for name, payload in files.items():
        if isinstance(payload, dict) and payload.get("__nested__"):
            nested_dir = folder / name
            nested_dir.mkdir(parents=True, exist_ok=True)
            for sub, data in payload.items():
                if sub == "__nested__":
                    continue
                (nested_dir / sub).write_bytes(data if isinstance(data, bytes) else bytes(data))
        elif isinstance(payload, (bytes, bytearray)):
            (folder / name).write_bytes(payload)
        else:
            helper.brace_file_write(payload, str(folder), name)


def _purge_skeleton_objects(folder: Path, keep_uuids: set[str]) -> None:
    root = helper.brace_file_read(str(folder), "root")
    header_name = root[0][1]
    for path in list(folder.iterdir()):
        if path.name in {"root", "version", "versions", header_name}:
            continue
        if path.name in keep_uuids:
            continue
        # drop skeleton language if replaced
        if path.is_dir():
            shutil.rmtree(path)
        else:
            # keep only if uuid is in keep set (base name without suffix)
            base = path.name.split(".")[0]
            if base not in keep_uuids:
                path.unlink()


def compile_dump(
    dump_dir: str | Path,
    output_cf: str | Path,
    *,
    allow_unsupported: bool = False,
    work_dir: str | Path | None = None,
) -> CompileReport:
    """Compile a hierarchical XML dump into a .cf file.

    Stable public API. Returns a CompileReport (also usable as JSON via to_json()).
    """
    layout = current_layout()
    dump_dir = Path(dump_dir)
    output_cf = Path(output_cf)
    warnings: list[str] = []

    try:
        dump = parse_dump(dump_dir)
    except Exception as exc:
        return CompileReport(
            ok=False,
            output=str(output_cf),
            layout=layout.id,
            configuration_uuid="",
            configuration_name="",
            error=str(exc),
        )

    unsupported = sorted(t for t in dump.child_names if t not in SUPPORTED)
    if unsupported and not allow_unsupported:
        return CompileReport(
            ok=False,
            output=str(output_cf),
            layout=layout.id,
            configuration_uuid=dump.uuid,
            configuration_name=dump.name,
            unsupported=unsupported,
            error=(
                "Unsupported metadata types: "
                + ", ".join(unsupported)
                + ". Pass allow_unsupported=True / --allow-unsupported to skip them."
            ),
        )
    if unsupported and allow_unsupported:
        warnings.append(f"Skipping unsupported types: {', '.join(unsupported)}")

    objects = [o for o in dump.objects if o.type_name in SUPPORTED]
    tmp_root = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="xml2cf-"))
    own_tmp = work_dir is None
    try:
        with _quiet_v8unpack():
            staging = tmp_root / "cf"
            folder = container.unpack_bytes(skeleton_cf_bytes(), staging)

            includes: dict[str, list[str]] = {}
            written: list[dict[str, Any]] = []
            keep: set[str] = set()
            default_lang_uuid: str | None = None

            for obj in objects:
                serialized = serialize_object(obj)
                _write_serialized(folder, serialized.files)
                includes.setdefault(obj.type_name, []).append(obj.uuid)
                keep.add(obj.uuid)
                written.append(
                    {
                        "type": obj.type_name,
                        "name": obj.name,
                        "uuid": obj.uuid,
                        "attributes": len(obj.attributes),
                        "tabular_sections": len(obj.tabular_sections),
                        "enum_values": len(obj.enum_values),
                    }
                )
                if obj.type_name == "Language" and (
                    obj.name == dump.default_language
                    or (default_lang_uuid is None and dump.default_language == "")
                ):
                    default_lang_uuid = obj.uuid

            if default_lang_uuid is None:
                for obj in objects:
                    if obj.type_name == "Language":
                        default_lang_uuid = obj.uuid
                        break

            _purge_skeleton_objects(folder, keep)

            root = helper.brace_file_read(str(folder), "root")
            header_name = root[0][1]
            header = helper.brace_file_read(str(folder), header_name)
            patch_header(
                header,
                dump,
                includes=includes,
                default_language_uuid=default_lang_uuid,
            )
            helper.brace_file_write(header, str(folder), header_name)

            container.rebuild_versions(folder)
            container.pack_cf(folder, output_cf)

        return CompileReport(
            ok=True,
            output=str(output_cf.resolve()),
            layout=layout.id,
            configuration_uuid=dump.uuid,
            configuration_name=dump.name,
            objects=written,
            unsupported=unsupported,
            warnings=warnings,
        )
    except Exception as exc:
        return CompileReport(
            ok=False,
            output=str(output_cf),
            layout=layout.id,
            configuration_uuid=dump.uuid,
            configuration_name=dump.name,
            unsupported=unsupported,
            warnings=warnings,
            error=str(exc),
        )
    finally:
        if own_tmp and tmp_root.exists():
            shutil.rmtree(tmp_root, ignore_errors=True)


def unpack_cf(cf_path: str | Path, dest_dir: str | Path) -> Path:
    with _quiet_v8unpack():
        return container.unpack_cf(cf_path, dest_dir)


__all__ = [
    "CompileReport",
    "UnsupportedTypeError",
    "compile_dump",
    "inspect_dump",
    "supported_types",
    "unpack_cf",
]
