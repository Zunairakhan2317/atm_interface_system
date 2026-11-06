import os
import pytest
from db import init_db, validate_pin, withdraw, get_account, get_history, DB_PATH

@pytest.fixture(autouse=True)
def fresh_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_valid_login():
    ok, msg, _ = validate_pin("1234567890", "1234")
    assert ok is True

def test_wrong_pin():
    ok, msg, _ = validate_pin("1234567890", "9999")
    assert ok is False
    assert "Wrong PIN" in msg

def test_account_locks_after_3_failures():
    for _ in range(3):
        validate_pin("1234567890", "9999")
    ok, msg, _ = validate_pin("1234567890", "1234")
    assert ok is False
    assert "locked" in msg.lower()

def test_withdraw_success():
    ok, msg = withdraw(1, 5000)
    assert ok is True
    assert get_account(1)["balance"] == 5000.0

def test_withdraw_insufficient_funds():
    # Balance is 10,000. Daily limit is 50,000. 
    # Withdrawing 15,000 triggers 'Insufficient funds' (passes limit check, fails balance check)
    ok, msg = withdraw(1, 15000)
    assert ok is False
    assert "Insufficient" in msg

def test_withdraw_exceeds_daily_limit():
    # Withdrawing 60,000 triggers 'Daily limit exceeded' (fails limit check)
    ok, msg = withdraw(1, 60000)
    assert ok is False
    assert "limit" in msg.lower() or "insufficient" in msg.lower()