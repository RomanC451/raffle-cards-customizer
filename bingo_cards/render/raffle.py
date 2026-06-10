from pathlib import Path

from PIL import Image, ImageDraw

from bingo_cards.config import PREVIEW_PLACEHOLDER_NUMBER


def format_ticket_number(value: int, digit_count: int) -> str:
    return str(value).zfill(digit_count)


def default_number_rectangle(image_width: int, image_height: int) -> dict[str, int]:
    half_width = max(1, image_width // 2)
    rect_height = max(40, int(image_height * 0.22))
    rect_width = max(80, int(half_width * 0.75))
    x = max(0, (half_width - rect_width) // 2)
    y = max(0, int(image_height * 0.58))
    return {"x": x, "y": y, "width": rect_width, "height": rect_height}


def panel_half_width(image_width: int) -> int:
    return max(1, image_width // 2)


def load_digit_images(digits_dir: Path) -> dict[str, Image.Image]:
    images: dict[str, Image.Image] = {}
    for digit in "0123456789":
        path = digits_dir / f"{digit}.png"
        if not path.exists():
            raise FileNotFoundError(f"Missing digit image: {path}")
        images[digit] = Image.open(path).convert("RGBA")
    return images


def _scale_digit_to_slot(
    digit_image: Image.Image, slot_width: int, slot_height: int
) -> Image.Image:
    if slot_width <= 0 or slot_height <= 0:
        return digit_image.copy()

    scaled = digit_image.copy()
    scaled.thumbnail((slot_width, slot_height), Image.Resampling.LANCZOS)
    return scaled


def _paste_number_on_panel(
    image: Image.Image,
    number_text: str,
    rect_x: int,
    rect_y: int,
    rect_width: int,
    rect_height: int,
    panel_offset_x: int,
    digit_images: dict[str, Image.Image],
) -> None:
    if not number_text or rect_width <= 0 or rect_height <= 0:
        return

    digit_count = len(number_text)
    slot_width = max(1, rect_width // digit_count)

    for index, character in enumerate(number_text):
        digit_image = digit_images.get(character)
        if digit_image is None:
            continue

        scaled = _scale_digit_to_slot(digit_image, slot_width, rect_height)
        slot_x = panel_offset_x + rect_x + (index * slot_width)
        slot_y = rect_y
        paste_x = slot_x + max(0, (slot_width - scaled.width) // 2)
        paste_y = slot_y + max(0, (rect_height - scaled.height) // 2)
        image.paste(scaled, (paste_x, paste_y), scaled)


def build_raffle_ticket(
    template_image: Image.Image,
    number_text: str,
    rect_x: int,
    rect_y: int,
    rect_width: int,
    rect_height: int,
    *,
    show_rectangle_overlay: bool,
    digit_images: dict[str, Image.Image],
) -> Image.Image:
    ticket = template_image.convert("RGB").copy()
    half_width = panel_half_width(ticket.width)

    for panel_offset_x in (0, half_width):
        _paste_number_on_panel(
            ticket,
            number_text,
            rect_x,
            rect_y,
            rect_width,
            rect_height,
            panel_offset_x,
            digit_images,
        )

    if show_rectangle_overlay:
        draw = ImageDraw.Draw(ticket)
        for panel_offset_x in (0, half_width):
            draw.rectangle(
                [
                    (panel_offset_x + rect_x, rect_y),
                    (panel_offset_x + rect_x + rect_width, rect_y + rect_height),
                ],
                outline=(255, 0, 0),
                width=2,
            )

    return ticket


def build_raffle_preview(
    template_image: Image.Image,
    rect_x: int,
    rect_y: int,
    rect_width: int,
    rect_height: int,
    *,
    show_rectangle_overlay: bool,
    digit_images: dict[str, Image.Image],
    preview_number: str = PREVIEW_PLACEHOLDER_NUMBER,
) -> Image.Image:
    return build_raffle_ticket(
        template_image=template_image,
        number_text=preview_number,
        rect_x=rect_x,
        rect_y=rect_y,
        rect_width=rect_width,
        rect_height=rect_height,
        show_rectangle_overlay=show_rectangle_overlay,
        digit_images=digit_images,
    )


def validate_ticket_sequence(
    start_number: int, digit_count: int, ticket_count: int
) -> str | None:
    if start_number < 0:
        return "Start number must be zero or greater."
    if digit_count < 1:
        return "Digit count must be at least 1."
    if ticket_count < 1:
        return "Ticket count must be at least 1."
    if ticket_count > 1_000_000:
        return "Ticket count is too large."

    last_number = start_number + ticket_count - 1
    if len(str(last_number)) > digit_count:
        return (
            f"The last ticket number ({last_number}) needs more than "
            f"{digit_count} digit(s). Increase digit count or reduce the batch."
        )
    return None
