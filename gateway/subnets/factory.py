"""Adapter factory — maps netuid to adapter class and model names.

Used by lifespan to register only enabled subnets at startup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from gateway.subnets.sn1_text import SN1TextAdapter
from gateway.subnets.sn19_image import SN19ImageAdapter
from gateway.subnets.sn22_search import SN22SearchAdapter
from gateway.subnets.sn32_detect import SN32DetectionAdapter
from gateway.subnets.sn62_code import SN62CodeAdapter

if TYPE_CHECKING:
    from gateway.subnets.base import BaseAdapter

# Mapping: netuid -> (AdapterClass, model_names)
_ADAPTER_MAP: dict[int, tuple[type[BaseAdapter], list[str]]] = {
    1: (SN1TextAdapter, ["tao-sn1"]),
    19: (SN19ImageAdapter, ["tao-sn19"]),
    22: (SN22SearchAdapter, ["tao-sn22"]),
    32: (SN32DetectionAdapter, ["tao-sn32"]),
    62: (SN62CodeAdapter, ["tao-sn62"]),
}


def adapter_factory(netuid: int) -> BaseAdapter | None:
    """Create adapter instance for a given netuid. Returns None if unknown."""
    entry = _ADAPTER_MAP.get(netuid)
    if entry is None:
        return None
    cls, _ = entry
    return cls()


def get_model_names(netuid: int) -> list[str]:
    """Get model names for a netuid."""
    entry = _ADAPTER_MAP.get(netuid)
    if entry is None:
        return []
    _, names = entry
    return list(names)
