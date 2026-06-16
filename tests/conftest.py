# conftest.py – Shared fixtures for TDD tests
# See test_plan.md §7 for planned fixtures.

import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock ib_insync at the module level since it's not installed in test env
# This must happen BEFORE any project imports that reference ib_insync
mock_ib_insync = MagicMock()
sys.modules["ib_insync"] = mock_ib_insync

from ib_exceptions import AccountData
from datetime import datetime


@pytest.fixture
def mock_ib():
    """Mocked ib_insync.IB instance."""
    with patch("ib_insync.IB") as MockIB:
        mock_instance = MagicMock()
        MockIB.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def sample_account_data():
    """Pre-built AccountData for assertion comparisons."""
    return AccountData(
        cash=12450.00,
        net_liquidation=24830.50,
        buying_power=49661.00,
        margin_req=3200.00,
        daily_commissions=12.40,
        timestamp=datetime(2026, 6, 16, 14, 32, 5),
        is_partial=False,
        missing_fields=[],
    )
