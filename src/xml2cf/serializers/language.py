from __future__ import annotations

from v8unpack import helper

from ..brace import deep_copy
from ..dump_parser import MetaObject
from .base import SerializedObject, load_template, patch_identity


def serialize_language(obj: MetaObject) -> SerializedObject:
    tpl = load_template("Language")
    header = deep_copy(tpl["header"])
    patch_identity(
        header,
        uuid=obj.uuid,
        name=obj.name,
        synonym=obj.synonym,
        comment=obj.comment,
    )
    code = obj.props.get("LanguageCode") or obj.props.get("Code") or "ru"
    try:
        header[0][1][2] = helper.str_encode(code)
    except Exception:
        pass
    return SerializedObject(
        uuid=obj.uuid,
        type_name="Language",
        name=obj.name,
        files={obj.uuid: header},
    )
