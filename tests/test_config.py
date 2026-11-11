from pathlib import Path

import pytest

from jigsaw.config import load_config


ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    ("name", "count"),
    [("pilot", 3), ("main", 20)],
)
def test_loads_project_configs(name: str, count: int) -> None:
    config = load_config(ROOT / "configs" / f"{name}.yaml")

    assert config.profile == name
    assert config.expected_image_count == count
    assert len(config.source_images) == count
    assert config.master_seed == 20261106
    assert config.pitch_px == 64
    assert config.grids == ((6, 9), (12, 18), (20, 30))
    assert config.complexity_levels == (0, 50)
    assert config.wear_levels_px == (0, 1)


def test_rejects_wrong_pilot_image_count(tmp_path: Path) -> None:
    config_path = tmp_path / "pilot.yaml"
    config_path.write_text(
        (ROOT / "configs" / "pilot.yaml")
        .read_text(encoding="utf-8")
        .replace("expected_image_count: 3", "expected_image_count: 2"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="pilot expected_image_count must be 3"):
        load_config(config_path)


def test_rejects_unknown_configuration_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.yaml"
    config_path.write_text(
        (ROOT / "configs" / "pilot.yaml").read_text(encoding="utf-8")
        + "unapproved_default: true\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown keys: unapproved_default"):
        load_config(config_path)


def test_rejects_duplicate_selected_images(tmp_path: Path) -> None:
    config_path = tmp_path / "pilot.yaml"
    config_path.write_text(
        (ROOT / "configs" / "pilot.yaml")
        .read_text(encoding="utf-8")
        .replace(
            "  - 0251.png\n",
            "  - 0269.png\n",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source_images must not contain duplicates"):
        load_config(config_path)


def test_rejects_invalid_grid(tmp_path: Path) -> None:
    config_path = tmp_path / "pilot.yaml"
    config_path.write_text(
        (ROOT / "configs" / "pilot.yaml")
        .read_text(encoding="utf-8")
        .replace("[6, 9]", "[6, 0]"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="grid rows and columns must be positive"):
        load_config(config_path)


def test_configs_match_seeded_selection() -> None:
    import json

    selection = json.loads((ROOT / "configs" / "image_selection.json").read_text(encoding="utf-8"))
    pilot = load_config(ROOT / "configs" / "pilot.yaml")
    main = load_config(ROOT / "configs" / "main.yaml")
    assert list(pilot.source_images) == selection["pilot"]
    assert list(main.source_images) == selection["main"]
    assert not set(pilot.source_images) & set(main.source_images)
