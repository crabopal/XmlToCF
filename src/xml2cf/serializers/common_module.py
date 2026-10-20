from __future__ import annotations

from ..brace import deep_copy
from ..dump_parser import MetaObject
from .base import SerializedObject, load_template, patch_identity

_BOOL_PROPS = [
    ("Global", 2),
    ("ClientManagedApplication", 3),
    ("Server", 4),
    ("ExternalConnection", 5),
    ("ClientOrdinaryApplication", 6),
    ("ServerCall", 7),
]


def serialize_common_module(obj: MetaObject) -> SerializedObject:
    tpl = load_template("CommonModule")
    header = deep_copy(tpl["header"])
    patch_identity(
        header,
        uuid=obj.uuid,
        name=obj.name,
        synonym=obj.synonym,
        comment=obj.comment,
    )
    flags = header[0][1]
    for prop, idx in _BOOL_PROPS:
        if prop in obj.props and idx < len(flags):
            flags[idx] = "1" if obj.props[prop].lower() == "true" else "0"

    module_text = ""
    if obj.module_path and obj.module_path.is_file():
        module_text = obj.module_path.read_text(encoding="utf-8-sig")

    nested = {
        "__nested__": True,
        "info": b'\xef\xbb\xbf{3,1,0,"",0}',
        "text": ("\ufeff" + module_text).encode("utf-8"),
    }
    return SerializedObject(
        uuid=obj.uuid,
        type_name="CommonModule",
        name=obj.name,
        files={obj.uuid: header, f"{obj.uuid}.0": nested},
    )
