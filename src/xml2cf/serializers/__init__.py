from __future__ import annotations

from .base import SerializedObject
from .catalog import serialize_catalog
from .common_module import serialize_common_module
from .constant import serialize_constant
from .enum import serialize_enum
from .language import serialize_language
from ..dump_parser import MetaObject

_SERIALIZERS = {
    "Language": serialize_language,
    "CommonModule": serialize_common_module,
    "Constant": serialize_constant,
    "Enum": serialize_enum,
    "Catalog": serialize_catalog,
}


def serialize_object(obj: MetaObject) -> SerializedObject:
    try:
        fn = _SERIALIZERS[obj.type_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported type: {obj.type_name}") from exc
    return fn(obj)
