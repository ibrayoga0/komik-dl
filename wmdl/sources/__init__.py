"""
Comic sources package for wmdl
"""

from .base import BaseSource
from .shinigami import ShinigamiSource
from .softkomik import SoftkomikSource
from .komiku import KomikuSource
from .registry import registry, SourceRegistry

__all__ = [
    "BaseSource",
    "ShinigamiSource",
    "SoftkomikSource",
    "KomikuSource",
    "registry",
    "SourceRegistry",
]
