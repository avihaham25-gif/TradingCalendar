# Trading Journal Pro – Test Plan

> **Version:** 1.0  
> **Status:** Active  
> **Last Updated:** 2026-06-16  
> **Depends on:** `design.md` v1.0, `requirements.md` v1.0  
> **Framework:** `pytest` + `unittest.mock`

---

## 1. Testing Philosophy

| Principle | Rule |
|-----------|------|
| **TDD Strict** | Test file is written BEFORE implementation. Test must fail (RED) before writing code (GREEN). |
| **One assertion per test** | Each test validates a single behavior. |
| **Layer isolation** | Each layer is tested independently; dependencies are mocked. |
| **No IB Gateway in unit tests** | All IB interactions are mocked. Integration tests require a live paper account. |
| **Hebrew messages tested** | Error messages to user are asserted in tests (exact string match). |

---

## 2. Test File Structure

```
TradingCalendar/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              ← Shared fixtures (mock IB, mock config, etc.)
│   ├── test_ib_exceptions.py    ← Layer 1: Exception classes
│   ├── test_ib_client.py        ← Layer 1: IBClient unit tests
│   ├── test_ib_controller.py    ← Layer 2: IBController unit tests
│   ├── test_ui_integration.py   ← Layer 3: UI callback wiring (lightweight)
│   └── test_integration.py      ← End-to-end (requires IB Gateway)
└── ...
```

---

## 3. Layer 1 – IB Client (`test_ib_client.py`)

### 3.1 Custom Exceptions (`test_ib_exceptions.py`)

| Test ID | Description | Assert |
|---------|-------------|--------|
| `test_connection_error_stores_message` | `IBConnectionError("msg", 326)` | `.message == "msg"`, `.error_code == 326` |
| `test_connection_error_str_repr` | `str(IBConnectionError(...))` | Contains message text |
| `test_data_error_stores_partial_data` | `IBDataError("msg", partial)` | `.partial_data == partial` |
| `test_data_error_without_partial` | `IBDataError("msg", None)` | `.partial_data is None` |

### 3.2 AccountData Dataclass

| Test ID | Description | Assert |
|---------|-------------|--------|
| `test_account_data_all_fields` | Create with all values | All fields accessible, correct types |
| `test_account_data_defaults` | Create minimal | `is_partial=False`, `missing_fields=[]` |
| `test_account_data_partial_flag` | Create with `is_partial=True` | Flag is set, missing_fields populated |

### 3.3 Config Loader

| Test ID | Description | Assert |
|---------|-------------|--------|
| `test_load_config_valid_file` | Valid JSON exists | Returns dict with `ib_connection` keys |
| `test_load_config_missing_file` | File doesn't exist | Returns defaults, no exception |
| `test_load_config_corrupt_file` | Invalid JSON | Returns defaults, no exception |
| `test_load_config_partial_keys` | JSON missing some keys | Merges with defaults |

### 3.4 IBClient – Connection

| Test ID | Description | Mock Setup | Assert |
|---------|-------------|------------|--------|
| `test_connect_success` | IB().connect() succeeds | Mock IB returns connected | No exception raised |
| `test_connect_refused` | IB().connect() raises ConnectionRefusedError | Mock raises | `IBConnectionError` with appropriate message |
| `test_connect_timeout` | IB().connect() raises TimeoutError | Mock raises | `IBConnectionError` with timeout message |
| `test_connect_client_id_in_use` | IB error callback code 326 | Mock raises with code | `IBConnectionError` with code 326 |
| `test_connect_api_disabled` | IB error callback code 502 | Mock raises with code | `IBConnectionError` with code 502 |

### 3.5 IBClient – Account Summary

| Test ID | Description | Mock Setup | Assert |
|---------|-------------|------------|--------|
| `test_get_account_summary_all_fields` | Returns 4 AccountValue items | Mock accountSummary() | `AccountData` with all fields populated |
| `test_get_account_summary_partial` | Returns 2/4 fields | Mock partial list | `is_partial=True`, `missing_fields` has 2 items |
| `test_get_account_summary_empty` | Returns empty list | Mock empty | Raises `IBDataError` |
| `test_get_account_summary_not_connected` | Called before connect | No mock connection | Raises `IBConnectionError` |
| `test_get_account_summary_correct_parsing` | Value strings parsed to float | Mock with string values | Correct float conversion |

### 3.6 IBClient – Daily Commissions

| Test ID | Description | Mock Setup | Assert |
|---------|-------------|------------|--------|
| `test_get_daily_commissions_with_fills` | 3 fills today | Mock fills() | Sum of 3 commissions |
| `test_get_daily_commissions_no_fills` | No fills | Mock empty fills() | Returns `0.0` |
| `test_get_daily_commissions_filters_old` | 2 today + 1 yesterday | Mock mixed dates | Only today's summed |
| `test_get_daily_commissions_handles_none` | Fill with no commission report | Mock with None | Skips gracefully, no crash |

### 3.7 IBClient – Disconnect

| Test ID | Description | Mock Setup | Assert |
|---------|-------------|------------|--------|
| `test_disconnect_when_connected` | Connected state | Mock connected IB | `ib.disconnect()` called, no exception |
| `test_disconnect_when_not_connected` | Not connected | Mock not connected | No exception (no-op) |
| `test_disconnect_after_error` | Connection in error state | Mock errored | No exception |

---

## 4. Layer 2 – Controller (`test_ib_controller.py`)

### 4.1 Initialization

| Test ID | Description | Assert |
|---------|-------------|--------|
| `test_init_status_idle` | Fresh instance | `status == IDLE` |
| `test_init_not_busy` | Fresh instance | `is_busy == False` |
| `test_init_no_data` | Fresh instance | `get_last_data() is None` |

### 4.2 fetch_account_data – Happy Path

| Test ID | Description | Mock Setup | Assert |
|---------|-------------|------------|--------|
| `test_fetch_sets_busy` | Call fetch | Mock IBClient | `is_busy == True` immediately |
| `test_fetch_sets_connecting` | Call fetch | Mock IBClient | `status == CONNECTING` |
| `test_fetch_calls_on_data_received` | Successful fetch | Mock returns AccountData | Callback invoked with data |
| `test_fetch_sets_connected_after_success` | Wait for completion | Mock returns AccountData | `status == CONNECTED` |
| `test_fetch_stores_last_data` | After success | Mock returns AccountData | `get_last_data()` matches |
| `test_fetch_resets_busy_after_success` | After completion | Mock returns | `is_busy == False` |

### 4.3 fetch_account_data – Error Path

| Test ID | Description | Mock Setup | Assert |
|---------|-------------|------------|--------|
| `test_fetch_connection_error_calls_on_error` | IBClient raises IBConnectionError | Mock raises | `on_error` called with Hebrew message |
| `test_fetch_data_error_partial` | IBClient raises IBDataError with partial | Mock raises | `on_data_received` with partial + `on_error` with warning |
| `test_fetch_unexpected_error` | IBClient raises RuntimeError | Mock raises | `on_error` called with generic message |
| `test_fetch_error_sets_status` | Any error | Mock raises | `status == ERROR` |
| `test_fetch_error_resets_busy` | Any error | Mock raises | `is_busy == False` |

### 4.4 Debounce

| Test ID | Description | Assert |
|---------|-------------|--------|
| `test_debounce_rejects_second_call` | Two rapid calls | Second call returns without new thread |
| `test_debounce_allows_after_completion` | Call, wait, call again | Second call executes normally |

### 4.5 Error Code Mapping

| Test ID | Description | Assert |
|---------|-------------|--------|
| `test_map_error_326` | Code 326 | Message contains "Client ID תפוס" |
| `test_map_error_502` | Code 502 | Message contains "API לא מופעל" |
| `test_map_error_connection_refused` | ConnectionRefusedError | Message contains "IB Gateway לא פעיל" |
| `test_map_error_timeout` | TimeoutError | Message contains "זמן ההמתנה עבר" |
| `test_map_error_unknown` | Unknown code | Message contains "שגיאה לא צפויה" |

### 4.6 Stale Data Detection

| Test ID | Description | Assert |
|---------|-------------|--------|
| `test_stale_after_threshold` | Data fetched 6 min ago | `status == STALE` or `is_stale == True` |
| `test_not_stale_within_threshold` | Data fetched 2 min ago | `status == CONNECTED` |

---

## 5. Layer 3 – UI Integration (`test_ui_integration.py`)

> Note: UI tests are lightweight – they verify wiring, not visual appearance.  
> Visual verification is manual.

### 5.1 Controller Wiring

| Test ID | Description | Assert |
|---------|-------------|--------|
| `test_sync_button_calls_controller` | Simulate button click | `controller.fetch_account_data()` called |
| `test_sync_button_debounce_feedback` | Click while busy | UI shows "כבר מסנכרן..." (no crash) |

### 5.2 Callback Handlers

| Test ID | Description | Assert |
|---------|-------------|--------|
| `test_on_ib_data_updates_labels` | Call `_on_ib_data(mock_data)` | Label texts contain expected values |
| `test_on_ib_error_shows_message` | Call `_on_ib_error("msg")` | Error label text == "msg" |
| `test_on_ib_data_clears_error` | Call data after error | Error label is cleared |

### 5.3 Status Indicator

| Test ID | Description | Assert |
|---------|-------------|--------|
| `test_status_idle_gray` | Initial state | Dot color is gray |
| `test_status_connecting_yellow` | During fetch | Dot color is yellow |
| `test_status_connected_green` | After success | Dot color is green |
| `test_status_error_red` | After error | Dot color is red |

---

## 6. Integration Tests (`test_integration.py`)

> **Prerequisite:** IB Gateway running on `127.0.0.1:7496` with paper account.  
> **Marker:** `@pytest.mark.integration` – skipped by default in CI.

| Test ID | Description | Assert |
|---------|-------------|--------|
| `test_full_flow_connect_fetch_disconnect` | Real connect → fetch → disconnect | AccountData has valid values |
| `test_full_flow_gateway_offline` | Gateway not running | Error handled, no crash |
| `test_full_flow_rapid_clicks` | 10 rapid fetch calls | Only 1 executes, no race condition |
| `test_full_flow_partial_data` | Disconnect mid-fetch | Graceful handling |

---

## 7. Shared Fixtures (`conftest.py`)

```python
# Planned fixtures:
@pytest.fixture
def mock_ib()            # Mocked ib_insync.IB instance
@pytest.fixture
def mock_config()        # Valid config dict
@pytest.fixture
def sample_account_data()  # Pre-built AccountData for assertions
@pytest.fixture
def mock_account_values()  # List of mock AccountValue objects
@pytest.fixture
def mock_fills_today()     # List of mock Fill objects (today)
@pytest.fixture
def mock_root()           # Mock Tkinter root with .after() method
```

---

## 8. Running Tests

```bash
# All unit tests (fast, no IB needed)
pytest tests/ -m "not integration" -v

# Integration tests only (requires IB Gateway)
pytest tests/ -m integration -v

# With coverage
pytest tests/ -m "not integration" --cov=. --cov-report=term-missing
```

---

## 9. Coverage Targets

| Layer | Target | Rationale |
|-------|--------|-----------|
| `ib_exceptions.py` | 100% | Trivial, must be fully covered |
| `ib_client.py` | ≥90% | Core logic, all paths tested via mocks |
| `ib_controller.py` | ≥90% | State machine must be fully validated |
| `main.py` (new IB code) | ≥70% | UI code harder to unit test; manual supplements |

---

## 10. TDD Workflow Reminder

```
1. Write test → assert expected behavior         (RED)
2. Run test → verify it FAILS                    (confirm test is valid)
3. Write minimal implementation                  (GREEN)
4. Run test → verify it PASSES
5. Refactor if needed                            (REFACTOR)
6. Commit: "test: ..." then "feat: ..."
```

**Every PR must include:**
- Test file changes BEFORE or WITH implementation changes
- No implementation without a corresponding test

---

*End of test_plan.md*
