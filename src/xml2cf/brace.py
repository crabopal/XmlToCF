"""Brace-format helpers (1C internal metadata serialization)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from v8unpack import helper


BraceTree = list[Any]


def read_file(directory: str | Path, name: str) -> BraceTree:
    return helper.brace_file_read(str(directory), name)


def write_file(data: BraceTree, directory: str | Path, name: str) -> None:
    helper.brace_file_write(data, str(directory), name)


def loads(text: str) -> BraceTree:
    """Parse brace text via v8unpack JSON round-trip encoder helpers."""
    # v8unpack stores decoded trees as nested lists of strings
    return helper.decode_brace(text) if hasattr(helper, "decode_brace") else _decode(text)


def dumps(data: BraceTree) -> str:
    if hasattr(helper, "encode_brace"):
        return helper.encode_brace(data)
    # Fall back: write via temp
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        write_file(data, td, "x")
        raw = Path(td, "x").read_bytes()
        return raw.decode("utf-8-sig")


def _decode(text: str) -> BraceTree:
    """Minimal brace decoder for tests; prefer helper.brace_file_read for files."""
    from v8unpack.json_container_decoder import JsonContainerDecoder

    return JsonContainerDecoder().decode_root_object(text)


def deep_copy(data: Any) -> Any:
    return json.loads(json.dumps(data))


def quote(value: str) -> str:
    return helper.str_encode(value) if hasattr(helper, "str_encode") else f'"{value}"'


def unquote(value: str) -> str:
    if isinstance(value, str) and len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value
