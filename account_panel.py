# account_panel.py – Account Data Panel (UI Component)
# Status: TDD GREEN – standalone CTkFrame for IB account display
#
# This module is a self-contained UI component that receives an IBController
# and displays account data, status indicator, and sync button.
#
# See design.md §3.5 for layout specification.

import customtkinter as ctk
from datetime import datetime


# Color constants (matching main.py palette)
COLOR_PANEL_BG = "#1a1a1e"
COLOR_TEXT = "#e8e8e8"
COLOR_SUBTEXT = "#888"
COLOR_ACCENT = "#3a7bd5"
COLOR_PROFIT = "#00e676"
COLOR_LOSS = "#ff4f4f"

# Status dot colors mapped to ConnectionStatus values
STATUS_COLORS = {
    "idle": "#666666",       # Gray
    "connecting": "#ffc107", # Yellow
    "connected": "#00e676",  # Green
    "error": "#ff4f4f",      # Red
    "stale": "#ff9800",      # Orange
}


class AccountPanel(ctk.CTkFrame):
    """Self-contained account data panel with status indicator and sync button.

    Args:
        master: Parent widget
        controller: IBController instance (dependency injection)
    """

    def __init__(self, master, controller, **kwargs):
        super().__init__(master, fg_color=COLOR_PANEL_BG, corner_radius=12, **kwargs)
        self._controller = controller
        self._setup_widgets()
        self._update_status_dot()

    def _setup_widgets(self):
        """Build all panel widgets."""
        # === Header row: status dot + title + sync button ===
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 6))

        # Status dot (colored circle indicator)
        self._status_dot = ctk.CTkLabel(
            header, text="●", font=("Arial", 16),
            text_color=STATUS_COLORS["idle"], width=20
        )
        self._status_dot.pack(side="left", padx=(0, 6))

        # Status text
        self._status_label = ctk.CTkLabel(
            header, text="לא מחובר",
            font=("Helvetica Neue", 11), text_color=COLOR_SUBTEXT
        )
        self._status_label.pack(side="left")

        # Sync button
        self._sync_btn = ctk.CTkButton(
            header, text="סנכרון IB", width=90, height=28,
            font=("Helvetica Neue", 12, "bold"),
            fg_color=COLOR_ACCENT, hover_color="#2a5fa8",
            corner_radius=8, command=self._on_sync_click
        )
        self._sync_btn.pack(side="right")

        # === Data rows ===
        self._data_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._data_frame.pack(fill="x", padx=12, pady=(4, 4))

        # Create data labels (Hebrew labels, right-aligned)
        self._labels = {}
        fields = [
            ("cash", "מזומן:"),
            ("net_liquidation", "שווי נקי:"),
            ("buying_power", "כוח קנייה:"),
            ("margin_req", "מרווח נדרש:"),
            ("daily_commissions", "עמלות היום:"),
        ]

        for i, (key, label_text) in enumerate(fields):
            row = ctk.CTkFrame(self._data_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)

            value_label = ctk.CTkLabel(
                row, text="—",
                font=("Helvetica Neue", 13, "bold"),
                text_color=COLOR_TEXT
            )
            value_label.pack(side="left", padx=(4, 0))

            name_label = ctk.CTkLabel(
                row, text=label_text,
                font=("Helvetica Neue", 12),
                text_color=COLOR_SUBTEXT
            )
            name_label.pack(side="right", padx=(0, 4))

            self._labels[key] = value_label

        # === Timestamp row ===
        self._timestamp_label = ctk.CTkLabel(
            self, text="לחץ סנכרון לעדכון",
            font=("Helvetica Neue", 10), text_color=COLOR_SUBTEXT
        )
        self._timestamp_label.pack(pady=(4, 10))

        # === Error message (hidden by default) ===
        self._error_label = ctk.CTkLabel(
            self, text="", font=("Helvetica Neue", 11),
            text_color=COLOR_LOSS, wraplength=350
        )
        self._error_label.pack(pady=(0, 6))
        self._error_label.pack_forget()  # Hidden initially

    def _on_sync_click(self):
        """Handle sync button click with debounce feedback."""
        if self._controller.is_busy:
            self._status_label.configure(text="כבר מסנכרן...")
            return

        self._controller.fetch_account_data()
        self._set_status("connecting")

    def _set_status(self, status_value):
        """Update status dot color and label based on status string."""
        color = STATUS_COLORS.get(status_value, STATUS_COLORS["idle"])
        self._status_dot.configure(text_color=color)

        status_texts = {
            "idle": "לא מחובר",
            "connecting": "מתחבר...",
            "connected": "מחובר",
            "error": "שגיאה",
            "stale": "נתונים ישנים",
        }
        self._status_label.configure(text=status_texts.get(status_value, ""))

    def on_data_received(self, data):
        """Callback: update panel with fresh AccountData.
        Called from IBController via root.after() – runs on main thread."""
        # Update data labels
        self._labels["cash"].configure(text=f"${data.cash:,.2f}")
        self._labels["net_liquidation"].configure(text=f"${data.net_liquidation:,.2f}")
        self._labels["buying_power"].configure(text=f"${data.buying_power:,.2f}")
        self._labels["margin_req"].configure(text=f"${data.margin_req:,.2f}")
        self._labels["daily_commissions"].configure(text=f"${data.daily_commissions:,.2f}")

        # Update timestamp
        ts = data.timestamp.strftime("%d/%m/%Y %H:%M:%S")
        self._timestamp_label.configure(text=f"עודכן: {ts}", text_color=COLOR_SUBTEXT)

        # Update status
        if data.is_partial:
            self._set_status("connected")
            missing = ", ".join(data.missing_fields)
            self._show_error(f"נתונים חלקיים – חסר: {missing}")
        else:
            self._set_status("connected")
            self._hide_error()

        # Check staleness for visual indicator
        if self._controller.is_stale:
            self._set_status("stale")
            self._timestamp_label.configure(text_color="#ff9800")

    def on_error(self, message):
        """Callback: display error message in panel.
        Called from IBController via root.after() – runs on main thread."""
        self._set_status("error")
        self._show_error(message)

    def _show_error(self, message):
        """Show error label with message."""
        self._error_label.configure(text=message)
        self._error_label.pack(pady=(0, 6))

    def _hide_error(self):
        """Hide error label."""
        self._error_label.configure(text="")
        self._error_label.pack_forget()

    def _update_status_dot(self):
        """Set initial status based on controller state."""
        self._set_status(self._controller.status.value)
