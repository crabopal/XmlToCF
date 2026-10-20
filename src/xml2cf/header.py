"""Patch Configuration header (name, UUID, compat, includes, InternalInfo groups)."""

from __future__ import annotations

import re
from typing import Any

from v8unpack import helper

from .dump_parser import ConfigurationDump, LocalString
from .types import (
    GROUP_ACCOUNTING,
    GROUP_CALCULATION,
    GROUP_DATASOURCE,
    GROUP_DOCFLOW,
    GROUP_GENERAL,
    GROUP_INTEGRATION,
    GROUP_MAIN,
    SUPPORTED,
)

# CompatibilityMode Version8_3_10 -> 80310
_COMPAT_RE = re.compile(r"Version8_(\d+)_(\d+)", re.I)
_COMPAT_RE_5 = re.compile(r"Version8_(\d+)_(\d+)_?(\d+)?", re.I)


def compat_to_int(mode: str) -> str | None:
    if not mode:
        return None
    m = re.search(r"Version8_(\d+)_(\d+)", mode)
    if not m:
        return None
    major, minor = int(m.group(1)), int(m.group(2))
    return f"{major}{minor:02d}{0:02d}"  # e.g. 8_3_10 -> 80300? 
    # Platform uses XYYZZ: 8.3.10 = 80310
    # Actually from docs: 8.3.6 = 80306 — so major*10000 + minor*100 + patch
    # Version8_3_10 -> 80310; Version8_3_24 -> 80324
    # Our regex only has two numbers for Version8_3_10


def compat_mode_to_cf(mode: str) -> str | None:
    if not mode:
        return None
    # Version8_3_24 or Version8_5_1
    m = re.search(r"Version8_(\d+)_(\d+)(?:_(\d+))?", mode)
    if not m:
        return None
    a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    if a == 8 and b >= 3 and c == 0 and m.group(3) is None:
        # Version8_3_24 → groups (8),(3),(24) if three-part; two-part Version8_5_1 → 80501
        pass
    # Prefer three-component: Version8_3_24
    parts = mode.replace("Version", "").split("_")
    # ["8", "3", "24"] or ["8", "5", "1"]
    nums = [int(p) for p in parts if p.isdigit()]
    if len(nums) >= 3:
        return f"{nums[0]}{nums[1]:02d}{nums[2]:02d}"
    if len(nums) == 2:
        return f"{nums[0]}{nums[1]:02d}00"
    return None


def _synonym_brace(syn: LocalString) -> list:
    if not syn.items:
        return ["0"]
    parts: list[Any] = [str(len(syn.items))]
    for lang, content in syn.items.items():
        parts.append(helper.str_encode(lang))
        parts.append(helper.str_encode(content))
    return parts


def _find_and_set_type_include(header: list, type_uuid: str, object_uuids: list[str]) -> bool:
    found = False

    def walk(node: Any) -> None:
        nonlocal found
        if not isinstance(node, list):
            return
        if (
            len(node) >= 2
            and node[0] == type_uuid
            and isinstance(node[1], str)
            and node[1].isdigit()
        ):
            del node[2:]
            node[1] = str(len(object_uuids))
            node.extend(object_uuids)
            found = True
            return
        for child in node:
            walk(child)

    walk(header)
    return found


def _patch_identity_props(header: list, dump: ConfigurationDump) -> None:
    """Patch name/synonym/comment/vendor/version/default language/compat inside props."""

    def walk(node: Any) -> None:
        if not isinstance(node, list):
            return
        # Identity: ["1", ["0","0", uuid], "\"Name\"", synonym, "\"comment\"", ...]
        if (
            len(node) >= 5
            and node[0] == "1"
            and isinstance(node[1], list)
            and len(node[1]) >= 3
            and node[1][0] == "0"
            and isinstance(node[2], str)
            and node[2].startswith('"')
        ):
            node[1][2] = dump.uuid
            node[2] = helper.str_encode(dump.name)
            node[3] = _synonym_brace(dump.synonym)
            node[4] = helper.str_encode(dump.comment or "")
        for child in node:
            walk(child)

    walk(header)

    # Vendor / Version / Update catalog — quoted strings near props
    # Default language UUID is set by caller after languages are known
    compat = compat_mode_to_cf(dump.compatibility_mode)
    if compat:

        def set_compat(node: Any) -> None:
            if not isinstance(node, list):
                return
            for i, x in enumerate(node):
                if isinstance(x, str) and x.isdigit() and len(x) == 5 and x.startswith("80"):
                    node[i] = compat
                else:
                    set_compat(x)

        set_compat(header)

    # Vendor / Version string fields: replace known template placeholders
    def replace_str(node: Any, old: str, new: str) -> None:
        if not isinstance(node, list):
            return
        for i, x in enumerate(node):
            if x == helper.str_encode(old) or x == f'"{old}"':
                node[i] = helper.str_encode(new)
            else:
                replace_str(x, old, new)

    if dump.vendor:
        replace_str(header, "Поставщик конфигурации", dump.vendor)
    if dump.version:
        replace_str(header, "Версия конфигурации", dump.version)


def _patch_internal_info_groups(header: list, dump: ConfigurationDump) -> None:
    """Update group ObjectIds from Configuration InternalInfo ContainedObject list."""
    # Groups appear as [group_uuid, [version, […, ["0","0", objectId], …], …]]
    for class_id, object_id in dump.contained.items():

        def walk(node: Any, target_class: str = class_id, oid: str = object_id) -> None:
            if not isinstance(node, list):
                return
            if node and node[0] == target_class and len(node) >= 2:
                # search for ["0","0", uuid] inside this group
                def patch_oid(n: Any) -> bool:
                    if (
                        isinstance(n, list)
                        and len(n) >= 3
                        and n[0] == "0"
                        and n[1] == "0"
                        and isinstance(n[2], str)
                        and len(n[2]) == 36
                    ):
                        n[2] = oid
                        return True
                    if isinstance(n, list):
                        for c in n:
                            if patch_oid(c):
                                return True
                    return False

                patch_oid(node[1] if len(node) > 1 else node)
            for child in node:
                walk(child, target_class, oid)

        walk(header)


def _set_default_language(header: list, language_uuid: str) -> None:
    """Replace the default-language UUID slot in configuration props."""

    # In skeleton props the default language appears as a bare UUID among zeros.
    # Strategy: find Language include uuids and set the known prop slot.
    # From Configuration.get_decode_header path, default language is at a fixed index.
    # Safer: replace e3991838... (skeleton Russian) if present; else first non-zero UUID
    # after detailed info strings.

    SKELETON_LANG = "e3991838-36de-456b-8b93-fda91f9ea1be"

    def walk(node: Any) -> None:
        if not isinstance(node, list):
            return
        for i, x in enumerate(node):
            if x == SKELETON_LANG:
                node[i] = language_uuid
            else:
                walk(x)

    walk(header)


def _set_configuration_uuid(header: list, uuid: str) -> None:
    """Set the configuration object UUID in the primary identity block.

    Shape: … ["1", ["50"|count, ["0", ["1", ["0","0", UUID], "\"Name\"", …]]]]
    """

    def walk(node: Any) -> bool:
        if not isinstance(node, list):
            return False
        # Match inner identity ["1", ["0","0", uuid], "\"Name\"", …]
        if (
            len(node) >= 5
            and node[0] == "1"
            and isinstance(node[1], list)
            and len(node[1]) >= 3
            and node[1][0] == "0"
            and node[1][1] == "0"
            and isinstance(node[2], str)
            and node[2].startswith('"')
        ):
            node[1][2] = uuid
            return True
        for child in node:
            if walk(child):
                return True
        return False

    walk(header)


def patch_header(
    header: list,
    dump: ConfigurationDump,
    *,
    includes: dict[str, list[str]],
    default_language_uuid: str | None,
) -> None:
    """In-place patch of configuration brace header."""
    _patch_internal_info_groups(header, dump)
    _patch_identity_props(header, dump)
    # Re-apply configuration UUID after InternalInfo patch (which also touches ["0","0",uuid])
    _set_configuration_uuid(header, dump.uuid)

    for type_name, uuids in includes.items():
        meta = SUPPORTED[type_name]
        _find_and_set_type_include(header, meta.type_uuid, uuids)

    # Zero-out supported types that are absent
    present = set(includes)
    for type_name, meta in SUPPORTED.items():
        if type_name not in present:
            _find_and_set_type_include(header, meta.type_uuid, [])

    if default_language_uuid:
        _set_default_language(header, default_language_uuid)
