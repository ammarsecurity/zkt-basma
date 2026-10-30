import json
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
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(employees)")}
        if "fingers" not in columns:
            conn.execute("ALTER TABLE employees ADD COLUMN fingers TEXT")
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


def list_employees(conn, device_id=None):
    rows, _total = query_employees(conn, device_id, "", page=None)
    return rows


def query_employees(conn, device_id, query, page, finger="all"):
    where = []
    params = []
    if device_id is not None:
        where.append("e.device_id = ?")
        params.append(device_id)
    if query:
        clause, like_params = _like_clause(query)
        where.append(clause)
        params.extend(like_params)
    if finger == "none":
        where.append("e.fingers = '[]'")
    elif finger == "enrolled":
        where.append("e.fingers IS NOT NULL AND e.fingers != '[]'")

    clause = f"WHERE {' AND '.join(where)}" if where else ""
    joins = """
        FROM employees e
        JOIN devices d ON d.id = e.device_id
    """
    total = conn.execute(f"SELECT COUNT(*) AS n {joins} {clause}", params).fetchone()["n"]
    sql = f"""
        SELECT
            e.id,
            e.device_id,
            e.user_id,
            e.name,
            e.fingers,
            d.name AS device_name
        {joins}
        {clause}
        ORDER BY CAST(e.user_id AS INTEGER), e.user_id
    """
    page_params = list(params)
    if page is not None:
        sql += " LIMIT ? OFFSET ?"
        page_params.extend([PAGE_SIZE, (page - 1) * PAGE_SIZE])
    rows = conn.execute(sql, page_params).fetchall()
    return rows, total


def upsert_employees(conn, device_id, users):
    if not users:
        return
    current = now_stamp()
    named = [user for user in users if "fingers" not in user]
    enrolled = [user for user in users if "fingers" in user]
    if named:
        conn.executemany(
            """
            INSERT INTO employees (device_id, user_id, name, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(device_id, user_id) DO UPDATE SET
                name = excluded.name,
                updated_at = excluded.updated_at
            """,
            [(device_id, user["user_id"], user["name"], current) for user in named],
        )
    if enrolled:
        conn.executemany(
            """
            INSERT INTO employees (device_id, user_id, name, fingers, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(device_id, user_id) DO UPDATE SET
                name = excluded.name,
                fingers = excluded.fingers,
                updated_at = excluded.updated_at
            """,
            [
                (
                    device_id,
                    user["user_id"],
                    user["name"],
                    json.dumps(sorted({int(fid) for fid in user["fingers"]})),
                    current,
                )
                for user in enrolled
            ],
        )


def delete_employee(conn, device_id, user_id):
    return conn.execute(
        "DELETE FROM employees WHERE device_id = ? AND user_id = ?",
        (device_id, user_id),
    ).rowcount


def _like_clause(query):
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    like = f"%{escaped}%"
    return "(IFNULL(e.name, '') LIKE ? ESCAPE '\\' OR e.user_id LIKE ? ESCAPE '\\')", [like, like]


def attendance_summary(conn, start, end, device_id, query, status, page):
    where = []
    params = [start, end]
    if device_id is not None:
        where.append("e.device_id = ?")
        params.append(device_id)
    if query:
        clause, like_params = _like_clause(query)
        where.append(clause)
        params.extend(like_params)
    employee_where = f"WHERE {' AND '.join(where)}" if where else ""
    grouped = f"""
        SELECT
            e.id,
            e.user_id,
            COALESCE(e.name, '') AS employee_name,
            e.device_id,
            d.name AS device_name,
            MIN(a.timestamp) AS first_punch,
            MAX(a.timestamp) AS last_punch,
            COUNT(a.id) AS punches,
            COUNT(DISTINCT date(a.timestamp)) AS days
        FROM employees e
        JOIN devices d ON d.id = e.device_id
        LEFT JOIN attendance a
            ON a.device_id = e.device_id
            AND a.user_id = e.user_id
            AND date(a.timestamp) >= date(?)
            AND date(a.timestamp) < date(?)
        {employee_where}
        GROUP BY e.id
    """
    stats = conn.execute(
        f"""
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN punches > 0 THEN 1 ELSE 0 END), 0) AS present,
            COALESCE(SUM(CASE WHEN punches = 0 THEN 1 ELSE 0 END), 0) AS absent
        FROM ({grouped}) s
        """,
        params,
    ).fetchone()
    status_sql = ""
    if status == "present":
        status_sql = "WHERE punches > 0"
    elif status == "absent":
        status_sql = "WHERE punches = 0"
    filtered = conn.execute(
        f"SELECT COUNT(*) AS n FROM ({grouped}) s {status_sql}",
        params,
    ).fetchone()["n"]
    sql = f"""
        SELECT * FROM ({grouped}) s
        {status_sql}
        ORDER BY CASE WHEN punches = 0 THEN 1 ELSE 0 END, CAST(user_id AS INTEGER), user_id
    """
    page_params = list(params)
    if page is not None:
        sql += " LIMIT ? OFFSET ?"
        page_params.extend([PAGE_SIZE, (page - 1) * PAGE_SIZE])
    rows = conn.execute(sql, page_params).fetchall()
    return rows, filtered, stats["present"], stats["absent"]


def month_punch_details(conn, start, end, device_id, query, page, user_id=""):
    where = []
    params = []
    if device_id is not None:
        where.append("e.device_id = ?")
        params.append(device_id)
    if user_id:
        where.append("e.user_id = ?")
        params.append(user_id)
    if query:
        clause, like_params = _like_clause(query)
        where.append(clause)
        params.extend(like_params)
    employee_where = f"WHERE {' AND '.join(where)}" if where else ""
    employees = conn.execute(
        f"""
        SELECT
            e.id,
            e.user_id,
            COALESCE(e.name, '') AS employee_name,
            e.device_id,
            d.name AS device_name
        FROM employees e
        JOIN devices d ON d.id = e.device_id
        {employee_where}
        ORDER BY CAST(e.user_id AS INTEGER), e.user_id
        """,
        params,
    ).fetchall()
    punches = conn.execute(
        f"""
        SELECT e.id AS employee_id, a.timestamp
        FROM employees e
        JOIN devices d ON d.id = e.device_id
        JOIN attendance a
            ON a.device_id = e.device_id
            AND a.user_id = e.user_id
            AND date(a.timestamp) >= date(?)
            AND date(a.timestamp) < date(?)
        {employee_where}
        ORDER BY a.timestamp
        """,
        [start, end, *params],
    ).fetchall()
    by_employee = {}
    for punch in punches:
        days = by_employee.setdefault(punch["employee_id"], {})
        days.setdefault(punch["timestamp"][:10], []).append(punch["timestamp"])
    items = []
    for employee in employees:
        days_map = by_employee.get(employee["id"], {})
        days = []
        count = 0
        for day in sorted(days_map):
            times = days_map[day]
            count += len(times)
            days.append({"date": day, "times": times})
        items.append({
            "id": employee["id"],
            "user_id": employee["user_id"],
            "employee_name": employee["employee_name"],
            "device_id": employee["device_id"],
            "device_name": employee["device_name"],
            "punches": count,
            "days": days,
        })
    total = len(items)
    punch_total = len(punches)
    if page is not None:
        offset = (page - 1) * PAGE_SIZE
        items = items[offset:offset + PAGE_SIZE]
    return items, total, punch_total


def save_pull(conn, device_id, users, logs):
    current = now_stamp()
    upsert_employees(conn, device_id, users)
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


def dashboard(conn):
    from datetime import date, timedelta

    today = date.today()
    week_start = today - timedelta(days=6)
    month_start = today.replace(day=1)

    def count(sql, params=()):
        return conn.execute(sql, params).fetchone()["n"]

    devices = count("SELECT COUNT(*) AS n FROM devices")
    employees = count("SELECT COUNT(*) AS n FROM employees")
    unnamed = count("SELECT COUNT(*) AS n FROM employees WHERE TRIM(IFNULL(name, '')) = ''")
    punches = count("SELECT COUNT(*) AS n FROM attendance")
    today_punches = count(
        "SELECT COUNT(*) AS n FROM attendance WHERE date(timestamp) = date(?)",
        (today.isoformat(),),
    )
    week_punches = count(
        "SELECT COUNT(*) AS n FROM attendance WHERE date(timestamp) >= date(?)",
        (week_start.isoformat(),),
    )
    month_punches = count(
        "SELECT COUNT(*) AS n FROM attendance WHERE date(timestamp) >= date(?)",
        (month_start.isoformat(),),
    )
    synced_ok = count("SELECT COUNT(*) AS n FROM devices WHERE last_ok = 1")

    grouped = {
        row["day"]: row["n"]
        for row in conn.execute(
            """
            SELECT date(timestamp) AS day, COUNT(*) AS n
            FROM attendance
            WHERE date(timestamp) >= date(?)
            GROUP BY date(timestamp)
            """,
            (week_start.isoformat(),),
        )
    }
    days = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        key = day.isoformat()
        days.append({"date": key, "count": grouped.get(key, 0)})

    by_device = conn.execute(
        """
        SELECT
            d.id,
            d.name,
            d.last_sync_at,
            d.last_ok,
            d.last_status,
            (SELECT COUNT(*) FROM employees e WHERE e.device_id = d.id) AS employees,
            (SELECT COUNT(*) FROM attendance a WHERE a.device_id = d.id) AS punches
        FROM devices d
        ORDER BY punches DESC, d.name
        """
    ).fetchall()

    recent = conn.execute(
        """
        SELECT
            a.id,
            a.user_id,
            a.timestamp,
            a.status,
            a.device_id,
            COALESCE(e.name, '') AS employee_name,
            d.name AS device_name
        FROM attendance a
        JOIN devices d ON d.id = a.device_id
        LEFT JOIN employees e
            ON e.device_id = a.device_id AND e.user_id = a.user_id
        ORDER BY a.timestamp DESC, a.id DESC
        LIMIT 8
        """
    ).fetchall()

    return {
        "today": today.isoformat(),
        "week_start": week_start.isoformat(),
        "month_start": month_start.isoformat(),
        "devices": devices,
        "employees": employees,
        "unnamed": unnamed,
        "punches": punches,
        "today_punches": today_punches,
        "week_punches": week_punches,
        "month_punches": month_punches,
        "synced_ok": synced_ok,
        "days": days,
        "by_device": by_device,
        "recent": recent,
    }
