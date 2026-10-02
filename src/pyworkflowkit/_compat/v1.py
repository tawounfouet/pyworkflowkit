"""Explicit access to the legacy 1.x compatibility contract.

This module is intentionally one-way: migration tooling may depend on it, while
canonical V2 implementation modules must not import it.
"""

import pyworkflowkit.compatibility as legacy_compatibility

__all__ = ["legacy_compatibility"]
