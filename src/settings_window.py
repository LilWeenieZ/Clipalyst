"""
settings_window.py — Settings panel for Clipalyst.

Features:
  - History limit slider (free: 1-50, pro: 1-5000)
  - Auto-delete option menu
  - Editable global hotkey
  - Launch at Windows startup toggle
  - AI Model selection (Pro only)
  - Advanced Settings accordion: ignore list + danger zone
  - Upgrade to Pro button
"""

import webbrowser
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from .startup import enable_startup, disable_startup, is_startup_enabled
from .bug_report import open_bug_report
from . import licence as _licence

# ── Design tokens (match search_window palette) ───────────────────────────────
_BG       = "#111111"
_SURFACE  = "#1c1c1e"
_BORDER   = "#2a2a2e"
_TEXT     = "#e2e8f0"
_MUTED    = "#64748b"
_BLUE     = "#3b82f6"
_BLUE_D   = "#2563eb"
_BLUE_DIM = "#1e3a5f"
_RED      = "#dc2626"
_RED_D    = "#b91c1c"
_GOLD     = "#f59e0b"
_GOLD_DIM = "#78350f"


class SettingsWindow(ctk.CTkToplevel):
    """Settings panel wired to SettingsManager, HotkeyManager, and AITagger."""

    def __init__(
        self,
        settings_manager,
        on_clear_history,
        hotkey_manager=None,
        is_pro_callback=None,
        tagger_reconfigure_callback=None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.settings_manager            = settings_manager
        self.on_clear_history            = on_clear_history
        self.hotkey_manager              = hotkey_manager
        self._is_pro                     = bool(is_pro_callback and is_pro_callback())
        self._tagger_reconfigure         = tagger_reconfigure_callback

        self.title("Settings — Clipalyst")
        self.geometry("420x660")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color=_BG)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Scrollable main area
        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=_BG,
            scrollbar_button_color=_BORDER,
            scrollbar_button_hover_color=_BLUE,
        )
        scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        scroll.grid_columnconfigure(0, weight=1)

        self._build_ui(scroll)

        # Intercept the close button so the window is hidden, not destroyed.
        self.protocol("WM_DELETE_WINDOW", self.hide)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self, parent):
        row = 0

        # ── Header ────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.grid(row=row, column=0, sticky="ew", padx=20, pady=(20, 4))
        hdr.grid_columnconfigure(0, weight=1)
        row += 1

        ctk.CTkLabel(
            hdr, text="⚙  Settings",
            font=("Inter", 17, "bold"),
            text_color=_TEXT,
        ).grid(row=0, column=0, sticky="w")

        # ── Upgrade to Pro ────────────────────────────────────────────────
        if not self._is_pro:
            btn = ctk.CTkButton(
                parent,
                text="⭐  Upgrade to Pro",
                height=38,
                fg_color=_GOLD_DIM,
                hover_color=_GOLD,
                text_color=_GOLD,
                font=("Inter", 13, "bold"),
                corner_radius=10,
                command=lambda: webbrowser.open("https://yoursite.com/upgrade"),
            )
            btn.grid(row=row, column=0, sticky="ew", padx=20, pady=(4, 16))
            btn.bind("<Enter>", lambda e: btn.configure(text_color="white"))
            btn.bind("<Leave>", lambda e: btn.configure(text_color=_GOLD))
        row += 1

        # ── Section: History ──────────────────────────────────────────────
        self._section_label(parent, row, "History")
        row += 1

        card = self._card(parent, row)
        row += 1

        self._hist_label = ctk.CTkLabel(
            card, text=f"History Limit: {self.settings_manager.get('history_limit')}",
            font=("Inter", 12), text_color=_TEXT, anchor="w",
        )
        self._hist_label.pack(fill="x", padx=16, pady=(14, 4))

        self._make_slider(card)

        ctk.CTkLabel(
            card, text="Auto-delete older than:",
            font=("Inter", 12), text_color=_MUTED, anchor="w",
        ).pack(fill="x", padx=16, pady=(10, 4))

        self.auto_delete_menu = ctk.CTkOptionMenu(
            card,
            values=["7 days", "30 days", "90 days", "Never"],
            fg_color=_SURFACE, button_color=_BLUE, button_hover_color=_BLUE_D,
            text_color=_TEXT, font=("Inter", 12),
            command=self._on_auto_delete_change,
        )
        self.auto_delete_menu.set(self.settings_manager.get("auto_delete"))
        self.auto_delete_menu.pack(fill="x", padx=16, pady=(0, 14))

        # ── Section: Global Hotkey ────────────────────────────────────────
        self._section_label(parent, row, "Global Hotkey")
        row += 1

        hk_card = self._card(parent, row)
        row += 1

        ctk.CTkLabel(
            hk_card, text="Trigger key combination:",
            font=("Inter", 12), text_color=_MUTED, anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 8))

        cb_row = ctk.CTkFrame(hk_card, fg_color="transparent")
        cb_row.pack(fill="x", padx=16, pady=(0, 8))

        self._ctrl_var  = tk.BooleanVar(value=self.settings_manager.get("hotkey_ctrl",  True))
        self._shift_var = tk.BooleanVar(value=self.settings_manager.get("hotkey_shift", False))
        self._alt_var   = tk.BooleanVar(value=self.settings_manager.get("hotkey_alt",   True))

        for text, var in [("Ctrl", self._ctrl_var), ("Shift", self._shift_var), ("Alt", self._alt_var)]:
            ctk.CTkCheckBox(
                cb_row, text=text, variable=var,
                font=("Inter", 12), text_color=_TEXT,
                fg_color=_BLUE, hover_color=_BLUE_D,
                checkmark_color="white",
                command=self._on_hotkey_change,
            ).pack(side="left", padx=(0, 16))

        key_row = ctk.CTkFrame(hk_card, fg_color="transparent")
        key_row.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(
            key_row, text="Key:",
            font=("Inter", 12), text_color=_MUTED, width=32,
        ).pack(side="left", padx=(0, 8))

        self._key_var = ctk.StringVar(value=self.settings_manager.get("hotkey_key", "V").upper())
        key_entry = ctk.CTkEntry(
            key_row,
            textvariable=self._key_var,
            width=52, height=30,
            fg_color=_SURFACE, border_color=_BLUE, border_width=1,
            text_color=_TEXT, font=("Inter", 13, "bold"),
            corner_radius=6,
            justify="center",
        )
        key_entry.pack(side="left")
        self._key_var.trace_add("write", self._on_key_entry_change)

        self._hk_preview = ctk.CTkLabel(
            key_row,
            text=self._hotkey_preview(),
            font=("Inter", 11),
            text_color=_BLUE,
            fg_color=_BLUE_DIM,
            corner_radius=6,
            padx=10, pady=2,
        )
        self._hk_preview.pack(side="left", padx=(12, 0))

        ctk.CTkLabel(
            hk_card, text="Changes take effect immediately.",
            font=("Inter", 10), text_color=_MUTED, anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 14))

        # ── Section: System ───────────────────────────────────────────────
        self._section_label(parent, row, "System")
        row += 1

        sys_card = self._card(parent, row)
        row += 1

        self._startup_var = tk.BooleanVar(value=is_startup_enabled())
        ctk.CTkCheckBox(
            sys_card,
            text="Launch at Windows startup",
            variable=self._startup_var,
            font=("Inter", 12), text_color=_TEXT,
            fg_color=_BLUE, hover_color=_BLUE_D, checkmark_color="white",
            command=self._on_startup_toggle,
        ).pack(anchor="w", padx=16, pady=(14, 8))

        self._crash_var = tk.BooleanVar(value=self.settings_manager.get("crash_reporting_enabled", True))
        ctk.CTkCheckBox(
            sys_card,
            text="Send anonymous crash reports",
            variable=self._crash_var,
            font=("Inter", 12), text_color=_TEXT,
            fg_color=_BLUE, hover_color=_BLUE_D, checkmark_color="white",
            command=self._on_crash_report_toggle,
        ).pack(anchor="w", padx=16, pady=(8, 2))

        ctk.CTkLabel(
            sys_card,
            text="Helps improve Clipalyst. No personal data is collected. Changes take affect after restart.",
            font=("Inter", 10), text_color=_MUTED, anchor="w",
            wraplength=340, justify="left",
        ).pack(anchor="w", fill="x", padx=46, pady=(0, 14))

        # ── Section: Licence ─────────────────────────────────────────────
        self._section_label(parent, row, "Licence")
        row += 1

        lic_card = self._card(parent, row)
        row += 1

        self._build_licence_section(lic_card)

        # ── Section: AI Model (Pro only) ──────────────────────────────────
        self._section_label(parent, row, "AI Model")
        row += 1

        ai_card = self._card(parent, row)
        row += 1

        self._build_ai_model_section(ai_card)

        # ── Advanced Settings accordion ───────────────────────────────────
        self._adv_open = tk.BooleanVar(value=False)
        adv_toggle = ctk.CTkButton(
            parent,
            text="▶  Advanced Settings",
            height=34,
            fg_color=_SURFACE,
            hover_color=_BORDER,
            text_color=_MUTED,
            font=("Inter", 11, "bold"),
            corner_radius=8,
            anchor="w",
            command=self._toggle_advanced,
        )
        adv_toggle.grid(row=row, column=0, sticky="ew", padx=20, pady=(16, 2))
        self._adv_toggle_btn = adv_toggle
        row += 1

        # Advanced content (hidden by default)
        self._adv_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._adv_frame.grid_columnconfigure(0, weight=1)
        self._adv_row = row
        self._adv_parent = parent
        row += 1

        self._build_advanced_content(self._adv_frame)

        # Bottom padding
        self._bottom_pad_row = row
        ctk.CTkLabel(parent, text="", height=10, fg_color="transparent").grid(
            row=row, column=0,
        )

    # ── Licence section ───────────────────────────────────────────────────────

    def _build_licence_section(self, card):
        """Build the activation-key UI inside *card*."""
        if self._is_pro:
            self._build_licence_active(card)
        else:
            self._build_licence_inactive(card)

    def _build_licence_active(self, card):
        """Show a 'Pro active' badge + deactivate option."""
        badge_row = ctk.CTkFrame(card, fg_color="transparent")
        badge_row.pack(fill="x", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            badge_row,
            text="⭐",
            font=("Inter", 20),
            text_color=_GOLD,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            badge_row,
            text="Pro licence active",
            font=("Inter", 13, "bold"),
            text_color=_GOLD,
        ).pack(side="left")

        stored_email = self.settings_manager.get("activation_email", "")
        if stored_email:
            ctk.CTkLabel(
                card,
                text=f"Registered to: {stored_email}",
                font=("Inter", 11),
                text_color=_MUTED,
                anchor="w",
            ).pack(fill="x", padx=16, pady=(0, 6))

        ctk.CTkButton(
            card,
            text="Deactivate licence",
            height=30,
            fg_color="transparent",
            hover_color=_BORDER,
            border_color=_BORDER,
            border_width=1,
            text_color=_MUTED,
            font=("Inter", 11),
            corner_radius=8,
            command=self._on_deactivate,
        ).pack(anchor="w", padx=16, pady=(0, 14))

    def _build_licence_inactive(self, card):
        """Show email + key entry form."""
        ctk.CTkLabel(
            card,
            text="Enter the activation key you received via email to unlock Pro.",
            font=("Inter", 11),
            text_color=_MUTED,
            anchor="w",
            wraplength=340,
            justify="left",
        ).pack(fill="x", padx=16, pady=(14, 8))

        # Email field
        ctk.CTkLabel(
            card, text="Email address:",
            font=("Inter", 12), text_color=_MUTED, anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 4))

        self._lic_email_var = ctk.StringVar(
            value=self.settings_manager.get("activation_email", "")
        )
        ctk.CTkEntry(
            card,
            textvariable=self._lic_email_var,
            placeholder_text="you@example.com",
            fg_color=_SURFACE, border_color=_BORDER, border_width=1,
            text_color=_TEXT, font=("Inter", 12),
            corner_radius=6,
        ).pack(fill="x", padx=16, pady=(0, 8))

        # Activation key field
        ctk.CTkLabel(
            card, text="Activation key:",
            font=("Inter", 12), text_color=_MUTED, anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 4))

        self._lic_key_var = ctk.StringVar(
            value=self.settings_manager.get("activation_key", "")
        )
        ctk.CTkEntry(
            card,
            textvariable=self._lic_key_var,
            placeholder_text="XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX",
            fg_color=_SURFACE, border_color=_BORDER, border_width=1,
            text_color=_TEXT, font=("Inter", 12),
            corner_radius=6,
        ).pack(fill="x", padx=16, pady=(0, 8))

        # Feedback label (shown after attempt)
        self._lic_feedback = ctk.CTkLabel(
            card,
            text="",
            font=("Inter", 11),
            text_color=_MUTED,
            anchor="w",
            wraplength=340,
            justify="left",
        )
        self._lic_feedback.pack(fill="x", padx=16, pady=(0, 4))

        ctk.CTkButton(
            card,
            text="Activate Pro",
            height=34,
            fg_color=_GOLD_DIM,
            hover_color=_GOLD,
            text_color=_GOLD,
            font=("Inter", 12, "bold"),
            corner_radius=8,
            command=self._on_activate,
        ).pack(fill="x", padx=16, pady=(0, 14))

    def _on_activate(self):
        key   = self._lic_key_var.get().strip()
        email = self._lic_email_var.get().strip()
        if not key:
            self._lic_feedback.configure(
                text="Please enter your activation key.", text_color=_MUTED
            )
            return
        success, msg = _licence.activate(key, email)
        self._lic_feedback.configure(
            text=msg,
            text_color=_GOLD if success else _RED,
        )
        if success:
            # Update the in-memory Pro flag so the rest of the window can react
            self._is_pro = True

    def _on_deactivate(self):
        if not messagebox.askyesno(
            "Deactivate Licence",
            "Are you sure you want to remove your Pro licence from this device?",
            parent=self,
        ):
            return
        _licence.deactivate()
        self._is_pro = False
        messagebox.showinfo(
            "Licence Removed",
            "Your Pro licence has been deactivated. Restart the app to apply changes.",
            parent=self,
        )

    # ── AI Model section ──────────────────────────────────────────────────────

    def _build_ai_model_section(self, card):
        if not self._is_pro:
            # Locked state: show info + upsell
            lock_row = ctk.CTkFrame(card, fg_color="transparent")
            lock_row.pack(fill="x", padx=16, pady=14)

            ctk.CTkLabel(
                lock_row,
                text="🔒",
                font=("Inter", 18),
                text_color=_GOLD,
            ).pack(side="left", padx=(0, 8))

            ctk.CTkLabel(
                lock_row,
                text="Custom AI model is a Pro feature.\nUpgrade to choose your model and API key.",
                font=("Inter", 12),
                text_color=_GOLD,
                anchor="w",
                justify="left",
            ).pack(side="left", fill="x", expand=True)

            ctk.CTkLabel(
                card,
                text="Current model: claude-haiku-4-5 (default)",
                font=("Inter", 11),
                text_color=_MUTED,
                anchor="w",
            ).pack(fill="x", padx=16, pady=(0, 14))
        else:
            # Pro: editable model + API key
            ctk.CTkLabel(
                card,
                text="Model name:",
                font=("Inter", 12), text_color=_MUTED, anchor="w",
            ).pack(fill="x", padx=16, pady=(14, 4))

            self._model_var = ctk.StringVar(
                value=self.settings_manager.get("ai_model", "") or "claude-haiku-4-5"
            )
            model_entry = ctk.CTkEntry(
                card,
                textvariable=self._model_var,
                placeholder_text="claude-haiku-4-5  (recommended)",
                fg_color=_SURFACE, border_color=_BLUE, border_width=1,
                text_color=_TEXT, font=("Inter", 12),
                corner_radius=6,
            )
            model_entry.pack(fill="x", padx=16, pady=(0, 10))

            ctk.CTkLabel(
                card,
                text="API key (overrides .env):",
                font=("Inter", 12), text_color=_MUTED, anchor="w",
            ).pack(fill="x", padx=16, pady=(0, 4))

            self._apikey_var = ctk.StringVar(
                value=self.settings_manager.get("ai_api_key", "")
            )
            key_entry = ctk.CTkEntry(
                card,
                textvariable=self._apikey_var,
                placeholder_text="sk-ant-…  (leave blank to use .env)",
                show="•",
                fg_color=_SURFACE, border_color=_BLUE, border_width=1,
                text_color=_TEXT, font=("Inter", 12),
                corner_radius=6,
            )
            key_entry.pack(fill="x", padx=16, pady=(0, 10))

            ctk.CTkButton(
                card,
                text="Apply",
                height=30,
                fg_color=_BLUE, hover_color=_BLUE_D,
                text_color="white", font=("Inter", 12, "bold"),
                corner_radius=8,
                command=self._on_ai_settings_apply,
            ).pack(anchor="e", padx=16, pady=(0, 14))

    # ── Advanced Settings accordion ───────────────────────────────────────────

    def _build_advanced_content(self, parent):
        row = 0

        # Ignore list
        self._section_label(parent, row, "Ignore List")
        row += 1

        ig_card = self._card(parent, row)
        row += 1

        ctk.CTkLabel(
            ig_card, text="Don't capture from these apps (one per line):",
            font=("Inter", 12), text_color=_MUTED, anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 6))

        self.ignore_list_text = ctk.CTkTextbox(
            ig_card, height=80,
            fg_color=_SURFACE, border_color=_BORDER, border_width=1,
            text_color=_TEXT, font=("Inter", 12),
        )
        self.ignore_list_text.insert("1.0", "\n".join(self.settings_manager.get("ignore_list", [])))
        self.ignore_list_text.pack(fill="x", padx=16, pady=(0, 14))
        self.ignore_list_text.bind("<FocusOut>", self._on_ignore_list_change)

        # Report a Bug
        self._section_label(parent, row, "Report a Bug")
        row += 1

        bug_card = self._card(parent, row)
        row += 1

        ctk.CTkLabel(
            bug_card,
            text="Found an issue? Report it on GitHub to help improve Clipalyst.",
            font=("Inter", 12), text_color=_MUTED, anchor="w",
            wraplength=340, justify="left",
        ).pack(fill="x", padx=16, pady=(14, 10))

        ctk.CTkButton(
            bug_card,
            text="Open GitHub Issues",
            height=32,
            fg_color=_BLUE, hover_color=_BLUE_D,
            text_color="white", font=("Inter", 12, "bold"),
            corner_radius=8,
            command=open_bug_report,
        ).pack(fill="x", padx=16, pady=(0, 14))

        # Danger zone
        self._section_label(parent, row, "Danger Zone")
        row += 1

        danger_card = self._card(parent, row)

        ctk.CTkButton(
            danger_card,
            text="Clear all history",
            height=36,
            fg_color=_RED, hover_color=_RED_D,
            text_color="white", font=("Inter", 12, "bold"),
            corner_radius=8,
            command=self._confirm_clear,
        ).pack(fill="x", padx=16, pady=14)

    def _toggle_advanced(self):
        """Show/hide the advanced settings accordion."""
        if self._adv_open.get():
            # Collapse
            self._adv_frame.grid_remove()
            self._adv_open.set(False)
            self._adv_toggle_btn.configure(text="▶  Advanced Settings")
        else:
            # Expand
            self._adv_frame.grid(row=self._adv_row, column=0, sticky="ew", padx=0, pady=0)
            self._adv_open.set(True)
            self._adv_toggle_btn.configure(text="▼  Advanced Settings")


    # ── Widget factories ──────────────────────────────────────────────────────

    def _section_label(self, parent, row: int, text: str):
        ctk.CTkLabel(
            parent, text=text.upper(),
            font=("Inter", 10, "bold"),
            text_color=_MUTED,
            anchor="w",
        ).grid(row=row, column=0, sticky="ew", padx=24, pady=(16, 4))

    def _card(self, parent, row: int = None) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent,
            fg_color=_SURFACE,
            corner_radius=12,
            border_width=1,
            border_color=_BORDER,
        )
        if row is not None:
            card.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 2))
        card.grid_columnconfigure(0, weight=1)
        return card

    def _make_slider(self, parent) -> ctk.CTkSlider:
        """Create and pack the history-limit slider.

        Free tier : 1–50  (slider physically limited to 50).
        Pro tier  : 1–5000.
        """
        _max   = 5000 if self._is_pro else 50
        _steps = 49
        current = max(1, min(self.settings_manager.get("history_limit", 50), _max))

        self._slider = ctk.CTkSlider(
            parent,
            from_=1, to=_max, number_of_steps=_steps,
            button_color=_BLUE, button_hover_color=_BLUE_D,
            progress_color=_BLUE,
            command=self._on_slider_change,
        )
        self._slider.set(current)
        self._slider.pack(fill="x", padx=16, pady=(0, 6))

        if not self._is_pro:
            lock_row = ctk.CTkFrame(parent, fg_color="transparent")
            lock_row.pack(fill="x", padx=16, pady=(0, 8))
            ctk.CTkLabel(
                lock_row, text="🔒",
                font=("Inter", 14),
                text_color=_GOLD,
            ).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(
                lock_row,
                text="Free tier limited to 50 items — Upgrade to Pro for up to 5 000",
                font=("Inter", 11),
                text_color=_GOLD,
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

        return self._slider

    # ── Hotkey helpers ────────────────────────────────────────────────────────

    def _hotkey_preview(self) -> str:
        parts = []
        if self._ctrl_var.get():  parts.append("Ctrl")
        if self._alt_var.get():   parts.append("Alt")
        if self._shift_var.get(): parts.append("Shift")
        key = self._key_var.get().strip().upper() or "?"
        parts.append(key)
        return "+".join(parts)

    def _on_hotkey_change(self):
        self._persist_hotkey()
        self._hk_preview.configure(text=self._hotkey_preview())

    def _on_key_entry_change(self, *_):
        raw = self._key_var.get().strip()
        if raw:
            norm = raw[-1].upper()
            if norm != raw:
                self._key_var.set(norm)
                return
        self._persist_hotkey()
        try:
            self._hk_preview.configure(text=self._hotkey_preview())
        except Exception:
            pass

    def _persist_hotkey(self):
        ctrl  = self._ctrl_var.get()
        shift = self._shift_var.get()
        alt   = self._alt_var.get()
        key   = self._key_var.get().strip().upper() or "V"

        self.settings_manager.set("hotkey_ctrl",  ctrl)
        self.settings_manager.set("hotkey_shift", shift)
        self.settings_manager.set("hotkey_alt",   alt)
        self.settings_manager.set("hotkey_key",   key)

        if self.hotkey_manager:
            try:
                self.hotkey_manager.reconfigure(ctrl=ctrl, shift=shift, alt=alt, key=key)
            except Exception as exc:
                print(f"HotkeyManager.reconfigure error: {exc}")

    # ── AI model handler ────────────────────────────────────────────────────

    def _on_ai_settings_apply(self):
        if not self._is_pro:
            return
        model   = self._model_var.get().strip()
        api_key = self._apikey_var.get().strip()

        self.settings_manager.set("ai_model",   model)
        self.settings_manager.set("ai_api_key", api_key)

        if self._tagger_reconfigure:
            self._tagger_reconfigure(
                model   = model   or None,
                api_key = api_key or None,
            )

        messagebox.showinfo(
            "AI Model",
            f"Applied.\nModel: {model or 'claude-haiku-4-5 (default)'}\n"
            f"API key: {'custom' if api_key else 'from .env'}",
            parent=self,
        )

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_slider_change(self, value):
        val = int(round(value))
        self._hist_label.configure(text=f"History Limit: {val}")
        self.settings_manager.set("history_limit", val)

    def _on_auto_delete_change(self, value):
        self.settings_manager.set("auto_delete", value)

    def _on_ignore_list_change(self, event=None):
        text = self.ignore_list_text.get("1.0", "end-1c")
        apps = [app.strip() for app in text.split("\n") if app.strip()]
        self.settings_manager.set("ignore_list", apps)

    def _on_startup_toggle(self):
        if self._startup_var.get():
            enable_startup()
        else:
            disable_startup()

    def _on_crash_report_toggle(self):
        self.settings_manager.set("crash_reporting_enabled", self._crash_var.get())

    def _confirm_clear(self):
        if messagebox.askyesno("Confirm Clear", "Delete all clipboard history? This cannot be undone.", parent=self):
            self.on_clear_history()
            messagebox.showinfo("History Cleared", "All clipboard history has been cleared.", parent=self)

    # ── Public API ────────────────────────────────────────────────────────────

    def show(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def hide(self):
        self.withdraw()
