"""Method registry. Methods are added in build order (spec B11)."""

from __future__ import annotations

from jigsaw.features.color import ColorMatcher
from jigsaw.features.geometric import GeoMatcher
from jigsaw.features.gradient import GradMatcher
from jigsaw.methods.base import Matcher
from jigsaw.methods.hybrids import HybFilterMatcher, HybGCMatcher

_MATCHERS = {
    "GEO": GeoMatcher,
    "COLOR": ColorMatcher,
    "GRAD": GradMatcher,
    "HYB-GC": HybGCMatcher,
    "HYB-FILTER": HybFilterMatcher,
}


def get_matcher(name: str, reference: bool = False) -> Matcher:
    """The method's reference-free matcher, or its +R arm when ``reference`` is true."""
    from jigsaw.methods.reference_arms import ReferenceArm, RefOnlyMatcher

    if name == "REF-ONLY":
        if not reference:
            raise ValueError("REF-ONLY is defined only where a reference exists")
        return RefOnlyMatcher()
    try:
        base = _MATCHERS[name]()
    except KeyError:
        raise KeyError(f"method {name!r} is not implemented yet (available: {available()})") from None
    return ReferenceArm(base) if reference else base


def available() -> tuple[str, ...]:
    """Reference-free methods (REF-ONLY exists only with a reference)."""
    return tuple(sorted(_MATCHERS))
