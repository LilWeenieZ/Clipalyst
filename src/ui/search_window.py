"""
search_window.py — Floating search UI for Clipalyst (v2).

Features:
  - Frameless CTkToplevel, 660×530, top-centre of screen
  - Live-filtering search with debounce via StringVar trace
  - Scrollable result cards: badge · AI label · preview · timestamp
  - Left-click  → copy full content & close
  - Right-click → context menu (Copy / Pin · Unpin / Delete)
  - ↑ / ↓       → keyboard navigation through results
  - Enter        → select highlighted result
  - Escape       → close
  - show() / hide() public API
"""

import datetime
import tkinter as tk
import tkinter.messagebox as _msgbox
import customtkinter as ctk
import win32clipboard
import webbrowser

from ..config import THEME_COLOR, BG_COLOR, TEXT_COLOR, ACCENT_COLOR
from ..licence import FREE_LIMIT, FREE_PIN_LIMIT
from .result_card import (
    ResultRow, BADGE_MAP, _DEFAULT_BADGE, 
    _SURFACE, _SURFACE_H, _SURFACE_S, _BORDER, _MUTED, _TEXT, _BLUE, _BLUE_D, _BLUE_DIM,
    WINDOW_W
)

# ── Design tokens ────────────────────────────────────────────────────────────
WINDOW_H = 530
_BG        = "#0a0a0a"          # true near-black

# ── Helpers ──────────────────────────────────────────────────────────────────

def _to_clip(text: str) -> None:
    """Write text to the Windows clipboard."""
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()

# ── Main window ──────────────────────────────────────────────────────────────

class SearchWindow(ctk.CTkToplevel):
    """Floating clipboard-search window."""

    def __init__(self, 
                 on_select=None, 
                 search_callback=None, 
                 stats_callback=None, 
                 pin_callback=None, 
                 delete_callback=None,
                 is_pro_callback=None,
                 api_status_callback=None,
                 clear_callback=None,
                 show_settings_callback=None):
        super().__init__()
        self.on_select              = on_select
        self.search_callback        = search_callback
        self.stats_callback         = stats_callback
        self.pin_callback           = pin_callback
        self.delete_callback        = delete_callback
        self.is_pro_callback        = is_pro_callback
        self.api_status_callback    = api_status_callback
        self.clear_callback         = clear_callback
        self.show_settings_callback = show_settings_callback

        self._rows: list[ResultRow] = []
        self._dividers: list[ctk.CTkFrame] = []   # section-divider widgets
        self._sel_idx      = -1
        self._ctx_menu: tk.Menu | None = None
        self._debounce_id  = None
        self._poll_id      = None
        self._active_filters = []

        self._configure_window()
        self._build_ui()
        self.refresh_results()

        # Kick off periodic API-status refresh (every 5 s)
        self.after(2000, self._refresh_api_status)

        # Global keybinds
        self.bind("<Escape>", lambda _: self.hide())
        self.bind("<Down>",   lambda _: self._move_sel(+1))
        self.bind("<Up>",     lambda _: self._move_sel(-1))
        self.bind("<Return>", lambda _: self._confirm_sel())

    # ── Window config ─────────────────────────────────────────────────────────

    def _configure_window(self):
        self.title("Clipalyst")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.97)

        sw = self.winfo_screenwidth()
        x  = (sw - WINDOW_W) // 2
        self.geometry(f"{WINDOW_W}x{WINDOW_H}+{x}+60")
        self.configure(fg_color=_BG)
        self.resizable(False, False)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Outer rounded card with border
        outer = ctk.CTkFrame(
            self,
            fg_color="#111111",
            corner_radius=18,
            border_width=1,
            border_color=_BORDER,
        )
        outer.pack(fill="both", expand=True, padx=1, pady=1)

        # ── Header ────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(outer, fg_color="transparent", height=54)
        hdr.pack(fill="x", padx=18, pady=(14, 0))
        hdr.pack_propagate(False)

        # Right-side widgets (packed first so they anchor to the right edge)
        ctk.CTkButton(
            hdr, text="✕",
            width=32, height=32,
            fg_color="transparent",
            hover_color=_BLUE_DIM,
            text_color=_MUTED,
            font=("Inter", 13),
            corner_radius=8,
            command=self.hide,
        ).pack(side="right")

        ctk.CTkButton(
            hdr, text="⚙",
            width=32, height=32,
            fg_color="transparent",
            hover_color=_BLUE_DIM,
            text_color=_MUTED,
            font=("Inter", 14),
            corner_radius=8,
            command=self._open_settings,
        ).pack(side="right", padx=(0, 2))

        tier_text = "Pro" if (self.is_pro_callback and self.is_pro_callback()) else "Free"
        self._tier_lbl = ctk.CTkLabel(
            hdr, text=tier_text,
            font=("Inter", 9, "bold"),
            text_color=_BLUE,
            fg_color=_BLUE_DIM,
            corner_radius=4,
            width=32, height=18,
        )
        self._tier_lbl.pack(side="right", padx=(0, 6))

        # Left-side widgets
        icon_lbl = ctk.CTkLabel(
            hdr, text="⬡",
            font=("Inter", 18),
            text_color=_BLUE,
            width=24,
        )
        icon_lbl.pack(side="left", padx=(0, 8))

        title_lbl = ctk.CTkLabel(
            hdr, text="Clipalyst",
            font=("Inter", 15, "bold"),
            text_color=_TEXT,
        )
        title_lbl.pack(side="left")

        sub_lbl = ctk.CTkLabel(
            hdr, text="·  clipboard history",
            font=("Inter", 12),
            text_color=_MUTED,
        )
        sub_lbl.pack(side="left", padx=(6, 0), pady=(1, 0))

        # ── Thin divider ──────────────────────────────────────────────────
        sep = ctk.CTkFrame(outer, fg_color=_BORDER, height=1)
        sep.pack(fill="x", padx=18, pady=(10, 0))
        sep.pack_propagate(False)

        # Make header + divider draggable (bind on frame AND child labels)
        for _drag_w in (hdr, icon_lbl, title_lbl, sub_lbl, sep):
            _drag_w.bind("<ButtonPress-1>", self._start_move, add="+")
            _drag_w.bind("<B1-Motion>",     self._do_move,    add="+")

        # ── API Status row ────────────────────────────────────────────────
        api_row = ctk.CTkFrame(outer, fg_color="transparent", height=20)
        api_row.pack(fill="x", padx=22, pady=(7, 0))
        api_row.pack_propagate(False)

        self._api_dot_lbl = ctk.CTkLabel(
            api_row, text="●",
            font=("Inter", 9),
            text_color=_MUTED,
            width=14,
        )
        self._api_dot_lbl.pack(side="left")

        self._api_status_lbl = ctk.CTkLabel(
            api_row,
            text="Initialising…",
            font=("Inter", 10),
            text_color=_MUTED,
            anchor="w",
        )
        self._api_status_lbl.pack(side="left", padx=(2, 0))

        # ── Search bar ────────────────────────────────────────────────────
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._schedule_query())

        bar_wrap = ctk.CTkFrame(outer, fg_color="transparent")
        bar_wrap.pack(fill="x", padx=14, pady=(12, 4))

        self._entry = ctk.CTkEntry(
            bar_wrap,
            textvariable=self._search_var,
            placeholder_text="  🔍  Search clipboard history…",
            font=("Inter", 13),
            height=42,
            fg_color=_SURFACE,
            border_color=_BLUE,
            border_width=2,
            text_color=_TEXT,
            placeholder_text_color=_MUTED,
            corner_radius=12,
        )
        self._entry.pack(fill="x")

        # ── Count + Filter button row ─────────────────────────────────────
        count_row = ctk.CTkFrame(outer, fg_color="transparent")
        count_row.pack(fill="x", padx=14, pady=(0, 2))

        self._count_var = ctk.StringVar()
        ctk.CTkLabel(
            count_row,
            textvariable=self._count_var,
            font=("Inter", 10),
            text_color=_MUTED,
            anchor="w",
        ).pack(side="left", padx=(6, 0))

        # Filter toggle button (compact, always visible)
        self._filter_add_btn = ctk.CTkButton(
            count_row,
            text="+ Filter",
            width=70,
            height=22,
            fg_color=_SURFACE,
            hover_color=_BLUE_DIM,
            text_color=_BLUE,
            font=("Inter", 11, "bold"),
            corner_radius=8,
            command=self._show_filter_menu
        )
        self._filter_add_btn.pack(side="right")

        # Clear All button — removes all non-pinned items
        ctk.CTkButton(
            count_row,
            text="Clear All",
            width=72,
            height=22,
            fg_color=_SURFACE,
            hover_color="#2d1219",
            text_color="#ef4444",
            font=("Inter", 11, "bold"),
            corner_radius=8,
            command=self._clear_all,
        ).pack(side="right", padx=(0, 6))

        # ── Active-filter chips row (hidden until filters are set) ────────
        self._filter_frame = ctk.CTkFrame(outer, fg_color="transparent")
        # Do NOT pack yet — shown in _refresh_filter_bar when needed
        self._chips_frame = ctk.CTkFrame(self._filter_frame, fg_color="transparent")
        self._chips_frame.pack(side="left", fill="x", expand=True)

        # ── Scrollable results ────────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(
            outer,
            fg_color="transparent",
            scrollbar_button_color=_BORDER,
            scrollbar_button_hover_color=_BLUE,
        )
        self._scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Empty-state label (hidden until needed)
        self._empty_lbl = ctk.CTkLabel(
            self._scroll,
            text="",          # set dynamically
            font=("Inter", 13),
            text_color=_MUTED,
        )

        # ── Upgrade Banner ────────────────────────────────────────────────
        self._banner = ctk.CTkFrame(
            outer,
            fg_color="#1a1a1a",
            height=50,
            border_width=1,
            border_color=_BORDER,
            corner_radius=12
        )
        # We will pack/unpack this in refresh_results
        
        banner_content = ctk.CTkFrame(self._banner, fg_color="transparent")
        banner_content.pack(fill="both", expand=True, padx=15)

        self._banner_lbl = ctk.CTkLabel(
            banner_content,
            text=f"Free tier: {FREE_LIMIT} items · {FREE_PIN_LIMIT} pinned. Upgrade to Pro for unlimited clipboard history & pinned items.",
            font=("Inter", 11),
            text_color=_TEXT,
            anchor="w"
        )
        self._banner_lbl.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            banner_content,
            text="Upgrade",
            width=80,
            height=28,
            fg_color=_BLUE,
            hover_color=_BLUE_D,
            text_color="white",
            font=("Inter", 11, "bold"),
            corner_radius=8,
            command=lambda: webbrowser.open("https://yoursite.com/upgrade")
        ).pack(side="right")

    # ── Dragging ──────────────────────────────────────────────────────────────

    def _start_move(self, event):
        self._x = event.x
        self._y = event.y

    def _do_move(self, event):
        x = self.winfo_x() + (event.x - self._x)
        y = self.winfo_y() + (event.y - self._y)
        self.geometry(f"+{x}+{y}")

    # ── Search logic ──────────────────────────────────────────────────────────

    def _schedule_query(self):
        if self._debounce_id:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(200, self._on_query)

    def _on_query(self):
        self._sel_idx = -1
        self.refresh_results(self._search_var.get().strip())

    def refresh_results(self, query: str = ""):
        # Optimization: Limit to top 50 matches for performance
        items = self.search_callback(query, tags=self._active_filters, limit=50) if self.search_callback else []
        n = len(items)

        # ── Banner Visibility (always update, even on fast-path) ─────────────
        stats = self.stats_callback() if self.stats_callback else {}
        total  = stats.get("total_items",  0)
        pinned = stats.get("pinned_items", 0)
        is_pro = self.is_pro_callback() if self.is_pro_callback else False

        if not is_pro and (total >= FREE_LIMIT or pinned >= FREE_PIN_LIMIT):
            self._banner.pack(side="bottom", fill="x", padx=14, pady=(0, 14))
        else:
            self._banner.pack_forget()

        # Fast path: skip rebuild if IDs, pin state, and AI tag all match.
        # content_type is included so that async AI tagging updates are
        # reflected immediately without needing a manual search/filter.
        new_state = [(item.get("id"), bool(item.get("pinned")), item.get("content_type")) for item in items]
        old_state = [(row._item.get("id"), bool(row._item.get("pinned")), row._item.get("content_type")) for row in self._rows]
        if new_state == old_state:
            self._count_var.set(self._format_count(n, total, pinned, is_pro) if n else self._format_count(0, total, pinned, is_pro))
            return

        # Tear down existing rows and dividers
        for row in self._rows:
            row.destroy()
        self._rows.clear()
        for div in self._dividers:
            div.destroy()
        self._dividers.clear()
        self._empty_lbl.pack_forget()

        if not items:
            msg = "No results found." if query else "Your clipboard history is empty."
            self._empty_lbl.configure(text=f"\n{msg}")
            self._empty_lbl.pack(pady=30)
            self._count_var.set(self._format_count(0, total, pinned, is_pro))
            return

        self._count_var.set(self._format_count(n, total, pinned, is_pro))

        pinned_items   = [item for item in items if item.get("pinned")]
        unpinned_items = [item for item in items if not item.get("pinned")]
        has_both = bool(pinned_items) and bool(unpinned_items)

        def _render_section(section_items):
            for item in section_items:
                row = ResultRow(
                    self._scroll, item,
                    on_click=self._handle_click,
                    on_right_click=self._handle_right_click,
                )
                row.pack(fill="x", padx=3, pady=3)
                self._rows.append(row)

        _render_section(pinned_items)

        if has_both:
            # ── Divider between pinned and unpinned ───────────────────────
            div_wrap = ctk.CTkFrame(self._scroll, fg_color="transparent")
            div_wrap.pack(fill="x", padx=6, pady=(6, 2))
            self._dividers.append(div_wrap)

            ctk.CTkFrame(
                div_wrap, fg_color=_BORDER, height=1,
            ).pack(fill="x", side="left", expand=True, pady=7)

            ctk.CTkLabel(
                div_wrap,
                text="  Recent  ",
                font=("Inter", 10, "bold"),
                text_color=_MUTED,
                fg_color="transparent",
            ).pack(side="left")

            ctk.CTkFrame(
                div_wrap, fg_color=_BORDER, height=1,
            ).pack(fill="x", side="left", expand=True, pady=7)

        _render_section(unpinned_items)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _format_count(self, n: int, total: int, pinned: int, is_pro: bool) -> str:
        """Return the items/pinned counter string appropriate for the tier."""
        if is_pro:
            return f"{n} item{'s' if n != 1 else ''}"
        return f"{total}/{FREE_LIMIT} items   {pinned}/{FREE_PIN_LIMIT} Pinned"

    # ── Filter Logic ──────────────────────────────────────────────────────────

    def _show_filter_menu(self):
        """Show a menu of available tags to filter by."""
        menu = tk.Menu(
            self, tearoff=False,
            bg=_SURFACE, fg=_TEXT,
            activebackground=_BLUE_D,
            activeforeground="#ffffff",
            bd=0, font=("Inter", 11),
        )
        
        # Get all distinct tags from BADGE_MAP (sorted)
        available_tags = sorted(BADGE_MAP.keys())
        
        for tag in available_tags:
            is_active = tag in self._active_filters
            label = f"  {'✓ ' if is_active else '  '}{tag.capitalize()}"
            menu.add_command(
                label=label,
                command=lambda t=tag: self._toggle_filter(t)
            )
            
        # Add clear all option if any filters exist
        if self._active_filters:
            menu.add_separator()
            menu.add_command(
                label="  Clear All",
                command=self._clear_filters,
                foreground="#ef4444"
            )
            
        x = self.winfo_x() + self._filter_add_btn.winfo_x()
        y = self.winfo_y() + self._filter_add_btn.winfo_y() + 60
        menu.tk_popup(x, y)

    def _toggle_filter(self, tag: str):
        if tag in self._active_filters:
            self._active_filters.remove(tag)
        else:
            self._active_filters.append(tag)
        self._refresh_filter_bar()
        self.refresh_results(self._search_var.get().strip())

    def _clear_filters(self):
        self._active_filters.clear()
        self._refresh_filter_bar()
        self.refresh_results(self._search_var.get().strip())

    def _refresh_filter_bar(self):
        """Update the chips row based on active filters."""
        # Clear existing chips
        for widget in self._chips_frame.winfo_children():
            widget.destroy()

        if not self._active_filters:
            # Collapse the entire chips row when no filters are active
            self._filter_frame.pack_forget()
            return

        # Insert the filter chip bar between the search controls and the
        # results list.  We cannot use pack's `before=` option with a
        # CTkScrollableFrame because Tkinter resolves the reference to the
        # internal canvas widget path (not self._scroll), which raises a
        # TclError.  Instead, we temporarily un-pack the scroll frame, pack
        # the filter bar, then re-pack scroll — achieving the same order.
        self._scroll.pack_forget()
        self._filter_frame.pack(fill="x", padx=14, pady=(0, 4))
        self._scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        MAX_CHIPS = 3
        visible_filters = self._active_filters[:MAX_CHIPS]
        overflow_count = len(self._active_filters) - MAX_CHIPS
        
        for tag in visible_filters:
            self._create_chip(tag)
            
        if overflow_count > 0:
            self._create_overflow_button(len(self._active_filters))

    def _create_chip(self, tag: str):
        bg, fg = BADGE_MAP.get(tag, _DEFAULT_BADGE)
        
        chip = ctk.CTkFrame(self._chips_frame, fg_color=bg, corner_radius=6, height=24)
        chip.pack(side="left", padx=(0, 6))
        
        ctk.CTkLabel(
            chip, text=tag.capitalize(),
            font=("Inter", 11, "bold"),
            text_color=fg,
            height=24
        ).pack(side="left", padx=(8, 4))
        
        ctk.CTkButton(
            chip, text="✕",
            width=16, height=16,
            fg_color="transparent",
            hover_color=_BLUE_D, # Use solid color instead of rgba
            text_color=fg,
            font=("Inter", 10, "bold"),
            corner_radius=4,
            command=lambda t=tag: self._toggle_filter(t)
        ).pack(side="left", padx=(0, 4))

    def _create_overflow_button(self, total: int):
        ctk.CTkButton(
            self._chips_frame,
            text=f"List all ({total})",
            width=80,
            height=24,
            fg_color=_SURFACE_H,
            hover_color=_BLUE_DIM,
            text_color=_MUTED,
            font=("Inter", 10, "bold"),
            corner_radius=6,
            command=self._show_filter_menu  # Re-use the menu for now as a summary
        ).pack(side="left")

    # ── Keyboard navigation ───────────────────────────────────────────────────

    def _move_sel(self, delta: int):
        if not self._rows:
            return
        n = len(self._rows)
        if 0 <= self._sel_idx < n:
            self._rows[self._sel_idx].set_selected(False)
        self._sel_idx = max(0, min(n - 1, self._sel_idx + delta))
        self._rows[self._sel_idx].set_selected(True)

    def _confirm_sel(self):
        if 0 <= self._sel_idx < len(self._rows):
            self._handle_click(self._rows[self._sel_idx]._item)

    # ── Click handlers ────────────────────────────────────────────────────────

    def _handle_click(self, item: dict):
        try:
            _to_clip(item.get("content", ""))
        except Exception:
            pass
        if self.on_select:
            self.on_select(item.get("content", ""))
        self.hide()

    def _handle_right_click(self, event: tk.Event, item: dict):
        self._dismiss_ctx()
        is_pinned = bool(item.get("pinned"))

        # ── Custom popup (matches app dark aesthetic) ─────────────────────
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg=_BORDER)          # thin border via bg bleed

        card = ctk.CTkFrame(
            popup,
            fg_color="#1c1c1e",
            corner_radius=10,
            border_width=1,
            border_color=_BORDER,
        )
        card.pack(padx=1, pady=1)

        _BTN_CFG = dict(
            width=150, height=28,
            anchor="w",
            fg_color="transparent",
            hover_color=_BLUE_DIM,
            text_color=_TEXT,
            font=("Inter", 12),
            corner_radius=5,
        )

        def _close(action):
            popup.destroy()
            self._ctx_menu = None
            action()

        ctk.CTkButton(
            card, text="  Copy", **_BTN_CFG,
            command=lambda: _close(lambda: self._ctx_copy(item)),
        ).pack(padx=4, pady=(4, 1))

        ctk.CTkFrame(card, fg_color=_BORDER, height=1).pack(fill="x", padx=6, pady=1)

        pin_label = "  Unpin" if is_pinned else "  Pin"
        ctk.CTkButton(
            card, text=pin_label, **_BTN_CFG,
            command=lambda: _close(lambda: self._ctx_pin(item, is_pinned)),
        ).pack(padx=4, pady=1)

        ctk.CTkFrame(card, fg_color=_BORDER, height=1).pack(fill="x", padx=6, pady=1)

        ctk.CTkButton(
            card, text="  Delete",
            **{**_BTN_CFG, "text_color": "#ef4444", "hover_color": "#2d1219"},
            command=lambda: _close(lambda: self._ctx_delete(item)),
        ).pack(padx=4, pady=(1, 4))

        self._ctx_menu = popup

        # Position near cursor, nudge inside screen edges
        popup.update_idletasks()
        pw = popup.winfo_reqwidth()
        ph = popup.winfo_reqheight()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = min(event.x_root, sw - pw - 4)
        y = min(event.y_root, sh - ph - 4)
        popup.geometry(f"+{x}+{y}")

        # Dismiss when focus leaves the popup
        popup.bind("<FocusOut>", lambda _: self._dismiss_ctx())
        popup.focus_set()

    def _dismiss_ctx(self):
        if self._ctx_menu:
            try:
                self._ctx_menu.destroy()
            except Exception:
                pass
            self._ctx_menu = None

    def _ctx_copy(self, item: dict):
        try:
            _to_clip(item.get("content", ""))
        except Exception:
            pass

    def _ctx_pin(self, item: dict, currently_pinned: bool):
        iid = item.get("id")
        if iid is None or not self.pin_callback:
            return

        # Enforce pinned-item limit for free tier
        if not currently_pinned:
            is_pro = self.is_pro_callback() if self.is_pro_callback else False
            if not is_pro:
                stats  = self.stats_callback() if self.stats_callback else {}
                pinned = stats.get("pinned_items", 0)
                if pinned >= FREE_PIN_LIMIT:
                    p = self._dialog_parent()
                    _msgbox.showinfo(
                        "Pin limit reached",
                        f"Free tier allows up to {FREE_PIN_LIMIT} pinned items.\n"
                        "Upgrade to Pro to pin unlimited items.",
                        parent=p,
                    )
                    p.destroy()
                    return

        self.pin_callback(iid, not currently_pinned)
        self.refresh_results(self._search_var.get().strip())

    def _ctx_delete(self, item: dict):
        iid = item.get("id")
        if iid is None or not self.delete_callback:
            return
        self.delete_callback(iid)
        self.refresh_results(self._search_var.get().strip())

    # ── API Status ────────────────────────────────────────────────────────────

    def _refresh_api_status(self) -> None:
        """Update the API status row and reschedule itself every 5 seconds."""
        _GREEN = "#22c55e"
        _AMBER = "#f59e0b"
        _RED   = "#ef4444"

        if self.api_status_callback:
            s       = self.api_status_callback()
            ready   = s.get("ready", False)
            error   = s.get("error")        # None → last op was OK
            tagged  = s.get("tags_processed", 0)

            if not ready:
                dot_col = _AMBER
                status  = "No API key — AI tagging disabled"
            elif error:
                dot_col = _RED
                status  = f"API error: {error}"
            else:
                dot_col = _GREEN
                status  = "API ready · claude-haiku-4-5"
                if tagged:
                    status += f"  ·  {tagged} tagged"
        else:
            dot_col = _MUTED
            status  = ""

        try:
            self._api_dot_lbl.configure(text_color=dot_col)
            self._api_status_lbl.configure(text=status)
        except Exception:
            pass  # widget may not exist yet in rare race conditions

        # Reschedule every 5 s
        self.after(5000, self._refresh_api_status)

    # ── Live polling ──────────────────────────────────────────────────────────

    def _start_polling(self) -> None:
        """Begin a 1.5-second refresh loop so new clipboard items appear
        automatically while the window is open."""
        self._stop_polling()          # cancel any existing loop first
        self._poll_results()

    def _stop_polling(self) -> None:
        """Cancel the live-refresh loop."""
        if self._poll_id is not None:
            self.after_cancel(self._poll_id)
            self._poll_id = None

    def _poll_results(self) -> None:
        """Refresh the result list then reschedule itself every 1.5 s."""
        self.refresh_results(self._search_var.get().strip())
        self._poll_id = self.after(1500, self._poll_results)

    # ── Settings ──────────────────────────────────────────────────────────────

    def _dialog_parent(self) -> tk.Toplevel:
        """Return a transient hidden Toplevel centred over the search window.

        tkinter's messagebox dialogs position themselves relative to their
        parent window.  Because SearchWindow uses overrideredirect(True) it
        cannot serve as a WM-managed parent on Windows, so we create a
        temporary, invisible stand-in that *is* WM-managed and destroy it
        immediately after the dialog closes.
        """
        t = tk.Toplevel(self)
        t.withdraw()
        t.attributes("-topmost", True)
        x = self.winfo_x() + (WINDOW_W  // 2) - 150
        y = self.winfo_y() + (WINDOW_H // 2) - 60
        t.geometry(f"+{x}+{y}")
        return t

    # ── Clear All ─────────────────────────────────────────────────────────────

    def _clear_all(self) -> None:
        """Delete all non-pinned items after confirmation.
        Pinned items are NEVER deleted.
        """
        if not self.clear_callback:
            return
        p = self._dialog_parent()
        confirmed = _msgbox.askyesno(
            "Clear history",
            "Delete all clipboard history?\n\nPinned items will be kept.",
            icon="warning",
            parent=p,
        )
        p.destroy()
        if confirmed:
            self.clear_callback()
            self.refresh_results(self._search_var.get().strip())

    # ── Settings ──────────────────────────────────────────────────────────────

    def _open_settings(self) -> None:
        """Open the settings window."""
        if self.show_settings_callback:
            self.show_settings_callback()

    # ── Public API ────────────────────────────────────────────────────────────


    def show(self):
        """Make the window visible, re-centred and focused."""
        sw = self.winfo_screenwidth()
        x  = (sw - WINDOW_W) // 2
        self.geometry(f"{WINDOW_W}x{WINDOW_H}+{x}+60")
        self._search_var.set("")
        self._sel_idx = -1
        self.refresh_results()
        self._refresh_api_status()   # immediate update on every open
        self._start_polling()        # begin live clipboard polling
        self.deiconify()
        self.lift()
        self.focus_force()
        self._entry.focus_set()

    def hide(self):
        """Hide without destroying."""
        self._stop_polling()          # stop live polling while hidden
        self._dismiss_ctx()
        self.withdraw()


# ── Standalone preview ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tkinter as _tk

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    root = _tk.Tk()
    root.withdraw()

    win = SearchWindow()
    win.show()
    win.protocol("WM_DELETE_WINDOW", root.quit)

    root.mainloop()
