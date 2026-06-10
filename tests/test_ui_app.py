"""Tests for RaffleDesktopApp logic (CustomTkinter)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import tkinter as tk

from bingo_cards.ui.app import RaffleDesktopApp

pytest_plugins = ["tests.gui_fixtures"]


@pytest.mark.gui
class TestRaffleDesktopAppHelpers:
    def test_format_output_button_text(self, app):
        assert app._format_output_button_text() == "Browse Output Folder"
        app.output_dir = Path("C:/short")
        assert "Output:" in app._format_output_button_text()

    def test_step_int_var(self, app):
        var = tk.IntVar(value=5)
        app._customize_history_suppressed = True
        app._step_int_var(var, 3, 1, 10)
        assert var.get() == 8
        app._step_int_var(var, 100, 1, 10)
        assert var.get() == 10

    def test_capture_and_apply_customize_snapshot(self, app):
        snap = app._capture_customize_snapshot()
        app.rect_x_var.set(99)
        app._apply_customize_snapshot(snap)
        assert app.rect_x_var.get() == snap["rect_x"]

    def test_undo_redo_customize(self, app):
        app._customize_history_suppressed = False
        app._loading_state = False
        app.rect_x_var.set(10)
        app._stash_customize_undo("rect_x")
        app.rect_x_var.set(20)
        app._undo_customize()
        assert app.rect_x_var.get() == 10
        app._redo_customize()
        assert app.rect_x_var.get() == 20

    def test_serialize_and_load_state(self, app, tmp_path, sample_template):
        import bingo_cards.config as config

        config.APP_STATE_PATH.write_text("{}", encoding="utf-8")

        app._loading_state = False
        app.template_path = sample_template
        app.output_dir = tmp_path
        app.rect_x_var.set(42)
        app.start_number_var.set(10)
        app.digit_count_var.set(3)
        app.ticket_count_var.set(5)
        app._save_state()

        payload = json.loads(config.APP_STATE_PATH.read_text(encoding="utf-8"))
        assert payload["rect_x"] == 42
        assert payload["start_number"] == 10
        assert payload["digit_count"] == 3
        assert payload["ticket_count"] == 5

        app.rect_x_var.set(0)
        app._load_state()
        assert app.rect_x_var.get() == 42

    def test_load_template_sets_default_rectangle(self, app, sample_template):
        app._load_template_file(sample_template, show_error=False, reset_rectangle=True)
        assert app.template_image is not None
        assert app.rect_width_var.get() > 0
        assert app.rect_height_var.get() > 0

    def test_reset_rectangle(self, app, sample_template):
        app._load_template_file(sample_template, show_error=False, reset_rectangle=True)
        app.rect_x_var.set(5)
        app._reset_rectangle()
        defaults_x = app.rect_x_var.get()
        app.rect_x_var.set(999)
        app._reset_rectangle()
        assert app.rect_x_var.get() == defaults_x

    def test_toggle_rect_settings(self, app):
        app.rect_settings_expanded = True
        app._toggle_rect_settings()
        assert app.rect_settings_expanded is False
        app._toggle_rect_settings()
        assert app.rect_settings_expanded is True

    def test_generate_tickets_writes_files(self, app, sample_template, tmp_path):
        app._load_template_file(sample_template, show_error=False, reset_rectangle=True)
        app.output_dir = tmp_path
        app.start_number_var.set(1)
        app.digit_count_var.set(4)
        app.ticket_count_var.set(3)
        with patch("bingo_cards.ui.app.messagebox.showinfo"):
            app._generate_tickets()
        assert (tmp_path / "ticket_0001.png").exists()
        assert (tmp_path / "ticket_0002.png").exists()
        assert (tmp_path / "ticket_0003.png").exists()

    def test_generate_tickets_rejects_invalid_sequence(self, app, sample_template, tmp_path):
        app._load_template_file(sample_template, show_error=False, reset_rectangle=True)
        app.output_dir = tmp_path
        app.start_number_var.set(9999)
        app.digit_count_var.set(4)
        app.ticket_count_var.set(2)
        with patch("bingo_cards.ui.app.messagebox.showwarning"):
            app._generate_tickets()
        assert not any(tmp_path.glob("ticket_*.png"))

    def test_refresh_preview_without_template_is_noop(self, app):
        app.template_image = None
        app._refresh_preview()

    def test_generate_tickets_requires_output_dir(self, app, sample_template):
        app._load_template_file(sample_template, show_error=False, reset_rectangle=True)
        app.output_dir = None
        with patch("bingo_cards.ui.app.messagebox.showwarning") as warning:
            app._generate_tickets()
        warning.assert_called_once()

    def test_preview_zoom_controls(self, app, sample_template):
        app._load_template_file(sample_template, show_error=False, reset_rectangle=True)
        app.preview_canvas.configure(width=600, height=400)
        app._flush_preview_refresh()
        assert app.preview_base_image is not None
        app._zoom_in()
        app._zoom_out()
        app._zoom_reset()
        app._set_preview_zoom(1.5, 100, 100)
        app._on_preview_ctrl_wheel(type("E", (), {"delta": 120, "x": 50, "y": 50})())
        app._on_preview_scroll(type("E", (), {"delta": 120})())
        app._on_preview_shift_scroll(type("E", (), {"delta": 120})())
        app._on_preview_canvas_configure(type("E", (), {})())

    def test_show_preview_warning(self, app):
        app.preview_canvas.configure(width=400, height=300)
        app._show_preview_warning("No template")
