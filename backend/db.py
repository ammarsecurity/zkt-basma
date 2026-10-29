import sqlite3

from formatting import now_stamp
from paths import database_file

DB_PATH = database_file()

PAGE_SIZE = 25


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                ip TEXT NOT NULL,
                port INTEGER NOT NULL,
                password INTEGER NOT NULL DEFAULT 0,
                last_sync_at TEXT,
                last_status TEXT,
                last_ok INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_devices_ip_port
                ON devices(ip, port);

            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_employees_device_user
                ON employees(device_id, user_id);

            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                status INTEGER NOT NULL DEFAULT 0,
                punch INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_attendance_unique
                ON attendance(device_id, user_id, timestamp);

            CREATE INDEX IF NOT EXISTS idx_attendance_timestamp
                ON attendance(timestamp);
            """
        )
        conn.commit()
    finally:
        conn.close()


def list_devices(conn):
    return conn.execute(
        """
        SELECT
            d.*,
            (
                SELECT COUNT(*)
                FROM attendance a
                WHERE a.device_id = d.id
            ) AS attendance_count
        FROM devices d
        ORDER BY d.id DESC
        """
    ).fetchall()


def get_device(conn, device_id):
    return conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()


def ip_taken(conn, ip, port, ignore_id=None):
    row = conn.execute(
        """
        SELECT id FROM devices
        WHERE ip = ? AND port = ? AND id != COALESCE(?, -1)
        """,
        (ip, port, ignore_id),
    ).fetchone()
    return row is not None


def create_device(conn, name, ip, port, password):
    cur = conn.execute(
        """
        INSERT INTO devices (name, ip, port, password, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name, ip, port, password, now_stamp()),
    )
    conn.commit()
    return cur.lastrowid


def update_device(conn, device_id, name, ip, port, password):
    conn.execute(
        """
        UPDATE devices
        SET name = ?, ip = ?, port = ?, password = ?
        WHERE id = ?
        """,
        (name, ip, port, password, device_id),
    )
    conn.commit()


def delete_device(conn, device_id):
    conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
    conn.commit()


def mark_sync(conn, device_id, ok, status):
    if ok:
        conn.execute(
            """
            UPDATE devices
            SET last_ok = 1, last_status = ?, last_sync_at = ?
            WHERE id = ?
            """,
            (status, now_stamp(), device_id),
        )
    else:
        conn.execute(
            """
            UPDATE devices
            SET last_ok = 0, last_status = ?
            WHERE id = ?
            """,
            (status, device_id),
        )
    conn.commit()


def save_pull(conn, device_id, users, logs):
    current = now_stamp()
    conn.executemany(
        """
        INSERT INTO employees (device_id, user_id, name, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(device_id, user_id) DO UPDATE SET
            name = excluded.name,
            updated_at = excluded.updated_at
        """,
        [(device_id, user["user_id"], user["name"], current) for user in users],
    )
    before = conn.execute(
        "SELECT COUNT(*) AS n FROM attendance WHERE device_id = ?",
        (device_id,),
    ).fetchone()["n"]
    conn.executemany(
        """
        INSERT OR IGNORE INTO attendance
            (device_id, user_id, timestamp, status, punch, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                device_id,
                log["user_id"],
                log["timestamp"],
                log["status"],
                log["punch"],
                current,
            )
            for log in logs
        ],
    )
    after = conn.execute(
        "SELECT COUNT(*) AS n FROM attendance WHERE device_id = ?",
        (device_id,),
    ).fetchone()["n"]
    conn.commit()
    return after - before, after


def query_logs(conn, device_id, query, date_from, date_to, kind, order, page=None):
    where = []
    params = []

    if device_id is not None:
        where.append("a.device_id = ?")
        params.append(device_id)
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append(
            "(IFNULL(e.name, '') LIKE ? ESCAPE '\\' OR a.user_id LIKE ? ESCAPE '\\')"
        )
        like = f"%{escaped}%"
        params.extend([like, like])
    if date_from:
        where.append("date(a.timestamp) >= date(?)")
        params.append(date_from)
    if date_to:
        where.append("date(a.timestamp) <= date(?)")
        params.append(date_to)
    if kind == "in":
        where.append("a.status = 0")
    elif kind == "out":
        where.append("a.status = 1")

    clause = f"WHERE {' AND '.join(where)}" if where else ""
    joins = """
        FROM attendance a
        JOIN devices d ON d.id = a.device_id
        LEFT JOIN employees e
            ON e.device_id = a.device_id AND e.user_id = a.user_id
    """
    total = conn.execute(f"SELECT COUNT(*) AS n {joins} {clause}", params).fetchone()["n"]

    direction = "ASC" if order == "asc" else "DESC"
    sql = f"""
        SELECT
            a.id,
            a.user_id,
            a.timestamp,
            a.status,
            a.device_id,
            COALESCE(e.name, '') AS employee_name,
            d.name AS device_name
        {joins}
        {clause}
        ORDER BY a.timestamp {direction}, employee_name ASC, a.id {direction}
    """
    page_params = list(params)
    if page is not None:
        sql += " LIMIT ? OFFSET ?"
        page_params.extend([PAGE_SIZE, (page - 1) * PAGE_SIZE])

    rows = conn.execute(sql, page_params).fetchall()
    return rows, total
