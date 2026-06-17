import sqlite3, hashlib, secrets, os
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data/app.db")
DB_PATH.parent.mkdir(exist_ok=True)

# Seed data — used only when qc_items table is first created
_SEED_QC_ITEMS = [
    {"sno": "1",     "label": "Signed Agreement",                         "key": "signed_agreement",  "check_type": "presence"},
    {"sno": "2",     "label": "Deposit",                                   "key": "deposit",            "check_type": "rule"},
    {"sno": "3",     "label": "Meter Photo/Switchboard",                   "key": "meter_photo",        "check_type": "presence"},
    {"sno": "4",     "label": "Phase and Upgrade",                         "key": "phase_upgrade",      "check_type": "rule"},
    {"sno": "5",     "label": "Roof Pic/House Pic",                        "key": "roof_pic",           "check_type": "presence"},
    {"sno": "6",     "label": "Storey and Roof Type",                      "key": "storey_roof",        "check_type": "rule"},
    {"sno": "7",     "label": "Electricity Bill/NMI",                      "key": "electricity_bill",   "check_type": "ai"},
    {"sno": "8",     "label": "Rate Notice",                               "key": "rate_notice",        "check_type": "ai"},
    {"sno": "9",     "label": "Meter Approval",                            "key": "meter_approval",     "check_type": "ai"},
    {"sno": "10",    "label": "Roof Layout Approved",                      "key": "roof_layout",        "check_type": "ai"},
    {"sno": "11",    "label": "Inverter Location Approved",                "key": "inverter_location",  "check_type": "ai"},
    {"sno": "12",    "label": "Tilt Frame/Clip Lock",                      "key": "tilt_frame",         "check_type": "ai"},
    {"sno": "13",    "label": "Scissor Lift Required",                     "key": "scissor_lift",       "check_type": "ai"},
    {"sno": "14",    "label": "Welcome Email/Invoice/RL/Fact Sheet",       "key": "welcome_email",      "check_type": "ai"},
    {"sno": "15",    "label": "Solar VIC Loan and Rebate Approved",        "key": "solar_vic",          "check_type": "ai"},
    {"sno": "16",    "label": "Finance Approved (Brighte/Plenti)",         "key": "finance",            "check_type": "ai"},
    {"sno": "17",    "label": "Export Control",                            "key": "export_control",     "check_type": "ai"},
    {"sno": "18",    "label": "Optimizer",                                 "key": "optimizer",          "check_type": "ai"},
    {"sno": "19",    "label": "First Time Installation?",                  "key": "first_install",      "check_type": "ai"},
    {"sno": "20",    "label": "Job Checked by Accounts",                   "key": "accounts",           "check_type": "ai"},
    {"sno": "21",    "label": "Customer Informed Install Date",            "key": "customer_informed",  "check_type": "ai"},
    {"sno": "22",    "label": "Wi-Fi Availability in VIC",                 "key": "wifi",               "check_type": "ai"},
    {"sno": "29",    "label": "Packing Slip vs Signed Agreement",          "key": "packing_slip",       "check_type": "ai"},
    {"sno": "30",    "label": "Organise Delivery",                         "key": "delivery",           "check_type": "ai"},
    {"sno": "31",    "label": "Raise WO for Installer",                    "key": "raise_wo",           "check_type": "ai"},
    {"sno": "32",    "label": "Inform Installer of Install Date",          "key": "inform_installer",   "check_type": "ai"},
    {"sno": "33",    "label": "Create STC in Green Deal",                  "key": "stc",                "check_type": "ai"},
    {"sno": "34i",   "label": "Customer Name & Address Match",             "key": "cust_name_address",  "check_type": "ai"},
    {"sno": "34ii",  "label": "Eligible for Solar VIC Rebate",             "key": "solar_vic_eligible", "check_type": "ai"},
    {"sno": "35i",   "label": "Panel Model # Matches",                     "key": "panel_model",        "check_type": "ai"},
    {"sno": "35ii",  "label": "Inverter Model # Matches",                  "key": "inverter_model",     "check_type": "ai"},
    {"sno": "35iii", "label": "Battery Model # Matches",                   "key": "battery_model",      "check_type": "ai"},
]


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # ── users ──────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            email       TEXT    NOT NULL UNIQUE,
            password    TEXT    NOT NULL,
            role        TEXT    NOT NULL DEFAULT 'user',
            created_at  TEXT    NOT NULL,
            is_active   INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ── sessions ───────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token       TEXT    PRIMARY KEY,
            user_id     INTEGER NOT NULL,
            created_at  TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # ── projects ───────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id    TEXT    NOT NULL UNIQUE,
            user_id       INTEGER NOT NULL,
            customer      TEXT,
            address       TEXT,
            agreement     TEXT,
            agreement_pdf BLOB,
            quote_data    TEXT,
            created_at    TEXT    NOT NULL,
            updated_at    TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Migrate existing DB — add columns that may be missing
    _ensure_columns(c, "projects", [
        ("agreement_pdf", "BLOB"),
        ("quote_data",    "TEXT"),
    ])
    # Drop legacy summary columns if present (they are now computed from check_results)
    # SQLite cannot DROP columns before 3.35 — we just leave them; they'll be ignored.

    # ── qc_items ───────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS qc_items (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            sno        TEXT    NOT NULL,
            label      TEXT    NOT NULL,
            key        TEXT    NOT NULL UNIQUE,
            check_type TEXT    NOT NULL DEFAULT 'ai',
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active  INTEGER NOT NULL DEFAULT 1,
            created_at TEXT    NOT NULL
        )
    """)

    # Seed qc_items only when the table is empty
    count = c.execute("SELECT COUNT(*) FROM qc_items").fetchone()[0]
    if count == 0:
        for idx, item in enumerate(_SEED_QC_ITEMS):
            c.execute(
                "INSERT INTO qc_items (sno, label, key, check_type, sort_order, created_at) VALUES (?,?,?,?,?,?)",
                (item["sno"], item["label"], item["key"], item["check_type"], idx, now())
            )

    # ── check_results ──────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS check_results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            item_key    TEXT    NOT NULL,
            result      TEXT,
            remark      TEXT,
            filename    TEXT,
            ocr_preview TEXT,
            checked_at  TEXT    NOT NULL,
            UNIQUE(session_id, item_key),
            FOREIGN KEY (session_id) REFERENCES projects(session_id)
        )
    """)

    conn.commit()

    # Seed default admin if not exists
    admin_email = os.getenv("ADMIN_EMAIL", "admin@adssolar.com")
    admin_pass  = os.getenv("ADMIN_PASSWORD", "Admin@123")
    row = c.execute("SELECT id FROM users WHERE email=?", (admin_email,)).fetchone()
    if not row:
        c.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?,?,?,?,?)",
            ("Admin", admin_email, hash_password(admin_pass), "admin", now())
        )
        conn.commit()

    conn.close()


def _ensure_columns(cursor, table: str, columns: list[tuple]):
    existing = [r[1] for r in cursor.execute(f"PRAGMA table_info({table})").fetchall()]
    for col_name, col_type in columns:
        if col_name not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")


def now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def hash_password(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    return hash_password(plain) == hashed


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn  = get_db()
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at) VALUES (?,?,?)",
        (token, user_id, now())
    )
    conn.commit()
    conn.close()
    return token


def get_user_by_token(token: str):
    if not token:
        return None
    conn = get_db()
    row  = conn.execute(
        "SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND u.is_active=1",
        (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_session(token: str):
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    conn.commit()
    conn.close()


# ── User CRUD ──────────────────────────────────────────────────────────────

def get_all_users():
    conn  = get_db()
    rows  = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_by_id(user_id: int):
    conn = get_db()
    row  = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email: str):
    conn = get_db()
    row  = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(name: str, email: str, password: str, role: str = "user"):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?,?,?,?,?)",
            (name, email, hash_password(password), role, now())
        )
        conn.commit()
        return True, "User created"
    except sqlite3.IntegrityError:
        return False, "Email already exists"
    finally:
        conn.close()


def update_user(user_id: int, name: str, email: str, role: str, is_active: int, password: str = ""):
    conn = get_db()
    try:
        if password:
            conn.execute(
                "UPDATE users SET name=?, email=?, role=?, is_active=?, password=? WHERE id=?",
                (name, email, role, is_active, hash_password(password), user_id)
            )
        else:
            conn.execute(
                "UPDATE users SET name=?, email=?, role=?, is_active=? WHERE id=?",
                (name, email, role, is_active, user_id)
            )
        conn.commit()
        return True, "User updated"
    except sqlite3.IntegrityError:
        return False, "Email already exists"
    finally:
        conn.close()


def delete_user(user_id: int):
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


# ── QC Items ───────────────────────────────────────────────────────────────

def get_all_qc_items(active_only: bool = True) -> list[dict]:
    conn = get_db()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM qc_items WHERE is_active=1 ORDER BY sort_order, id"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM qc_items ORDER BY sort_order, id"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_qc_item_by_key(key: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM qc_items WHERE key=?", (key,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_qc_item(sno: str, label: str, key: str, check_type: str, sort_order: int) -> tuple[bool, str]:
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO qc_items (sno, label, key, check_type, sort_order, created_at) VALUES (?,?,?,?,?,?)",
            (sno, label, key, check_type, sort_order, now())
        )
        conn.commit()
        return True, "Item created"
    except sqlite3.IntegrityError:
        return False, "Key already exists"
    finally:
        conn.close()


def update_qc_item(item_id: int, sno: str, label: str, key: str, check_type: str,
                   sort_order: int, is_active: int) -> tuple[bool, str]:
    conn = get_db()
    try:
        conn.execute(
            "UPDATE qc_items SET sno=?, label=?, key=?, check_type=?, sort_order=?, is_active=? WHERE id=?",
            (sno, label, key, check_type, sort_order, is_active, item_id)
        )
        conn.commit()
        return True, "Item updated"
    except sqlite3.IntegrityError:
        return False, "Key already exists"
    finally:
        conn.close()


def delete_qc_item(item_id: int):
    conn = get_db()
    conn.execute("DELETE FROM qc_items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()


# ── Check Results ──────────────────────────────────────────────────────────

def upsert_check_result(session_id: str, item_key: str, result: str,
                        remark: str, filename: str, ocr_preview: str = ""):
    conn = get_db()
    conn.execute("""
        INSERT INTO check_results (session_id, item_key, result, remark, filename, ocr_preview, checked_at)
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(session_id, item_key) DO UPDATE SET
            result=excluded.result,
            remark=excluded.remark,
            filename=excluded.filename,
            ocr_preview=excluded.ocr_preview,
            checked_at=excluded.checked_at
    """, (session_id, item_key, result, remark, filename, ocr_preview, now()))
    conn.commit()
    conn.close()


def get_check_results(session_id: str) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM check_results WHERE session_id=? ORDER BY checked_at", (session_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_check_results(session_id: str):
    conn = get_db()
    conn.execute("DELETE FROM check_results WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()


# ── Projects ───────────────────────────────────────────────────────────────

def save_quote_data(session_id: str, quote_json: str):
    conn = get_db()
    conn.execute(
        "UPDATE projects SET quote_data=? WHERE session_id=?",
        (quote_json, session_id)
    )
    conn.commit()
    conn.close()


def save_agreement_pdf(session_id: str, pdf_bytes: bytes):
    conn = get_db()
    conn.execute(
        "UPDATE projects SET agreement_pdf=? WHERE session_id=?",
        (pdf_bytes, session_id)
    )
    conn.commit()
    conn.close()


def get_agreement_pdf(session_id: str) -> bytes | None:
    conn = get_db()
    row = conn.execute(
        "SELECT agreement_pdf FROM projects WHERE session_id=?", (session_id,)
    ).fetchone()
    conn.close()
    return bytes(row["agreement_pdf"]) if row and row["agreement_pdf"] else None


def upsert_project(session_id: str, user_id: int, customer: str, address: str, agreement: str):
    conn = get_db()
    existing = conn.execute("SELECT * FROM projects WHERE session_id=?", (session_id,)).fetchone()
    if existing:
        new_customer  = customer  or existing["customer"]  or ""
        new_address   = address   or existing["address"]   or ""
        new_agreement = agreement or existing["agreement"] or ""
        conn.execute("""
            UPDATE projects SET customer=?, address=?, agreement=?, updated_at=?
            WHERE session_id=?
        """, (new_customer, new_address, new_agreement, now(), session_id))
    else:
        conn.execute("""
            INSERT INTO projects (session_id, user_id, customer, address, agreement, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?)
        """, (session_id, user_id, customer, address, agreement, now(), now()))
    conn.commit()
    conn.close()


def get_project(session_id: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE session_id=?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_projects():
    conn = get_db()
    rows = conn.execute("""
        SELECT p.*, u.name as user_name, u.email as user_email
        FROM projects p
        LEFT JOIN users u ON u.id = p.user_id
        ORDER BY p.updated_at DESC
    """).fetchall()
    conn.close()
    projects = []
    for r in rows:
        d = dict(r)
        d.pop("agreement_pdf", None)
        projects.append(d)
    return projects


def get_projects_by_user(user_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM projects WHERE user_id=? ORDER BY updated_at DESC", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_project(project_id: int):
    conn = get_db()
    # Also delete associated check results
    row = conn.execute("SELECT session_id FROM projects WHERE id=?", (project_id,)).fetchone()
    if row:
        conn.execute("DELETE FROM check_results WHERE session_id=?", (row["session_id"],))
    conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()
