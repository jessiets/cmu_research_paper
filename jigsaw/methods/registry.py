"""Method registry. Methods are added in build order (spec B11)."""

from __future__ import annotations

from jigsaw.features.color import ColorMatcher
from jigsaw.features.geometric import GeoMatcher
from jigsaw.methods.base import Matcher

_MATCHERS = {
    "GEO": GeoMatcher,
    "COLOR": ColorMatcher,
}


def get_matcher(name: str) -> Matcher:
    try:
        return _MATCHERS[name]()
    except KeyError:
        raise KeyError(f"method {name!r} is not implemented yet (available: {sorted(_MATCHERS)})") from None


def available() -> tuple[str, ...]:
    return tuple(sorted(_MATCHERS))
