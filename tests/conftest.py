"""Shared fixtures for tombola-cards unit tests."""

from __future__ import annotations

import sys

if sys.platform == "win32":
    import pathlib

    pathlib.PosixPath = pathlib.WindowsPath
    if pathlib.Path.__name__ == "PosixPath":
        pathlib.Path = pathlib.WindowsPath

import os
from pathlib import Path

import pytest
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_TEMPLATE = PROJECT_ROOT / "templates" / "raffle.png"


def pytest_sessionstart(session) -> None:
    os.chdir(PROJECT_ROOT)


def pytest_sessionfinish(session, exitstatus) -> None:
    os.chdir(PROJECT_ROOT)


def pytest_collection_modifyitems(config, items) -> None:
    non_gui = [item for item in items if "gui" not in item.keywords]
    gui = [item for item in items if "gui" in item.keywords]
    items[:] = non_gui + gui


@pytest.fixture
def sample_template() -> Path:
    if not SAMPLE_TEMPLATE.exists():
        pytest.skip(f"Sample template not found: {SAMPLE_TEMPLATE}")
    return SAMPLE_TEMPLATE


@pytest.fixture
def tiny_rgb_image() -> Image.Image:
    return Image.new("RGB", (800, 400), color=(20, 30, 60))


@pytest.fixture
def digits_dir(tmp_path: Path) -> Path:
    digits_path = tmp_path / "numbers"
    digits_path.mkdir()
    for digit in "0123456789":
        image = Image.new("RGBA", (40, 80), color=(0, 0, 0, 0))
        for x in range(8, 32):
            for y in range(10, 70):
                image.putpixel((x, y), (255, 255, 255, 255))
        image.save(digits_path / f"{digit}.png")
    return digits_path
