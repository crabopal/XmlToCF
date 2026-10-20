from __future__ import annotations

from ..brace import deep_copy
from ..dump_parser import MetaObject
from .base import SerializedObject, load_template, patch_identity


def serialize_constant(obj: MetaObject) -> SerializedObject:
    tpl = load_template("Constant")
    header = deep_copy(tpl["header"])
    patch_identity(
        header,
        uuid=obj.uuid,
        name=obj.name,
        synonym=obj.synonym,
        comment=obj.comment,
    )
    return SerializedObject(
        uuid=obj.uuid,
        type_name="Constant",
        name=obj.name,
        files={obj.uuid: header},
    )
