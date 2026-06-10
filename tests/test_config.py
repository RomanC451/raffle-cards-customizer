import importlib
import sys
from pathlib import Path

import bingo_cards.config as config


def test_paths_exist_in_dev_mode():
    assert config.BUNDLE_ROOT.is_dir()
    assert config.PROJECT_ROOT.is_dir()
    assert config.ICONS_DIR.is_dir()
    assert config.TEMPLATES_DIR.is_dir()
    assert config.DEFAULT_TEMPLATE_PATH.name == "raffle.png"
    assert config.DIGITS_DIR.name == "numbers"


def test_is_frozen_false_by_default():
    assert config._is_frozen() is False


def test_bundle_and_writable_roots_when_frozen(monkeypatch, tmp_path):
    meipass = tmp_path / "bundle"
    meipass.mkdir()
    exe_dir = tmp_path / "install"
    exe_dir.mkdir()
    fake_exe = exe_dir / "Raffle.exe"
    fake_exe.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe), raising=False)

    reloaded = importlib.reload(config)
    assert reloaded._bundle_root() == meipass
    assert reloaded._writable_root() == exe_dir

    importlib.reload(config)
