"""Shared serializer utilities and template loading."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any
from uuid import uuid4

from v8unpack import helper

from ..brace import deep_copy, unquote
from ..dump_parser import LocalString, MetaObject


@dataclass
class SerializedObject:
    uuid: str
    type_name: str
    name: str
    files: dict[str, Any] = field(default_factory=dict)  # name -> brace tree OR bytes
    """Brace trees are written via helper.brace_file_write; bytes written raw."""


def load_template(name: str) -> dict[str, Any]:
    text = resources.files("xml2cf").joinpath(f"data/templates/{name}.json").read_text(
        encoding="utf-8"
    )
    return json.loads(text)


def new_uuid() -> str:
    return str(uuid4())


def synonym_brace(syn: LocalString, fallback_name: str = "") -> list:
    if not syn.items:
        return ["0"]
    parts: list[Any] = [str(len(syn.items))]
    for lang, content in syn.items.items():
        parts.append(helper.str_encode(lang))
        parts.append(helper.str_encode(content))
    return parts


def patch_identity(header_tree: list, *, uuid: str, name: str, synonym: LocalString, comment: str) -> None:
    """Replace the standard identity block inside a cloned object header.

    Most simple objects store identity at header[0][1][…][1] as:
    ["1", ["0","0", uuid|"в отдельном файле"], "\"Name\"", synonym, "\"comment\"", ...]
    Templates from v8unpack use 'в отдельном файле' placeholder for uuid in id.json mode;
    we put the real uuid into the object file and keep structure.
    """
    identity = _find_identity(header_tree)
    if identity is None:
        raise ValueError("identity block not found in template")
    # identity is ["1", ["0","0", ...], "\"Name\"", synonym, "\"comment\"", ...]
    identity[1][2] = "в отдельном файле"
    identity[2] = helper.str_encode(name)
    identity[3] = synonym_brace(synonym, name)
    identity[4] = helper.str_encode(comment or "")


def _find_identity(node: Any) -> list | None:
    if not isinstance(node, list):
        return None
    # Match ["1", ["0","0", x], "\"...\"", ...]
    if (
        len(node) >= 5
        and node[0] == "1"
        and isinstance(node[1], list)
        and len(node[1]) >= 3
        and node[1][0] == "0"
        and isinstance(node[2], str)
        and node[2].startswith('"')
    ):
        return node
    for child in node:
        found = _find_identity(child)
        if found is not None:
            return found
    return None


def replace_generated_uuids(header: list, obj: MetaObject, slots: list[str]) -> None:
    """Replace leading generated-type UUID slots in object header[0][1]."""
    block = header[0][1]
    # For Catalog: [count, uuid1..uuidN, identity, ...]
    # slots map to generated categories in order used by template
    for i, cat in enumerate(slots):
        idx = 1 + i
        if cat in obj.generated and obj.generated[cat][0]:
            block[idx] = obj.generated[cat][0]
        elif isinstance(block[idx], str) and len(block[idx]) == 36:
            # keep template or assign new
            if cat in obj.generated and obj.generated[cat][0]:
                block[idx] = obj.generated[cat][0]


def set_include(header: list, type_uuid: str, entries: list[Any]) -> None:
    """Set or replace a nested include [type_uuid, count, *entries]."""

    def walk(node: Any) -> bool:
        if not isinstance(node, list):
            return False
        if (
            len(node) >= 2
            and node[0] == type_uuid
            and isinstance(node[1], str)
            and node[1].isdigit()
        ):
            del node[2:]
            node[1] = str(len(entries))
            node.extend(entries)
            return True
        for child in node:
            if walk(child):
                return True
        return False

    if not walk(header):
        raise ValueError(f"include type {type_uuid} not found in template")


def module_container(module_text: str) -> dict[str, bytes]:
    """Build nested module files (info + text) for uuid.0 container content.

    When packing with recursive=False, nested modules must already be compressed
    containers. For MVP CommonModule we write a small nested container via v8unpack.
    """
    return {"text": module_text.encode("utf-8-sig"), "info": b"{1,\n{1,\n{0},\n{0}\n}\n}"}
