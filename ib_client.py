# ib_client.py – IB Communication Layer (ib_insync wrapper)
# Status: TDD GREEN phase – connect() implemented
#
# This module handles all direct communication with IB Gateway
# via ib_insync. It knows nothing about the UI or threading.
#
# See design.md §3.2 for full interface specification.

import logging

from ib_exceptions import IBConnectionError, IBDataError, AccountData
import ib_insync

logger = logging.getLogger("ib_integration.client")


class IBClient:
    """Wrapper around ib_insync for pull-on-demand account data retrieval.

    Public Interface:
        connect(host, port, client_id, timeout) → None | raises IBConnectionError
        get_account_summary() → AccountData | raises IBDataError
        get_daily_commissions() → float | raises IBDataError
        disconnect() → None (never raises)
    """

    def __init__(self):
        self._ib = None

    def connect(self, host: str, port: int, client_id: int, timeout: int) -> None:
        """Connect to IB Gateway. Raises IBConnectionError on failure."""
        try:
            self._ib = ib_insync.IB()
            self._ib.connect(host, port, clientId=client_id, timeout=timeout)
        except ConnectionRefusedError:
            raise IBConnectionError(
                "IB Gateway לא פעיל. הפעל ונסה שוב.", error_code=None
            )
        except TimeoutError:
            raise IBConnectionError(
                "זמן ההמתנה עבר (timeout). בדוק שIB Gateway פועל.", error_code=None
            )
        except Exception as e:
            error_msg = str(e)
            # Detect specific IB error codes from the exception message
            if "clientId" in error_msg and "already in use" in error_msg:
                raise IBConnectionError(
                    "Client ID תפוס. סגור חיבורים אחרים.", error_code=326
                )
            elif "API" in error_msg and ("not enabled" in error_msg or "refused" in error_msg):
                raise IBConnectionError(
                    "API לא מופעל בהגדרות IB Gateway.", error_code=502
                )
            else:
                raise IBConnectionError(
                    f"שגיאה לא צפויה בחיבור: {error_msg}", error_code=None
                )

    # Fields we expect from IB accountSummary
    _EXPECTED_TAGS = {
        "TotalCashValue": "cash",
        "NetLiquidation": "net_liquidation",
        "BuyingPower": "buying_power",
        "FullMaintMarginReq": "margin_req",
    }

    def get_account_summary(self) -> "AccountData":
        """Fetch account summary. Raises IBConnectionError if not connected,
        IBDataError if no data returned."""
        from datetime import datetime

        # Guard: must be connected
        if self._ib is None:
            raise IBConnectionError("לא מחובר ל-IB Gateway.", error_code=None)

        # Fetch raw account summary from IB
        raw_summary = self._ib.accountSummary()

        # Empty response → raise IBDataError
        if not raw_summary:
            raise IBDataError("לא התקבלו נתונים מ-IB.", partial_data=None)

        # Parse fields
        parsed = {}
        for item in raw_summary:
            if item.tag in self._EXPECTED_TAGS:
                field_name = self._EXPECTED_TAGS[item.tag]
                try:
                    parsed[field_name] = float(item.value)
                except (ValueError, TypeError):
                    pass  # Skip unparseable values – will be marked as missing

        # Determine missing fields
        missing = [
            tag for tag, field_name in self._EXPECTED_TAGS.items()
            if field_name not in parsed
        ]

        is_partial = len(missing) > 0

        return AccountData(
            cash=parsed.get("cash", 0.0),
            net_liquidation=parsed.get("net_liquidation", 0.0),
            buying_power=parsed.get("buying_power", 0.0),
            margin_req=parsed.get("margin_req", 0.0),
            daily_commissions=0.0,  # Populated separately via get_daily_commissions()
            timestamp=datetime.now(),
            is_partial=is_partial,
            missing_fields=missing,
        )

    def get_daily_commissions(self) -> float:
        """Sum today's commissions from executions.
        Raises IBConnectionError if not connected.
        Returns 0.0 if no fills today."""
        from datetime import datetime, date

        # Guard: must be connected
        if self._ib is None:
            raise IBConnectionError("לא מחובר ל-IB Gateway.", error_code=None)

        # Fetch all fills
        fills = self._ib.fills()

        if not fills:
            return 0.0

        # Filter to today's fills and sum commissions
        today = date.today()
        total = 0.0

        for fill in fills:
            try:
                exec_time = fill.execution.time
                # Check if execution is from today
                if hasattr(exec_time, 'date'):
                    fill_date = exec_time.date()
                else:
                    continue  # Skip if no valid time

                if fill_date != today:
                    continue  # Skip fills from other days

                commission = fill.commissionReport.commission
                if commission is None:
                    continue  # Skip invalid commission values

                total += float(commission)
            except (AttributeError, TypeError, ValueError):
                # Skip any malformed fill entry
                continue

        return round(total, 2)

    def disconnect(self) -> None:
        """Safely disconnect. Never raises."""
        try:
            if self._ib and self._ib.isConnected():
                self._ib.disconnect()
        except Exception:
            pass
