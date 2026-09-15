"""Stable Stage 3 G adapter surface for H and main integration."""
from collections.abc import Mapping, Sequence
from typing import Any


PROFILE = "DYNAMIC_FIXED_AABB_TRANSLATION_V01"
INTERFACE_VERSION = "0.1.0"


def evaluate_dynamic_evidence(
    spec: Mapping[str, Any],
    trusted_events: Sequence[Mapping[str, Any]],
    independent_replay: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate declared dynamic rigid-body pairs over one trusted trace.

    The implementation is deliberately imported lazily so this small adapter
    stays stable while the candidate implementation is validated.
    """
    from dynamic_geometry_v01 import evaluate_dynamic_evidence as implementation

    return implementation(spec, trusted_events, independent_replay)

