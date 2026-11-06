import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = "atm.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS customer (
        customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS account (
        account_id  INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        balance     REAL NOT NULL DEFAULT 0,
        daily_limit REAL NOT NULL DEFAULT 50000,
        account_type TEXT NOT NULL DEFAULT 'savings',
        FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
    );

    CREATE TABLE IF NOT EXISTS card (
        card_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id     INTEGER NOT NULL,
        card_number    TEXT UNIQUE NOT NULL,
        pin_hash       TEXT NOT NULL,
        is_locked      INTEGER NOT NULL DEFAULT 0,
        failed_attempts INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (account_id) REFERENCES account(account_id)
    );

    CREATE TABLE IF NOT EXISTS transaction_log (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id     INTEGER NOT NULL,
        type           TEXT NOT NULL,
        amount         REAL NOT NULL,
        timestamp      DATETIME DEFAULT CURRENT_TIMESTAMP,
        status         TEXT NOT NULL,
        FOREIGN KEY (account_id) REFERENCES account(account_id)
    );
    """)

    cur.execute("SELECT COUNT(*) FROM customer")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO customer (name) VALUES ('Ali Khan')")
        cid = cur.lastrowid
        cur.execute(
            "INSERT INTO account (customer_id, balance, daily_limit) VALUES (?, ?, ?)",
            (cid, 10000.0, 50000.0)
        )
        aid = cur.lastrowid
        cur.execute(
            "INSERT INTO card (account_id, card_number, pin_hash) VALUES (?, ?, ?)",
            (aid, "1234567890", generate_password_hash("1234"))
        )

    conn.commit()
    conn.close()

def validate_pin(card_number, pin):
    conn = get_db()
    card = conn.execute(
        "SELECT * FROM card WHERE card_number = ?", (card_number,)
    ).fetchone()

    if card is None:
        conn.close()
        return False, "Card not found", None

    if card["is_locked"]:
        conn.close()
        return False, "Account locked after 3 failed attempts", None

    if check_password_hash(card["pin_hash"], pin):
        conn.execute("UPDATE card SET failed_attempts = 0 WHERE card_id = ?", (card["card_id"],))
        conn.commit()
        conn.close()
        return True, "OK", card

    attempts = card["failed_attempts"] + 1
    if attempts >= 3:
        conn.execute(
            "UPDATE card SET failed_attempts = ?, is_locked = 1 WHERE card_id = ?",
            (attempts, card["card_id"])
        )
        conn.commit()
        conn.close()
        return False, "Account locked after 3 failed attempts", None

    conn.execute("UPDATE card SET failed_attempts = ? WHERE card_id = ?", (attempts, card["card_id"]))
    conn.commit()
    conn.close()
    return False, f"Wrong PIN. Attempts left: {3 - attempts}", None

def get_account(account_id):
    conn = get_db()
    acc = conn.execute("SELECT * FROM account WHERE account_id = ?", (account_id,)).fetchone()
    conn.close()
    return acc

def withdraw(account_id, amount):
    conn = get_db()
    try:
        conn.execute("BEGIN")
        acc = conn.execute("SELECT * FROM account WHERE account_id = ?", (account_id,)).fetchone()

        if acc is None:
            conn.rollback()
            return False, "Account not found"
        if amount <= 0:
            conn.rollback()
            return False, "Amount must be positive"

        # 1. CHECK DAILY LIMIT FIRST (Policy rule)
        today_total = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM transaction_log "
            "WHERE account_id = ? AND type='WITHDRAW' AND DATE(timestamp)=DATE('now')",
            (account_id,)
        ).fetchone()[0]

        if today_total + amount > acc["daily_limit"]:
            conn.rollback()
            return False, "Daily withdrawal limit exceeded"

        # 2. THEN CHECK BALANCE (Account rule)
        if amount > acc["balance"]:
            conn.rollback()
            return False, "Insufficient funds"

        # 3. PROCESS TRANSACTION
        conn.execute("UPDATE account SET balance = balance - ? WHERE account_id = ?", (amount, account_id))
        conn.execute(
            "INSERT INTO transaction_log (account_id, type, amount, status) "
            "VALUES (?, 'WITHDRAW', ?, 'SUCCESS')",
            (account_id, amount)
        )
        conn.execute("COMMIT")
        return True, "Cash dispensed. New balance: Rs. %.2f" % (acc["balance"] - amount)
    except Exception as e:
        conn.rollback()
        return False, f"Transaction failed: {e}"
    finally:
        conn.close()

def get_history(account_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM transaction_log WHERE account_id = ? ORDER BY transaction_id DESC LIMIT 20",
        (account_id,)
    ).fetchall()
    conn.close()
    return rows