# Tombola Cards

Desktop app ("Raffle Ticket Designer") for generating numbered raffle tickets by compositing digit images onto a ticket template.

## Language

**Raffle ticket**:
A finished PNG image: the raffle template with a ticket number rendered in the number rectangle on both panel halves.
_Avoid_: Bingo card, card

**Ticket template**:
The base background image (user-selectable PNG; `raffle.png` is the default) with empty space reserved for the number.
_Avoid_: Background, base image

**Ticket panel** (or **panel half**):
One side of the dual-panel template; left and right halves are separated by a perforation line and normally show the same number. The split is always at the horizontal center of the template (`image_width / 2`).
_Avoid_: Stub, side

**Number rectangle**:
The adjustable region on a panel half where digit images are placed and scaled to fit. Defined once in half-panel coordinates and applied identically to both ticket panel halves. Digits are laid out in equal-width slots; each digit scales to fit its slot while preserving aspect ratio.
_Avoid_: Number box, digit area

**Digit image**:
A single-character PNG (0–9) from `templates/numbers/` with a transparent background, used to render each digit of the ticket number.
_Avoid_: Number sprite, glyph

**Ticket number sequence**:
The range of numbers to generate, defined by a start number, digit count (zero-padding width), and ticket count (how many tickets to produce). Example: start 1, 4 digits, 50 tickets → `0001` … `0050`, saved as `ticket_0001.png` … `ticket_0050.png`.
_Avoid_: Batch, range

**Number rectangle settings**:
The X, Y, Width, Height values (pixels, relative to the left panel half) that define the number rectangle. Adjusted via numeric fields; preview can show a toggleable red outline (never on exported tickets) and sample digits.
_Avoid_: Grid settings, placement box

## Relationships

- A **Raffle ticket** is built from one **Ticket template** and one ticket number
- Each **Raffle ticket** renders the same number on both **Ticket panel** halves
- A ticket number is composed of one or more **Digit image**s placed inside the **Number rectangle**
- The **Number rectangle** is defined once and mirrored to both **Ticket panel** halves (right half offset by half the template width)

## Example dialogue

> **Dev:** "User generates 50 tickets — do we output 50 PNG files?"
> **Domain expert:** "Yes, one **Raffle ticket** per number — `ticket_0001.png`, `ticket_0002.png`, and so on."

## Flagged ambiguities

- Digit images live in `templates/numbers/` (renamed from `nubers/`). Assets must have transparent backgrounds before compositing looks correct.
- Digit images will be re-exported with transparent backgrounds; no chroma-key compositing in code.
- "Max number" means ticket count (how many to generate), not the ending ticket number value.
- App was formerly a Music Bingo Card Designer; being replaced by raffle-only workflow (zoom, undo/redo retained).
- Undo/redo applies to **Number rectangle settings** only (X, Y, Width, Height).
- Live preview uses a fixed placeholder number (`0123`), not the start number from the form.
