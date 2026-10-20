"""CF container layout versioning.

The embedded skeleton.cf uses the classic 32-bit container (marker 0x7FFFFFFF).
Platform 8.3.16+ can emit 64-bit containers (marker 0xFFFFFFFFFFFFFFFF) when the
configuration version is >= 80316. This MVP always produces the 32-bit layout.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources


LAYOUT_32BIT = "32bit"
LAYOUT_64BIT = "64bit"  # reserved; not produced by this MVP

# version file body used by the skeleton (v8unpack / classic CF)
SKELETON_VERSION_TOKEN = "216"


@dataclass(frozen=True)
class LayoutInfo:
    id: str
    description: str
    version_token: str
    address_bits: int


LAYOUTS = {
    LAYOUT_32BIT: LayoutInfo(
        id=LAYOUT_32BIT,
        description="Classic CF container (INT32 addresses, pre/compat 8.3.16 style)",
        version_token=SKELETON_VERSION_TOKEN,
        address_bits=32,
    ),
    LAYOUT_64BIT: LayoutInfo(
        id=LAYOUT_64BIT,
        description="64-bit CF container (UINT64 addresses, platform >= 8.3.16)",
        version_token="80316",
        address_bits=64,
    ),
}


def current_layout() -> LayoutInfo:
    return LAYOUTS[LAYOUT_32BIT]


def skeleton_cf_bytes() -> bytes:
    return resources.files("xml2cf").joinpath("data/skeleton.cf").read_bytes()
