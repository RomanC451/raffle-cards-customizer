from pathlib import Path

from PIL import Image

from bingo_cards.render.raffle import (
    build_raffle_preview,
    build_raffle_ticket,
    default_number_rectangle,
    format_ticket_number,
    load_digit_images,
    panel_half_width,
    validate_ticket_sequence,
)


def test_format_ticket_number():
    assert format_ticket_number(158, 4) == "0158"
    assert format_ticket_number(7, 3) == "007"


def test_default_number_rectangle():
    rect = default_number_rectangle(1600, 800)
    assert rect["width"] > 0
    assert rect["height"] > 0
    assert rect["x"] >= 0
    assert rect["y"] >= 0


def test_panel_half_width():
    assert panel_half_width(1000) == 500


def test_validate_ticket_sequence():
    assert validate_ticket_sequence(1, 4, 50) is None
    assert validate_ticket_sequence(9999, 4, 2) is not None
    assert validate_ticket_sequence(-1, 4, 1) is not None
    assert validate_ticket_sequence(1, 0, 1) is not None
    assert validate_ticket_sequence(1, 4, 0) is not None


def test_build_raffle_ticket_renders_on_both_halves(
    tiny_rgb_image: Image.Image, digits_dir: Path
):
    digit_images = load_digit_images(digits_dir)
    ticket = build_raffle_ticket(
        template_image=tiny_rgb_image,
        number_text="0123",
        rect_x=40,
        rect_y=80,
        rect_width=240,
        rect_height=120,
        show_rectangle_overlay=True,
        digit_images=digit_images,
    )
    assert ticket.size == tiny_rgb_image.size
    left_pixel = ticket.getpixel((60, 120))
    right_pixel = ticket.getpixel((panel_half_width(tiny_rgb_image.width) + 60, 120))
    assert left_pixel != tiny_rgb_image.getpixel((60, 120))
    assert right_pixel != tiny_rgb_image.getpixel(
        (panel_half_width(tiny_rgb_image.width) + 60, 120)
    )


def test_load_digit_images_missing_file(tmp_path: Path):
    digits_path = tmp_path / "numbers"
    digits_path.mkdir()
    (digits_path / "0.png").write_bytes(b"not-a-png")
    try:
        load_digit_images(digits_path)
    except Exception:
        pass

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    import pytest

    with pytest.raises(FileNotFoundError):
        load_digit_images(empty_dir)


def test_build_raffle_ticket_skips_unknown_digits(
    tiny_rgb_image: Image.Image, digits_dir: Path
):
    digit_images = load_digit_images(digits_dir)
    ticket = build_raffle_ticket(
        template_image=tiny_rgb_image,
        number_text="",
        rect_x=10,
        rect_y=10,
        rect_width=0,
        rect_height=0,
        show_rectangle_overlay=False,
        digit_images=digit_images,
    )
    assert ticket.size == tiny_rgb_image.size


def test_build_raffle_preview_uses_placeholder(
    tiny_rgb_image: Image.Image, digits_dir: Path
):
    digit_images = load_digit_images(digits_dir)
    preview = build_raffle_preview(
        template_image=tiny_rgb_image,
        rect_x=20,
        rect_y=40,
        rect_width=200,
        rect_height=100,
        show_rectangle_overlay=False,
        digit_images=digit_images,
    )
    assert preview.size == tiny_rgb_image.size
