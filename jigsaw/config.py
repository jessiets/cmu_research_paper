from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


_REQUIRED_KEYS = {
    "profile",
    "python_version",
    "source_dir",
    "source_images",
    "expected_image_count",
    "grids",
    "complexity_levels",
    "wear_levels_px",
    "reference_levels",
    "methods",
    "timing_repetitions",
    "master_seed",
    "pitch_px",
}
_METHODS = {"GEO", "COLOR", "GRAD", "HYB-GC", "HYB-FILTER", "REF-ONLY"}
_REFERENCES = {"none", "exact", "degraded"}
_PROFILE_IMAGE_COUNTS = {"pilot": 3, "main": 20}


@dataclass(frozen=True)
class ExperimentConfig:
    profile: str
    python_version: str
    source_dir: str
    source_images: tuple[str, ...]
    expected_image_count: int
    grids: tuple[tuple[int, int], ...]
    complexity_levels: tuple[int, ...]
    wear_levels_px: tuple[int, ...]
    reference_levels: tuple[str, ...]
    methods: tuple[str, ...]
    timing_repetitions: int
    master_seed: int
    pitch_px: int


def load_config(path: str | Path) -> ExperimentConfig:
    config_path = Path(path)
    try:
        with config_path.open(encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Configuration in {config_path} must be a mapping")

    missing = _REQUIRED_KEYS - data.keys()
    extra = data.keys() - _REQUIRED_KEYS
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing keys: {', '.join(sorted(missing))}")
        if extra:
            details.append(f"unknown keys: {', '.join(sorted(extra))}")
        raise ValueError(f"Invalid configuration in {config_path}: {'; '.join(details)}")

    profile = _string(data, "profile")
    if profile not in _PROFILE_IMAGE_COUNTS:
        raise ValueError(f"profile must be one of {', '.join(_PROFILE_IMAGE_COUNTS)}")
    python_version = _string(data, "python_version")
    if python_version != "3.13":
        raise ValueError("python_version must be '3.13' to match the pinned environment")
    source_dir = _string(data, "source_dir")
    source_images = _string_tuple(data, "source_images")
    if source_images and len(source_images) != _PROFILE_IMAGE_COUNTS[profile]:
        raise ValueError(
            f"{profile} requires exactly {_PROFILE_IMAGE_COUNTS[profile]} source images"
        )
    if len(set(source_images)) != len(source_images):
        raise ValueError("source_images must not contain duplicates")

    expected_image_count = _integer(data, "expected_image_count", minimum=1)
    if expected_image_count != _PROFILE_IMAGE_COUNTS[profile]:
        raise ValueError(
            f"{profile} expected_image_count must be {_PROFILE_IMAGE_COUNTS[profile]}"
        )

    grids_raw = data["grids"]
    if not isinstance(grids_raw, list) or not grids_raw:
        raise ValueError("grids must be a non-empty list of [rows, columns]")
    grids: list[tuple[int, int]] = []
    for grid in grids_raw:
        if not isinstance(grid, list) or len(grid) != 2:
            raise ValueError("each grid must contain exactly [rows, columns]")
        rows, columns = grid
        if not _is_positive_integer(rows) or not _is_positive_integer(columns):
            raise ValueError("grid rows and columns must be positive integers")
        grids.append((rows, columns))
    if len(set(grids)) != len(grids):
        raise ValueError("grids must not contain duplicates")

    complexity_levels = _integer_tuple(data, "complexity_levels", minimum=0)
    if any(value > 100 for value in complexity_levels):
        raise ValueError("complexity_levels must be percentages from 0 to 100")
    wear_levels_px = _integer_tuple(data, "wear_levels_px", minimum=0)
    reference_levels = _string_tuple(data, "reference_levels")
    if not reference_levels or not set(reference_levels) <= _REFERENCES:
        raise ValueError(f"reference_levels must use {sorted(_REFERENCES)}")
    methods = _string_tuple(data, "methods")
    if not methods or not set(methods) <= _METHODS:
        raise ValueError(f"methods must use {sorted(_METHODS)}")
    timing_repetitions = _integer(data, "timing_repetitions", minimum=1)
    master_seed = _integer(data, "master_seed", minimum=0)
    if master_seed != 20261106:
        raise ValueError("master_seed must be 20261106 (decision D4)")
    pitch_px = _integer(data, "pitch_px", minimum=1)
    if pitch_px != 64:
        raise ValueError("pitch_px must be 64 (spec A3)")

    return ExperimentConfig(
        profile=profile,
        python_version=python_version,
        source_dir=source_dir,
        source_images=source_images,
        expected_image_count=expected_image_count,
        grids=tuple(grids),
        complexity_levels=complexity_levels,
        wear_levels_px=wear_levels_px,
        reference_levels=reference_levels,
        methods=methods,
        timing_repetitions=timing_repetitions,
        master_seed=master_seed,
        pitch_px=pitch_px,
    )


def _string(data: dict[str, Any], key: str) -> str:
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _string_tuple(data: dict[str, Any], key: str) -> tuple[str, ...]:
    value = data[key]
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{key} must be a list of non-empty strings")
    return tuple(value)


def _integer(data: dict[str, Any], key: str, *, minimum: int) -> int:
    value = data[key]
    if not _is_integer(value) or value < minimum:
        raise ValueError(f"{key} must be an integer greater than or equal to {minimum}")
    return value


def _integer_tuple(data: dict[str, Any], key: str, *, minimum: int) -> tuple[int, ...]:
    value = data[key]
    if not isinstance(value, list) or any(
        not _is_integer(item) or item < minimum for item in value
    ):
        raise ValueError(f"{key} must be a list of integers greater than or equal to {minimum}")
    if not value:
        raise ValueError(f"{key} must not be empty")
    if len(set(value)) != len(value):
        raise ValueError(f"{key} must not contain duplicates")
    return tuple(value)


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_positive_integer(value: Any) -> bool:
    return _is_integer(value) and value > 0
