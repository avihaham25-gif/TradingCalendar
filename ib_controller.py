# ib_controller.py – Orchestration Layer (Bridge between UI and IBClient)
# Status: TDD GREEN phase – Enum + __init__ implemented
#
# This module manages threading, state, and callbacks.
# It knows about IBClient and the UI callback contract, but not about
# specific UI widgets.
#
# See design.md §3.3 for full specification.

import logging
import threading
from enum import Enum

from ib_client import IBClient
from ib_exceptions import IBConnectionError, IBDataError, AccountData

logger = logging.getLogger("ib_integration.controller")


class ConnectionStatus(Enum):
    """Connection state machine for IB integration."""
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    STALE = "stale"


class IBController:
    """Orchestrator between UI layer and IBClient.

    Public Interface:
        fetch_account_data() → None (triggers async fetch)
        get_last_data() → AccountData or None
        status → ConnectionStatus
        is_busy → bool
    """

    def __init__(self, root, on_data_received, on_error, config_path="config.json"):
        self._root = root
        self._on_data_received = on_data_received
        self._on_error = on_error
        self._config_path = config_path
        self._status = ConnectionStatus.IDLE
        self._is_busy = False
        self._last_data = None

    def fetch_account_data(self):
        """Trigger async fetch in background thread. Returns immediately.
        Debounce: if already busy, silently ignores the call."""
        if self._is_busy:
            return  # Debounce – ignore while fetch is in progress

        self._is_busy = True
        self._status = ConnectionStatus.CONNECTING

        thread = threading.Thread(target=self._do_fetch, daemon=True)
        thread.start()

    def _do_fetch(self):
        """Background thread: connect → fetch → disconnect → callback."""
        client = IBClient()
        try:
            # Load config (use defaults if missing)
            config = self._load_config()
            ib_config = config.get("ib_connection", {})

            host = ib_config.get("host", "127.0.0.1")
            port = ib_config.get("port", 7496)
            client_id = ib_config.get("client_id", 1)
            timeout = ib_config.get("timeout_seconds", 5)

            # Connect
            client.connect(host=host, port=port, client_id=client_id, timeout=timeout)

            # Fetch account summary
            data = client.get_account_summary()

            # Fetch daily commissions
            commissions = client.get_daily_commissions()
            data.daily_commissions = commissions

            # Disconnect
            client.disconnect()

            # Success – store data and notify UI
            self._last_data = data
            self._status = ConnectionStatus.CONNECTED
            self._is_busy = False
            self._root.after(0, self._on_data_received, data)

        except (IBConnectionError, IBDataError) as e:
            client.disconnect()
            self._status = ConnectionStatus.ERROR
            self._is_busy = False
            message = e.message if hasattr(e, 'message') else str(e)
            self._root.after(0, self._on_error, message)

        except Exception as e:
            client.disconnect()
            self._status = ConnectionStatus.ERROR
            self._is_busy = False
            logger.error(f"Unexpected error in fetch: {e}", exc_info=True)
            self._root.after(0, self._on_error, "שגיאה לא צפויה – ראה קובץ Log.")

    def _load_config(self) -> dict:
        """Load config from JSON file. Returns defaults if file is missing/corrupt."""
        import json
        import os

        defaults = {
            "ib_connection": {
                "host": "127.0.0.1",
                "port": 7496,
                "client_id": 1,
                "timeout_seconds": 5,
            },
            "display": {
                "stale_threshold_minutes": 5,
            },
        }

        if not os.path.exists(self._config_path):
            return defaults

        try:
            with open(self._config_path, "r") as f:
                loaded = json.load(f)
            # Merge with defaults
            for key in defaults:
                if key not in loaded:
                    loaded[key] = defaults[key]
            return loaded
        except (json.JSONDecodeError, OSError):
            return defaults

    def get_last_data(self):
        """Return last successful AccountData or None."""
        return self._last_data

    @property
    def status(self):
        """Current connection status."""
        return self._status

    @property
    def is_busy(self):
        """True if a fetch is in progress."""
        return self._is_busy

    @property
    def is_stale(self):
        """True if last data is older than the configured stale threshold.
        Returns False if no data has been fetched yet."""
        from datetime import datetime, timedelta

        if self._last_data is None:
            return False

        config = self._load_config()
        threshold_minutes = config.get("display", {}).get("stale_threshold_minutes", 5)

        age = datetime.now() - self._last_data.timestamp
        return age >= timedelta(minutes=threshold_minutes)
