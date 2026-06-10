import json
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

from bingo_cards.config import (
    APP_STATE_PATH,
    CUSTOMIZE_UNDO_LIMIT,
    DEFAULT_TEMPLATE_PATH,
    DIGITS_DIR,
    PREVIEW_REFRESH_DEBOUNCE_MS,
    SAVE_STATE_DEBOUNCE_MS,
)
from bingo_cards.render import (
    build_raffle_preview,
    build_raffle_ticket,
    default_number_rectangle,
    format_ticket_number,
    load_digit_images,
    validate_ticket_sequence,
)
from bingo_cards.ui.toolbar_icons import load_toolbar_icon
from bingo_cards.ui.widgets import HoldRepeatController, HoverToolTip, IconToolbarButton


class RaffleDesktopApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Raffle Ticket Designer")
        self.geometry("1380x900")
        self.minsize(1200, 780)
        self.after(0, lambda: self.state("zoomed"))

        self.template_path: Path | None = None
        self.template_image: Image.Image | None = None
        self.output_dir: Path | None = None
        self.preview_photo = None
        self.preview_base_image: Image.Image | None = None
        self.preview_image_id: int | None = None
        self.preview_zoom = 1.0
        self.preview_zoom_label_var = tk.StringVar(value="100%")
        self._pending_fit_zoom = False
        self._preview_h_scroll_visible = True
        self._preview_v_scroll_visible = True
        self._cached_digit_images: dict[str, Image.Image] | None = None

        self.rect_x_var = tk.IntVar(value=0)
        self.rect_y_var = tk.IntVar(value=0)
        self.rect_width_var = tk.IntVar(value=200)
        self.rect_height_var = tk.IntVar(value=120)
        self.show_rect_overlay_var = tk.BooleanVar(value=True)
        self.rect_settings_expanded = True

        self.start_number_var = tk.IntVar(value=1)
        self.digit_count_var = tk.IntVar(value=4)
        self.ticket_count_var = tk.IntVar(value=50)

        self._loading_state = False
        self._customize_history_suppressed = False
        self._customize_undo_stack: list[dict] = []
        self._customize_redo_stack: list[dict] = []
        self._customize_active_action_key: str | None = None
        self._preview_refresh_after_id: str | None = None
        self._save_state_after_id: str | None = None

        self._build_layout()
        self._load_state()
        if self.template_image is None:
            self._try_load_default_template()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left_panel = ctk.CTkFrame(self, fg_color="transparent", width=380)
        left_panel.grid(row=0, column=0, sticky="nsw", padx=(16, 8), pady=16)
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(0, weight=1)

        controls = ctk.CTkScrollableFrame(left_panel, corner_radius=12, width=380)
        controls.grid(row=0, column=0, sticky="nsew")
        controls.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            controls,
            text="Raffle Ticket Designer",
            font=ctk.CTkFont(size=26, weight="bold"),
        ).grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")

        ctk.CTkLabel(
            controls,
            text="Source",
            text_color="#9ca3af",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=1, column=0, padx=16, pady=(8, 6), sticky="w")

        self.select_template_button = ctk.CTkButton(
            controls,
            text="Select Template Image",
            command=self._select_template,
            height=36,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
        )
        self.select_template_button.grid(
            row=2, column=0, padx=16, pady=(0, 14), sticky="ew"
        )

        ctk.CTkFrame(controls, height=2, fg_color="#6b7280", corner_radius=0).grid(
            row=3, column=0, padx=16, pady=(4, 12), sticky="ew"
        )
        ctk.CTkLabel(
            controls,
            text="Number Rectangle",
            text_color="#9ca3af",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=4, column=0, padx=16, pady=(0, 6), sticky="w")

        self.rect_settings_toggle_button = ctk.CTkButton(
            controls,
            text="▼ Rectangle Settings",
            command=self._toggle_rect_settings,
            height=32,
            fg_color="#374151",
            hover_color="#4b5563",
        )
        self.rect_settings_toggle_button.grid(
            row=5, column=0, padx=16, pady=(0, 10), sticky="ew"
        )

        self.rect_settings_frame = ctk.CTkFrame(controls, corner_radius=8)
        self.rect_settings_frame.grid_columnconfigure(0, weight=1)
        self.rect_settings_frame.grid(
            row=6, column=0, padx=16, pady=(0, 12), sticky="ew"
        )

        overlay_row = ctk.CTkFrame(self.rect_settings_frame, fg_color="transparent")
        overlay_row.grid(row=0, column=0, padx=10, pady=(10, 8), sticky="ew")
        overlay_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(overlay_row, text="Show Rectangle Overlay").grid(
            row=0, column=0, sticky="w"
        )
        self.rect_overlay_switch = ctk.CTkSwitch(
            overlay_row,
            text="",
            width=46,
            switch_width=36,
            variable=self.show_rect_overlay_var,
            command=self._on_rect_overlay_toggled,
        )
        self.rect_overlay_switch.grid(row=0, column=1, sticky="e")

        self._create_stepper_row(
            self.rect_settings_frame,
            row=1,
            label="X",
            variable=self.rect_x_var,
            minimum=0,
            maximum=4096,
        )
        self._create_stepper_row(
            self.rect_settings_frame,
            row=2,
            label="Y",
            variable=self.rect_y_var,
            minimum=0,
            maximum=4096,
        )
        self._create_stepper_row(
            self.rect_settings_frame,
            row=3,
            label="Width",
            variable=self.rect_width_var,
            minimum=20,
            maximum=4096,
        )
        self._create_stepper_row(
            self.rect_settings_frame,
            row=4,
            label="Height",
            variable=self.rect_height_var,
            minimum=20,
            maximum=4096,
        )

        ctk.CTkFrame(controls, height=2, fg_color="#6b7280", corner_radius=0).grid(
            row=7, column=0, padx=16, pady=(10, 12), sticky="ew"
        )
        ctk.CTkLabel(
            controls,
            text="Generation",
            text_color="#9ca3af",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=8, column=0, padx=16, pady=(0, 6), sticky="w")

        self._create_stepper_row(
            controls,
            row=9,
            label="Start Number",
            variable=self.start_number_var,
            minimum=0,
            maximum=9_999_999,
            undo=False,
        )
        self._create_stepper_row(
            controls,
            row=10,
            label="Digit Count",
            variable=self.digit_count_var,
            minimum=1,
            maximum=12,
            undo=False,
        )
        self._create_stepper_row(
            controls,
            row=11,
            label="Ticket Count",
            variable=self.ticket_count_var,
            minimum=1,
            maximum=1_000_000,
            undo=False,
        )

        ctk.CTkFrame(controls, height=2, fg_color="#6b7280", corner_radius=0).grid(
            row=12, column=0, padx=16, pady=(10, 12), sticky="ew"
        )
        ctk.CTkLabel(
            controls,
            text="Output",
            text_color="#9ca3af",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=13, column=0, padx=16, pady=(0, 6), sticky="w")
        self.output_folder_button = ctk.CTkButton(
            controls,
            text=self._format_output_button_text(),
            command=self._select_output_folder,
            height=36,
            fg_color="#0891b2",
            hover_color="#0e7490",
        )
        self.output_folder_button.grid(
            row=14, column=0, padx=16, pady=(0, 10), sticky="ew"
        )
        ctk.CTkButton(
            controls,
            text="Open Generated Folder",
            command=self._open_output_folder,
            height=34,
            fg_color="#475569",
            hover_color="#334155",
        ).grid(row=15, column=0, padx=16, pady=(0, 12), sticky="ew")

        ctk.CTkFrame(controls, height=2, fg_color="#6b7280", corner_radius=0).grid(
            row=16, column=0, padx=16, pady=(2, 12), sticky="ew"
        )
        ctk.CTkLabel(
            controls,
            text="Run",
            text_color="#9ca3af",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=17, column=0, padx=16, pady=(0, 6), sticky="w")
        self.generate_button = ctk.CTkButton(
            controls,
            text="Generate Tickets",
            command=self._generate_tickets,
            fg_color="#16a34a",
            hover_color="#15803d",
            height=38,
        )
        self.generate_button.grid(row=18, column=0, padx=16, pady=(0, 10), sticky="ew")
        self.generate_progress = ctk.CTkProgressBar(controls)
        self.generate_progress.set(0)
        self.generate_progress.grid(row=19, column=0, padx=16, pady=(0, 4), sticky="ew")
        self.generate_status_label = ctk.CTkLabel(
            controls, text="Generation status: idle", anchor="w", text_color="#9ca3af"
        )
        self.generate_status_label.grid(
            row=20, column=0, padx=16, pady=(0, 16), sticky="ew"
        )

        preview_frame = ctk.CTkFrame(self, corner_radius=12)
        preview_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)
        preview_frame.grid_columnconfigure(0, weight=1)
        preview_frame.grid_rowconfigure(1, weight=1)

        preview_header = ctk.CTkFrame(preview_frame, fg_color="transparent")
        preview_header.grid(row=0, column=0, padx=18, pady=(16, 10), sticky="ew")
        preview_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            preview_header,
            text="Live Preview",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        preview_toolbar = ctk.CTkFrame(preview_header, fg_color="transparent")
        preview_toolbar.grid(row=0, column=1, sticky="e")

        icon_pixel_size = 24
        toolbar_button_size = 36

        undo_icon_on = load_toolbar_icon("undo", icon_pixel_size, enabled=True)
        undo_icon_off = load_toolbar_icon("undo", icon_pixel_size, enabled=False)
        redo_icon_on = load_toolbar_icon("redo", icon_pixel_size, enabled=True)
        redo_icon_off = load_toolbar_icon("redo", icon_pixel_size, enabled=False)

        self.undo_customize_button = IconToolbarButton(
            preview_toolbar,
            pil_image=undo_icon_on,
            pil_image_disabled=undo_icon_off,
            command=self._undo_customize,
            size=toolbar_button_size,
            state="disabled",
        )
        self.undo_customize_button.grid(row=0, column=0, padx=(0, 4))

        self.redo_customize_button = IconToolbarButton(
            preview_toolbar,
            pil_image=redo_icon_on,
            pil_image_disabled=redo_icon_off,
            command=self._redo_customize,
            size=toolbar_button_size,
            state="disabled",
        )
        self.redo_customize_button.grid(row=0, column=1, padx=(0, 4))

        self.reset_customize_button = IconToolbarButton(
            preview_toolbar,
            pil_image=load_toolbar_icon("reset", icon_pixel_size),
            command=self._reset_rectangle,
            size=toolbar_button_size,
            fg_color="#6b7280",
        )
        self.reset_customize_button.grid(row=0, column=2, padx=(0, 10))

        ctk.CTkFrame(
            preview_toolbar, width=1, height=toolbar_button_size - 6, fg_color="#6b7280"
        ).grid(row=0, column=3, padx=(0, 10))

        zoom_button_fg = "#2563eb"
        zoom_button_hover = "#1d4ed8"

        self.zoom_out_button = IconToolbarButton(
            preview_toolbar,
            pil_image=load_toolbar_icon("minus", icon_pixel_size),
            command=self._zoom_out,
            size=toolbar_button_size,
            fg_color=zoom_button_fg,
            hover_color=zoom_button_hover,
        )
        self.zoom_out_button.grid(row=0, column=4, padx=(0, 6))
        self.preview_zoom_label = ctk.CTkLabel(
            preview_toolbar,
            textvariable=self.preview_zoom_label_var,
            width=56,
            anchor="center",
        )
        self.preview_zoom_label.grid(row=0, column=5, padx=(0, 6))
        self.zoom_in_button = IconToolbarButton(
            preview_toolbar,
            pil_image=load_toolbar_icon("plus", icon_pixel_size),
            command=self._zoom_in,
            size=toolbar_button_size,
            fg_color=zoom_button_fg,
            hover_color=zoom_button_hover,
        )
        self.zoom_in_button.grid(row=0, column=6, padx=(0, 6))
        self.zoom_fit_button = IconToolbarButton(
            preview_toolbar,
            pil_image=load_toolbar_icon("fit", icon_pixel_size),
            command=self._zoom_reset,
            size=toolbar_button_size,
        )
        self.zoom_fit_button.grid(row=0, column=7)

        self._preview_tooltips = [
            HoverToolTip(self.undo_customize_button, "Undo rectangle change (Ctrl+Z)"),
            HoverToolTip(self.redo_customize_button, "Redo rectangle change (Ctrl+Y)"),
            HoverToolTip(
                self.reset_customize_button,
                "Reset number rectangle to template defaults",
            ),
            HoverToolTip(self.zoom_out_button, "Zoom out"),
            HoverToolTip(self.preview_zoom_label, "Preview zoom level"),
            HoverToolTip(self.zoom_in_button, "Zoom in"),
            HoverToolTip(self.zoom_fit_button, "Fit preview to window"),
        ]

        preview_viewport = ctk.CTkFrame(preview_frame, corner_radius=8)
        preview_viewport.grid(row=1, column=0, padx=18, pady=(0, 18), sticky="nsew")
        preview_viewport.grid_rowconfigure(0, weight=1)
        preview_viewport.grid_columnconfigure(0, weight=1)

        self.preview_canvas = tk.Canvas(
            preview_viewport,
            bg="#2b2b2b",
            highlightthickness=0,
            xscrollincrement=1,
            yscrollincrement=1,
        )
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")

        self.preview_v_scroll = ctk.CTkScrollbar(
            preview_viewport, orientation="vertical", command=self.preview_canvas.yview
        )
        self.preview_v_scroll.grid(row=0, column=1, sticky="ns")
        self.preview_h_scroll = ctk.CTkScrollbar(
            preview_viewport,
            orientation="horizontal",
            command=self.preview_canvas.xview,
        )
        self.preview_h_scroll.grid(row=1, column=0, sticky="ew")
        self.preview_canvas.configure(
            xscrollcommand=self.preview_h_scroll.set,
            yscrollcommand=self.preview_v_scroll.set,
        )
        self.preview_canvas.bind("<Control-MouseWheel>", self._on_preview_ctrl_wheel)
        self.preview_canvas.bind("<MouseWheel>", self._on_preview_scroll)
        self.preview_canvas.bind("<Shift-MouseWheel>", self._on_preview_shift_scroll)
        self.preview_canvas.bind("<Configure>", self._on_preview_canvas_configure)
        self._show_preview_warning("Select a template image to start.")

        preview_refresh = lambda *_args: self._schedule_preview_refresh()
        self.rect_x_var.trace_add("write", preview_refresh)
        self.rect_y_var.trace_add("write", preview_refresh)
        self.rect_width_var.trace_add("write", preview_refresh)
        self.rect_height_var.trace_add("write", preview_refresh)
        self.show_rect_overlay_var.trace_add("write", preview_refresh)

        self.bind_all("<Control-z>", self._on_customize_undo_shortcut)
        self.bind_all("<Control-Z>", self._on_customize_undo_shortcut)
        self.bind_all("<Control-y>", self._on_customize_redo_shortcut)
        self.bind_all("<Control-Y>", self._on_customize_redo_shortcut)
        self.bind_all("<Control-Shift-z>", self._on_customize_redo_shortcut)
        self.bind_all("<Control-Shift-Z>", self._on_customize_redo_shortcut)

    def _toggle_rect_settings(self):
        self.rect_settings_expanded = not self.rect_settings_expanded
        if self.rect_settings_expanded:
            self.rect_settings_toggle_button.configure(text="▼ Rectangle Settings")
            self.rect_settings_frame.grid(
                row=6, column=0, padx=16, pady=(0, 12), sticky="ew"
            )
        else:
            self.rect_settings_toggle_button.configure(text="▶ Rectangle Settings")
            self.rect_settings_frame.grid_forget()
        self._save_state()

    def _step_int_var(
        self,
        variable: tk.IntVar,
        delta: int,
        minimum: int,
        maximum: int,
        *,
        undo: bool = True,
    ) -> bool:
        current = int(variable.get())
        if delta > 0 and current >= maximum:
            return False
        if delta < 0 and current <= minimum:
            return False
        if undo:
            self._stash_customize_undo(f"step:{id(variable)}")
        variable.set(max(minimum, min(maximum, current + delta)))
        return True

    def _create_stepper_row(
        self,
        parent,
        row: int,
        label: str,
        variable: tk.IntVar,
        minimum: int,
        maximum: int,
        *,
        undo: bool = True,
    ):
        stepper = ctk.CTkFrame(parent, fg_color="transparent")
        stepper.grid(row=row, column=0, padx=10, pady=(0, 8), sticky="ew")
        stepper.grid_columnconfigure(0, weight=1)
        button_width = 32
        value_width = 60

        ctk.CTkLabel(stepper, text=label).grid(row=0, column=0, sticky="w")
        controls = ctk.CTkFrame(stepper, fg_color="transparent")
        controls.grid(row=0, column=1, sticky="e")
        controls.grid_columnconfigure(0, minsize=button_width)
        controls.grid_columnconfigure(1, minsize=value_width)
        controls.grid_columnconfigure(2, minsize=button_width)

        minus_button = ctk.CTkButton(controls, text="-", width=button_width)
        minus_button.grid(row=0, column=0, padx=(0, 6))
        HoldRepeatController(
            minus_button,
            lambda: self._step_int_var(variable, -1, minimum, maximum, undo=undo),
        )
        entry_var = tk.StringVar(value=str(int(variable.get())))

        def sync_entry_from_var(*_args):
            entry_var.set(str(int(variable.get())))

        def commit_int_entry(_event=None):
            raw_value = entry_var.get().strip()
            try:
                parsed = int(raw_value)
            except ValueError:
                parsed = int(variable.get())
            parsed = max(minimum, min(maximum, parsed))
            if undo and parsed != int(variable.get()):
                self._stash_customize_undo(f"entry:{id(variable)}")
            variable.set(parsed)
            entry_var.set(str(parsed))
            self._save_state()

        variable.trace_add("write", sync_entry_from_var)
        entry_action_key = f"entry:{id(variable)}"
        value_entry = ctk.CTkEntry(
            controls,
            textvariable=entry_var,
            width=value_width,
            justify="center",
        )
        value_entry.grid(row=0, column=1, padx=(0, 6))
        if undo:
            value_entry.bind(
                "<FocusIn>",
                lambda _event, key=entry_action_key: self._stash_customize_undo(key),
            )
        value_entry.bind("<Return>", commit_int_entry)
        value_entry.bind("<FocusOut>", commit_int_entry)
        plus_button = ctk.CTkButton(controls, text="+", width=button_width)
        plus_button.grid(row=0, column=2)
        HoldRepeatController(
            plus_button,
            lambda: self._step_int_var(variable, 1, minimum, maximum, undo=undo),
        )

        return value_entry

    def _try_load_default_template(self):
        if DEFAULT_TEMPLATE_PATH.exists():
            self._load_template_file(
                DEFAULT_TEMPLATE_PATH, show_error=False, reset_rectangle=True
            )

    def _select_template(self):
        file_path = filedialog.askopenfilename(
            title="Select template image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.webp"),
                ("All files", "*.*"),
            ],
        )
        if not file_path:
            return
        self._load_template_file(
            Path(file_path), show_error=True, reset_rectangle=False
        )

    def _apply_default_rectangle(self) -> None:
        if self.template_image is None:
            return
        width, height = self.template_image.size
        defaults = default_number_rectangle(width, height)
        self.rect_x_var.set(defaults["x"])
        self.rect_y_var.set(defaults["y"])
        self.rect_width_var.set(defaults["width"])
        self.rect_height_var.set(defaults["height"])

    def _format_output_button_text(self) -> str:
        if self.output_dir is None:
            return "Browse Output Folder"
        folder_text = str(self.output_dir)
        if len(folder_text) > 42:
            folder_text = f"...{folder_text[-39:]}"
        return f"Output: {folder_text}"

    def _capture_customize_snapshot(self) -> dict:
        return {
            "rect_x": int(self.rect_x_var.get()),
            "rect_y": int(self.rect_y_var.get()),
            "rect_width": int(self.rect_width_var.get()),
            "rect_height": int(self.rect_height_var.get()),
            "show_rect_overlay": bool(self.show_rect_overlay_var.get()),
        }

    def _apply_customize_snapshot(self, snapshot: dict) -> None:
        self._customize_history_suppressed = True
        try:
            self.rect_x_var.set(int(snapshot.get("rect_x", 0)))
            self.rect_y_var.set(int(snapshot.get("rect_y", 0)))
            self.rect_width_var.set(int(snapshot.get("rect_width", 200)))
            self.rect_height_var.set(int(snapshot.get("rect_height", 120)))
            self.show_rect_overlay_var.set(bool(snapshot.get("show_rect_overlay", True)))
        finally:
            self._customize_history_suppressed = False
        self._schedule_preview_refresh()

    def _clear_customize_action_group(self) -> None:
        self._customize_active_action_key = None

    def _stash_customize_undo(self, action_key: str | None = None) -> None:
        if self._customize_history_suppressed or self._loading_state:
            return

        if action_key is not None and action_key == self._customize_active_action_key:
            return

        snapshot = self._capture_customize_snapshot()
        if self._customize_undo_stack and self._customize_undo_stack[-1] == snapshot:
            self._customize_active_action_key = action_key
            return

        self._customize_undo_stack.append(snapshot)
        if len(self._customize_undo_stack) > CUSTOMIZE_UNDO_LIMIT:
            self._customize_undo_stack.pop(0)
        self._customize_redo_stack.clear()
        self._customize_active_action_key = action_key
        self._update_customize_undo_redo_buttons()

    def _update_customize_undo_redo_buttons(self) -> None:
        undo_state = "normal" if self._customize_undo_stack else "disabled"
        redo_state = "normal" if self._customize_redo_stack else "disabled"
        self.undo_customize_button.configure(state=undo_state)
        self.redo_customize_button.configure(state=redo_state)

    def _undo_customize(self) -> None:
        if not self._customize_undo_stack:
            return
        self._clear_customize_action_group()
        current = self._capture_customize_snapshot()
        previous = self._customize_undo_stack.pop()
        if previous != current:
            self._customize_redo_stack.append(current)
            if len(self._customize_redo_stack) > CUSTOMIZE_UNDO_LIMIT:
                self._customize_redo_stack.pop(0)
        self._apply_customize_snapshot(previous)
        self._update_customize_undo_redo_buttons()
        self._schedule_save_state()

    def _redo_customize(self) -> None:
        if not self._customize_redo_stack:
            return
        self._clear_customize_action_group()
        current = self._capture_customize_snapshot()
        next_snapshot = self._customize_redo_stack.pop()
        if next_snapshot != current:
            self._customize_undo_stack.append(current)
            if len(self._customize_undo_stack) > CUSTOMIZE_UNDO_LIMIT:
                self._customize_undo_stack.pop(0)
        self._apply_customize_snapshot(next_snapshot)
        self._update_customize_undo_redo_buttons()
        self._schedule_save_state()

    def _on_rect_overlay_toggled(self) -> None:
        self._stash_customize_undo("toggle:rect_overlay")
        self._schedule_preview_refresh()

    def _on_customize_undo_shortcut(self, _event=None):
        self._undo_customize()
        return "break"

    def _on_customize_redo_shortcut(self, _event=None):
        self._redo_customize()
        return "break"

    def _select_output_folder(self):
        folder = filedialog.askdirectory(title="Select output folder")
        if not folder:
            return
        self.output_dir = Path(folder)
        self.output_folder_button.configure(text=self._format_output_button_text())
        self._save_state()

    def _open_output_folder(self):
        if self.output_dir is None:
            messagebox.showwarning(
                "Missing Output Folder", "Please choose an output folder first."
            )
            return
        if not self.output_dir.exists():
            messagebox.showwarning(
                "Missing Folder", f"Output folder does not exist:\n{self.output_dir}"
            )
            return
        os.startfile(self.output_dir)

    def _reset_rectangle(self):
        if self.template_image is None:
            return
        self._stash_customize_undo("reset:rectangle")
        self._apply_default_rectangle()
        self.show_rect_overlay_var.set(True)
        self._schedule_preview_refresh()

    def _get_digit_images(self) -> dict[str, Image.Image]:
        if self._cached_digit_images is None:
            self._cached_digit_images = load_digit_images(DIGITS_DIR)
        return self._cached_digit_images

    def _generate_tickets(self):
        if self.template_image is None or self.template_path is None:
            messagebox.showwarning(
                "Missing Template", "Please select a template image first."
            )
            return
        if self.output_dir is None:
            messagebox.showwarning(
                "Missing Output Folder", "Please choose an output folder first."
            )
            return

        start_number = int(self.start_number_var.get())
        digit_count = int(self.digit_count_var.get())
        ticket_count = int(self.ticket_count_var.get())
        validation_error = validate_ticket_sequence(
            start_number, digit_count, ticket_count
        )
        if validation_error:
            messagebox.showwarning("Invalid Settings", validation_error)
            return

        try:
            digit_images = self._get_digit_images()
        except FileNotFoundError as error:
            messagebox.showerror("Missing Digit Images", str(error))
            return

        self.generate_button.configure(state="disabled")
        self.generate_progress.set(0)
        self.generate_status_label.configure(text="Generation status: preparing...")
        self.update_idletasks()

        rect_x = int(self.rect_x_var.get())
        rect_y = int(self.rect_y_var.get())
        rect_width = int(self.rect_width_var.get())
        rect_height = int(self.rect_height_var.get())

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            for index in range(ticket_count):
                ticket_number = start_number + index
                number_text = format_ticket_number(ticket_number, digit_count)
                image = build_raffle_ticket(
                    template_image=self.template_image,
                    number_text=number_text,
                    rect_x=rect_x,
                    rect_y=rect_y,
                    rect_width=rect_width,
                    rect_height=rect_height,
                    show_rectangle_overlay=False,
                    digit_images=digit_images,
                )
                output_path = self.output_dir / f"ticket_{number_text}.png"
                image.save(output_path)
                self.generate_progress.set((index + 1) / ticket_count)
                self.generate_status_label.configure(
                    text=f"Generation status: {index + 1}/{ticket_count}"
                )
                self.update_idletasks()

            self.generate_status_label.configure(
                text=f"Generation status: done ({ticket_count}/{ticket_count})"
            )
            messagebox.showinfo(
                "Generation Complete",
                f"Generated {ticket_count} tickets in:\n{self.output_dir}",
            )
        except Exception as error:
            self.generate_status_label.configure(text="Generation status: failed")
            messagebox.showerror(
                "Generation Error", f"Could not generate tickets:\n{error}"
            )
        finally:
            self.generate_button.configure(state="normal")

    def _show_preview_warning(self, message: str):
        self.preview_base_image = None
        self.preview_photo = None
        self.preview_image_id = None
        self.preview_canvas.delete("all")
        canvas_w = max(200, self.preview_canvas.winfo_width())
        canvas_h = max(150, self.preview_canvas.winfo_height())
        self.preview_canvas.create_text(
            canvas_w // 2,
            canvas_h // 2,
            text=message,
            fill="#f59e0b",
            anchor="center",
            width=max(180, canvas_w - 40),
        )
        self.preview_canvas.configure(scrollregion=(0, 0, canvas_w, canvas_h))
        self._set_preview_scrollbars_visibility(
            show_horizontal=False, show_vertical=False
        )

    def _set_preview_scrollbars_visibility(
        self, show_horizontal: bool, show_vertical: bool
    ):
        if show_horizontal != self._preview_h_scroll_visible:
            if show_horizontal:
                self.preview_h_scroll.grid(row=1, column=0, sticky="ew")
            else:
                self.preview_h_scroll.grid_remove()
            self._preview_h_scroll_visible = show_horizontal
        if show_vertical != self._preview_v_scroll_visible:
            if show_vertical:
                self.preview_v_scroll.grid(row=0, column=1, sticky="ns")
            else:
                self.preview_v_scroll.grid_remove()
            self._preview_v_scroll_visible = show_vertical

    def _preview_layout(self, render_w: int, render_h: int) -> dict[str, int]:
        canvas_w = max(1, self.preview_canvas.winfo_width())
        canvas_h = max(1, self.preview_canvas.winfo_height())
        origin_x = max(0, (canvas_w - render_w) // 2)
        origin_y = max(0, (canvas_h - render_h) // 2)
        scroll_w = max(canvas_w, render_w)
        scroll_h = max(canvas_h, render_h)
        return {
            "canvas_w": canvas_w,
            "canvas_h": canvas_h,
            "origin_x": origin_x,
            "origin_y": origin_y,
            "scroll_w": scroll_w,
            "scroll_h": scroll_h,
        }

    def _set_preview_zoom(
        self,
        zoom_value: float,
        anchor_canvas_x: int | None = None,
        anchor_canvas_y: int | None = None,
    ):
        old_zoom = self.preview_zoom
        base_x: float | None = None
        base_y: float | None = None
        pointer_x = anchor_canvas_x
        pointer_y = anchor_canvas_y

        if (
            self.preview_base_image is not None
            and old_zoom > 0
            and anchor_canvas_x is not None
            and anchor_canvas_y is not None
        ):
            base_w, base_h = self.preview_base_image.size
            old_render_w = max(1, int(round(base_w * old_zoom)))
            old_render_h = max(1, int(round(base_h * old_zoom)))
            old_layout = self._preview_layout(old_render_w, old_render_h)
            world_x = self.preview_canvas.canvasx(anchor_canvas_x)
            world_y = self.preview_canvas.canvasy(anchor_canvas_y)
            base_x = (world_x - old_layout["origin_x"]) / old_zoom
            base_y = (world_y - old_layout["origin_y"]) / old_zoom

        self.preview_zoom = max(0.25, min(4.0, zoom_value))
        self.preview_zoom_label_var.set(f"{int(round(self.preview_zoom * 100))}%")
        self._render_preview_image()

        if (
            self.preview_base_image is None
            or base_x is None
            or base_y is None
            or pointer_x is None
            or pointer_y is None
        ):
            return

        base_w, base_h = self.preview_base_image.size
        new_render_w = max(1, int(round(base_w * self.preview_zoom)))
        new_render_h = max(1, int(round(base_h * self.preview_zoom)))
        new_layout = self._preview_layout(new_render_w, new_render_h)

        new_world_x = new_layout["origin_x"] + (base_x * self.preview_zoom)
        new_world_y = new_layout["origin_y"] + (base_y * self.preview_zoom)

        max_x_scroll = max(0, new_layout["scroll_w"] - new_layout["canvas_w"])
        max_y_scroll = max(0, new_layout["scroll_h"] - new_layout["canvas_h"])

        desired_left = new_world_x - pointer_x
        desired_top = new_world_y - pointer_y

        if max_x_scroll > 0:
            clamped_left = max(0, min(max_x_scroll, desired_left))
            self.preview_canvas.xview_moveto(clamped_left / new_layout["scroll_w"])
        else:
            self.preview_canvas.xview_moveto(0)
        if max_y_scroll > 0:
            clamped_top = max(0, min(max_y_scroll, desired_top))
            self.preview_canvas.yview_moveto(clamped_top / new_layout["scroll_h"])
        else:
            self.preview_canvas.yview_moveto(0)

    def _calculate_fit_zoom(self) -> float:
        if self.preview_base_image is None:
            return 1.0
        image_w, image_h = self.preview_base_image.size
        if image_w <= 0 or image_h <= 0:
            return 1.0
        canvas_w = max(1, self.preview_canvas.winfo_width())
        canvas_h = max(1, self.preview_canvas.winfo_height())
        fit_zoom = min(canvas_w / image_w, canvas_h / image_h)
        return max(0.25, min(4.0, fit_zoom))

    def _zoom_in(self):
        self._set_preview_zoom(self.preview_zoom * 1.1)

    def _zoom_out(self):
        self._set_preview_zoom(self.preview_zoom / 1.1)

    def _zoom_reset(self):
        self._set_preview_zoom(self._calculate_fit_zoom())

    def _on_preview_ctrl_wheel(self, event):
        if event.delta > 0:
            self._set_preview_zoom(self.preview_zoom * 1.1, event.x, event.y)
        else:
            self._set_preview_zoom(self.preview_zoom / 1.1, event.x, event.y)

    def _on_preview_scroll(self, event):
        if event.delta == 0:
            return
        self.preview_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _on_preview_shift_scroll(self, event):
        if event.delta == 0:
            return
        self.preview_canvas.xview_scroll(int(-event.delta / 120), "units")

    def _on_preview_canvas_configure(self, _event):
        if self._pending_fit_zoom and self.preview_base_image is not None:
            self._pending_fit_zoom = False
            self._set_preview_zoom(self._calculate_fit_zoom())
            return
        self._render_preview_image()

    def _render_preview_image(self):
        if self.preview_base_image is None:
            return
        base_w, base_h = self.preview_base_image.size
        render_w = max(1, int(round(base_w * self.preview_zoom)))
        render_h = max(1, int(round(base_h * self.preview_zoom)))
        rendered = self.preview_base_image.resize(
            (render_w, render_h), Image.Resampling.LANCZOS
        )
        self.preview_photo = ImageTk.PhotoImage(rendered)
        self.preview_canvas.delete("all")
        layout = self._preview_layout(render_w, render_h)
        self.preview_image_id = self.preview_canvas.create_image(
            layout["origin_x"],
            layout["origin_y"],
            image=self.preview_photo,
            anchor="nw",
        )
        self.preview_canvas.configure(
            scrollregion=(0, 0, layout["scroll_w"], layout["scroll_h"])
        )
        self._set_preview_scrollbars_visibility(
            show_horizontal=layout["scroll_w"] > layout["canvas_w"],
            show_vertical=layout["scroll_h"] > layout["canvas_h"],
        )

    def _schedule_preview_refresh(self) -> None:
        if self._preview_refresh_after_id is not None:
            self.after_cancel(self._preview_refresh_after_id)
        self._preview_refresh_after_id = self.after(
            PREVIEW_REFRESH_DEBOUNCE_MS, self._run_scheduled_preview_refresh
        )

    def _run_scheduled_preview_refresh(self) -> None:
        self._preview_refresh_after_id = None
        self._refresh_preview()

    def _flush_preview_refresh(self) -> None:
        if self._preview_refresh_after_id is not None:
            self.after_cancel(self._preview_refresh_after_id)
            self._preview_refresh_after_id = None
        self._refresh_preview()

    def _schedule_save_state(self) -> None:
        if self._save_state_after_id is not None:
            self.after_cancel(self._save_state_after_id)
        self._save_state_after_id = self.after(
            SAVE_STATE_DEBOUNCE_MS, self._run_scheduled_save_state
        )

    def _run_scheduled_save_state(self) -> None:
        self._save_state_after_id = None
        self._save_state()

    def _flush_save_state(self) -> None:
        if self._save_state_after_id is not None:
            self.after_cancel(self._save_state_after_id)
            self._save_state_after_id = None
        self._save_state()

    def _refresh_preview(self):
        if self.template_image is None:
            return

        try:
            digit_images = self._get_digit_images()
        except FileNotFoundError as error:
            self._show_preview_warning(str(error))
            return

        preview = build_raffle_preview(
            template_image=self.template_image,
            rect_x=int(self.rect_x_var.get()),
            rect_y=int(self.rect_y_var.get()),
            rect_width=int(self.rect_width_var.get()),
            rect_height=int(self.rect_height_var.get()),
            show_rectangle_overlay=bool(self.show_rect_overlay_var.get()),
            digit_images=digit_images,
        )

        should_fit_preview = (
            self.preview_base_image is None
            or self.preview_base_image.size != preview.size
        )
        self.preview_base_image = preview
        if should_fit_preview:
            self._pending_fit_zoom = True
            self._render_preview_image()
        else:
            self._render_preview_image()
        self._schedule_save_state()

    def _load_template_file(self, path: Path, show_error: bool, *, reset_rectangle: bool):
        self.template_path = path
        try:
            self.template_image = Image.open(self.template_path).convert("RGB")
            if reset_rectangle:
                self._apply_default_rectangle()
            self._flush_preview_refresh()
            return True
        except Exception as error:
            self.template_path = None
            self.template_image = None
            if show_error:
                messagebox.showerror(
                    "Template Error", f"Could not read template:\n{error}"
                )
            return False

    def _serialize_state(self) -> dict:
        return {
            "template_path": str(self.template_path) if self.template_path else None,
            "output_dir": str(self.output_dir) if self.output_dir else None,
            "rect_x": int(self.rect_x_var.get()),
            "rect_y": int(self.rect_y_var.get()),
            "rect_width": int(self.rect_width_var.get()),
            "rect_height": int(self.rect_height_var.get()),
            "show_rect_overlay": bool(self.show_rect_overlay_var.get()),
            "start_number": int(self.start_number_var.get()),
            "digit_count": int(self.digit_count_var.get()),
            "ticket_count": int(self.ticket_count_var.get()),
            "rect_settings_expanded": bool(self.rect_settings_expanded),
        }

    def _save_state(self):
        if self._loading_state:
            return
        try:
            APP_STATE_PATH.write_text(
                json.dumps(self._serialize_state(), indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _load_state(self):
        if not APP_STATE_PATH.exists():
            return
        try:
            state = json.loads(APP_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return

        self._loading_state = True
        try:
            self.rect_x_var.set(int(state.get("rect_x", 0)))
            self.rect_y_var.set(int(state.get("rect_y", 0)))
            self.rect_width_var.set(int(state.get("rect_width", 200)))
            self.rect_height_var.set(int(state.get("rect_height", 120)))
            self.show_rect_overlay_var.set(bool(state.get("show_rect_overlay", True)))
            self.start_number_var.set(int(state.get("start_number", 1)))
            self.digit_count_var.set(int(state.get("digit_count", 4)))
            self.ticket_count_var.set(int(state.get("ticket_count", 50)))

            output_dir = state.get("output_dir")
            if output_dir:
                self.output_dir = Path(output_dir)
            self.output_folder_button.configure(text=self._format_output_button_text())

            if not state.get("rect_settings_expanded", True):
                self.rect_settings_expanded = True
                self._toggle_rect_settings()

            template_path = state.get("template_path")
            if template_path and Path(template_path).exists():
                self._load_template_file(
                    Path(template_path), show_error=False, reset_rectangle=False
                )
        finally:
            self._loading_state = False

        self._customize_undo_stack.clear()
        self._customize_redo_stack.clear()
        self._clear_customize_action_group()
        self._update_customize_undo_redo_buttons()
        self._flush_preview_refresh()

    def _on_close(self):
        self._flush_preview_refresh()
        self._flush_save_state()
        self.destroy()


if __name__ == "__main__":
    app = RaffleDesktopApp()
    app.mainloop()
