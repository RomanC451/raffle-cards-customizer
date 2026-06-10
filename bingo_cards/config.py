import sys
from pathlib import Path


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _bundle_root() -> Path:
    """Read-only packaged assets (icons, templates, etc.)."""
    if _is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


def _writable_root() -> Path:
    """User data next to source tree in dev, next to the .exe when frozen."""
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BUNDLE_ROOT = _bundle_root()
PROJECT_ROOT = _writable_root()
ICONS_DIR = BUNDLE_ROOT / "icons"
TEMPLATES_DIR = BUNDLE_ROOT / "templates"
DEFAULT_TEMPLATE_PATH = TEMPLATES_DIR / "raffle.png"
DIGITS_DIR = TEMPLATES_DIR / "numbers"
APP_STATE_PATH = PROJECT_ROOT / "ui_desktop_state.json"

PREVIEW_PLACEHOLDER_NUMBER = "0123"
CUSTOMIZE_UNDO_LIMIT = 50
PREVIEW_REFRESH_DEBOUNCE_MS = 60
SAVE_STATE_DEBOUNCE_MS = 500

STEPPER_HOLD_INITIAL_DELAY_MS = 400
STEPPER_HOLD_START_INTERVAL_MS = 110
STEPPER_HOLD_MIN_INTERVAL_MS = 45
STEPPER_HOLD_ACCELERATION = 0.82
