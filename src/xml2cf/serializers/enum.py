from __future__ import annotations

from uuid import uuid4

from v8unpack import helper

from ..brace import deep_copy
from ..dump_parser import EnumValue, MetaObject
from ..types import ENUM_VALUE
from .base import SerializedObject, load_template, patch_identity, set_include, synonym_brace


def _enum_value_entry(ev: EnumValue) -> list:
    """Brace entry for one EnumValue (embedded include item)."""
    uid = ev.uuid or str(uuid4())
    return [
        "1",
        [
            "0",
            [
                "1",
                ["0", "0", uid],
                helper.str_encode(ev.name),
                synonym_brace(ev.synonym, ev.name),
                helper.str_encode(ev.comment or ""),
                "0",
                "0",
            ],
        ],
        "0",
    ]


def serialize_enum(obj: MetaObject) -> SerializedObject:
    tpl = load_template("Enum")
    header = deep_copy(tpl["header"])
    patch_identity(
        header,
        uuid=obj.uuid,
        name=obj.name,
        synonym=obj.synonym,
        comment=obj.comment,
    )
    # Generated type UUIDs at header[0][1][1..3]
    block = header[0][1]
    for i, cat in enumerate(["Ref", "Manager", "List"]):
        idx = 1 + i
        if cat in obj.generated and obj.generated[cat][0]:
            block[idx] = obj.generated[cat][0]

    entries = [_enum_value_entry(ev) for ev in obj.enum_values]
    set_include(header, ENUM_VALUE, entries)

    return SerializedObject(
        uuid=obj.uuid,
        type_name="Enum",
        name=obj.name,
        files={obj.uuid: header},
    )
