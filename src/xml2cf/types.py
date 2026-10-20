"""Metadata type registry for MVP support matrix."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetaType:
    name: str  # Designer XML element / ChildObjects tag
    type_uuid: str  # CF include type UUID
    group: str  # InternalInfo / configuration group
    folder: str  # dump folder name


# Group UUIDs (Configuration InternalInfo ContainedObject ClassId)
GROUP_GENERAL = "9cd510cd-abfc-11d4-9434-004095e12fc7"
GROUP_MAIN = "9fcd25a0-4822-11d4-9414-008048da11f9"
GROUP_ACCOUNTING = "e3687481-0a87-462c-a166-9f34594f9bba"
GROUP_CALCULATION = "9de14907-ec23-4a07-96f0-85521cb6b53b"
GROUP_DOCFLOW = "51f2d5d8-ea4d-4064-8892-82951750031e"
GROUP_DATASOURCE = "e68182ea-4237-4383-967f-90c1e3370bc7"
GROUP_INTEGRATION = "fb282519-d103-4dd3-bc12-cb271d631dfc"

SUPPORTED: dict[str, MetaType] = {
    "Language": MetaType(
        "Language",
        "9cd510ce-abfc-11d4-9434-004095e12fc7",
        GROUP_GENERAL,
        "Languages",
    ),
    "CommonModule": MetaType(
        "CommonModule",
        "0fe48980-252d-11d6-a3c7-0050bae0a776",
        GROUP_GENERAL,
        "CommonModules",
    ),
    "Constant": MetaType(
        "Constant",
        "0195e80c-b157-11d4-9435-004095e12fc7",
        GROUP_MAIN,
        "Constants",
    ),
    "Enum": MetaType(
        "Enum",
        "f6a80749-5ad7-400b-8519-39dc5dff2542",
        GROUP_MAIN,
        "Enums",
    ),
    "Catalog": MetaType(
        "Catalog",
        "cf4abea6-37b2-11d4-940f-008048da11f9",
        GROUP_MAIN,
        "Catalogs",
    ),
}

# Nested child type UUIDs embedded in object headers
CATALOG_ATTRIBUTE = "cf4abea7-37b2-11d4-940f-008048da11f9"
CATALOG_TABULAR_SECTION = "932159f9-95b2-4e76-a8dd-8849fe5c5ded"
ENUM_VALUE = "bee0a08c-07eb-40c0-8544-5c364c171465"

# Configuration root type (not in ChildObjects)
CONFIGURATION_TYPE = "9cd510cd-abfc-11d4-9434-004095e12fc7"


def supported_type_names() -> list[str]:
    return sorted(SUPPORTED.keys())
