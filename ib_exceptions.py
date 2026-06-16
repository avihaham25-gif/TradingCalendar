# ib_exceptions.py – Custom exceptions and data contracts for IB integration
# Status: SKELETON – awaiting TDD implementation
#
# See design.md §3.2 for specification.

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


class IBConnectionError(Exception):
    """Raised when connection to IB Gateway fails."""

    def __init__(self, message: str, error_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class IBDataError(Exception):
    """Raised when data retrieval from IB fails or is incomplete."""

    def __init__(self, message: str, partial_data: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.partial_data = partial_data


@dataclass
class AccountData:
    """Data contract for account summary returned by IBClient."""

    cash: float = 0.0
    net_liquidation: float = 0.0
    buying_power: float = 0.0
    margin_req: float = 0.0
    daily_commissions: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    is_partial: bool = False
    missing_fields: list = field(default_factory=list)
