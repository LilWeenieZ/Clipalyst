import datetime
import customtkinter as ctk

# ── Design tokens shared with search window ────────────────────────────────
_SURFACE   = "#141414"          # card background
_SURFACE_H = "#1c1c1c"          # card hover
_SURFACE_S = "#0d1a33"          # card selected (blue tint)
_BORDER    = "#272727"          # subtle borders
_MUTED     = "#6b7280"          # secondary text
_TEXT      = "#f0f0f0"          # primary text
_BLUE      = "#3b82f6"          # accent blue
_BLUE_D    = "#1d4ed8"          # darker blue
_BLUE_DIM  = "#0d1a33"          # hover bg for buttons

# Badge colours: (bg, fg)
BADGE_MAP: dict[str, tuple[str, str]] = {
    "url":     ("#1a2a3a", "#60a5fa"),
    "code":    ("#1a2e1a", "#34d399"),
    "email":   ("#1a2e1a", "#4ade80"),
    "phone":   ("#2e1a0a", "#fb923c"),
    "path":    ("#1a2a3a", "#38bdf8"),
    "address": ("#1a2a3a", "#38bdf8"),
    "name":    ("#1a2233", "#7dd3fc"),
    "number":  ("#2a1e00", "#fbbf24"),
    "text":    ("#1e1e1e", "#94a3b8"),
    "general": ("#1e1e1e", "#94a3b8"),
    "api_key": ("#1e1428", "#a78bfa"),
}
_DEFAULT_BADGE = ("#1e1e1e", "#94a3b8")
PREVIEW_LEN = 100
WINDOW_W = 660


def _rel_time(ts_str: str) -> str:
    """Convert SQLite CURRENT_TIMESTAMP (UTC) string -> short relative label."""
    try:
        ts = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        delta = datetime.datetime.utcnow() - ts
        s = int(delta.total_seconds())
        if s < 0:     return "just now"
        if s < 60:    return "just now"
        if s < 3600:  return f"{s // 60}m ago"
        if s < 86400: return f"{s // 3600}h ago"
        return f"{s // 86400}d ago"
    except Exception:
        return ""


class ResultRow(ctk.CTkFrame):
    """A single polished result card."""

    def __init__(self, parent, item: dict, on_click, on_right_click, **kw):
        super().__init__(
            parent,
            fg_color=_SURFACE,
            corner_radius=12,
            border_width=1,
            border_color=_BORDER,
            **kw,
        )
        self._item           = item
        self._on_click       = on_click
        self._on_right_click = on_right_click
        self._selected       = False
        self._hovered        = False

        self._build()
        self._bind_events()

    def _build(self):
        item     = self._item
        ctype    = (item.get("content_type") or "general").lower()
        ai_label = item.get("ai_label") or ""
        content  = item.get("content") or ""
        ts       = item.get("copied_at") or ""
        pinned   = bool(item.get("pinned"))

        badge_bg, badge_fg = BADGE_MAP.get(ctype, _DEFAULT_BADGE)

        preview = content[:PREVIEW_LEN].replace("\n", " ").replace("\r", "")
        if len(content) > PREVIEW_LEN:
            preview += "..."

        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=12, pady=9)

        top = ctk.CTkFrame(wrap, fg_color="transparent")
        top.pack(fill="x")

        ctk.CTkLabel(
            top,
            text=f"  {ctype}  ",
            font=("Inter", 9, "bold"),
            fg_color=badge_bg,
            text_color=badge_fg,
            corner_radius=5,
            height=20,
        ).pack(side="left", padx=(0, 8))

        if pinned:
            ctk.CTkLabel(
                top, text="📌",
                font=("Inter", 11),
                text_color=_BLUE,
            ).pack(side="left", padx=(0, 4))

        display_label = ai_label if ai_label else ctype.capitalize()
        ctk.CTkLabel(
            top,
            text=display_label,
            font=("Inter", 12, "bold"),
            text_color=_TEXT,
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            top,
            text=_rel_time(ts),
            font=("Inter", 10),
            text_color=_MUTED,
            anchor="e",
        ).pack(side="right")

        if preview:
            ctk.CTkLabel(
                wrap,
                text=preview,
                font=("Inter", 11),
                text_color=_MUTED,
                anchor="w",
                wraplength=WINDOW_W - 90,
                justify="left",
            ).pack(fill="x", pady=(5, 0))

        self._all_widgets = self.winfo_children()

    def set_selected(self, sel: bool):
        self._selected = sel
        self._refresh_bg()

    def _refresh_bg(self):
        if self._selected:
            colour = _SURFACE_S
        elif self._hovered:
            colour = _SURFACE_H
        else:
            colour = _SURFACE
        self.configure(fg_color=colour, border_color=_BLUE if self._selected else _BORDER)

    def _on_enter(self, _e=None):
        self._hovered = True
        self._refresh_bg()

    def _on_leave(self, _e=None):
        self._hovered = False
        self._refresh_bg()

    def _bind_events(self):
        def _all_descendants(widget):
            """Yield widget and all of its descendants recursively."""
            yield widget
            for child in widget.winfo_children():
                yield from _all_descendants(child)

        for w in _all_descendants(self):
            try:
                w.bind("<Enter>",    self._on_enter)
                w.bind("<Leave>",    self._on_leave)
                w.bind("<Button-1>", lambda _e: self._on_click(self._item))
                w.bind("<Button-3>", lambda e:  self._on_right_click(e, self._item))
            except Exception:
                pass
