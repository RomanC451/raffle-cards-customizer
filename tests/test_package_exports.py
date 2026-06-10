import bingo_cards
import bingo_cards.render
import bingo_cards.ui
from bingo_cards.render import (
    build_raffle_preview,
    build_raffle_ticket,
    format_ticket_number,
)
from bingo_cards.ui import RaffleDesktopApp


def test_package_docstring():
    assert "raffle" in bingo_cards.__doc__.lower()


def test_render_public_exports():
    assert callable(build_raffle_preview)
    assert callable(build_raffle_ticket)
    assert callable(format_ticket_number)


def test_ui_public_exports():
    assert RaffleDesktopApp is not None
    assert bingo_cards.render
    assert bingo_cards.ui
