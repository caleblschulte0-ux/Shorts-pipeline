"""Review-only capability studio for future Shorts-pipeline integrations.

The package is intentionally disconnected from production. It imports only the
Python standard library, performs no network calls by default, and has no uploader,
workflow, OAuth, renderer, secret, or production-state access.
"""

from .contracts import CapabilityKind, Maturity, Verdict
from .registry import CapabilityRegistry, default_registry

__all__ = ["CapabilityKind", "Maturity", "Verdict", "CapabilityRegistry", "default_registry"]
