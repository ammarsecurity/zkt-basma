import logging
import json
from contextlib import asynccontextmanager
from datetime import datetime
from urllib.parse import quote

import ipaddress
from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, field_validator

import db
from excel_export import build_workbook
from formatting import (
    KIND_LABELS,
    display_date,
    clock_12,
    display_stamp,
    now_stamp,
    split_stamp,
    status_kind,
    weekday_name,
    status_label,
)
from paths import frontend_dist
from zk_service import (
    DeviceError,
    DuplicateUser,
    add_device_user,
    delete_device_user,
    list_device_users,
    pull_device,
    test_connection,
    update_device_user,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("zkt")

DIST = frontend_dist()


def _valid_date(value, label):
    if value in (None, ""):
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{label} غير صحيح")
    return value


def _filters(
    device_id: int | None,
    q: str,
    date_from: str | None,
    date_to: str | None,
    kind: str,
):
    if kind not in KIND_LABELS:
        raise HTTPException(status_code=400, detail="نوع الحركة غير صحيح")
    date_from = _valid_date(date_from, "تاريخ البداية")
    date_to = _valid_date(date_to, "تاريخ النهاية")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="تاريخ البداية بعد تاريخ النهاية")
    query = (q or "").strip()
    return device_id, query, date_from, date_to, kind


def _log_item(row):
    date_text, clock = split_stamp(row["timestamp"])
    return {
        "id": row["id"],
        "employee_name": row["employee_name"] or "",
        "user_id": row["user_id"],
        "date": date_text,
        "weekday": weekday_name(row["timestamp"]),
        "time": clock_12(clock),
        "status": row["status"],
        "status_label": status_label(row["status"]),
        "status_kind": status_kind(row["status"]),
        "device_id": row["device_id"],
        "device_name": row["device_name"],
    }


def _device_out(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "ip": row["ip"],
        "port": row["port"],
        "password": row["password"],
        "last_sync_at": display_stamp(row["last_sync_at"]) or None,
        "last_status": row["last_status"] or "",
        "last_ok": bool(row["last_ok"]),
        "ever_synced": row["last_sync_at"] is not None,
        "attendance_count": row["attendance_count"],
    }


def _clean_password(value):
    if value < 0 or value > 99999999:
        raise ValueError("كلمة مرور الاتصال غير صحيحة")
    return value


class DeviceIn(BaseModel):
    name: str
    ip: str
    port: int = 4370
    password: int = 0

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = (value or "").strip()
        if not value:
            raise ValueError("اكتب اسم الجهاز")
        if len(value) > 80:
            raise ValueError("اسم الجهاز طويل")
        return value

    @field_validator("ip")
    @classmethod
    def clean_ip(cls, value):
        value = (value or "").strip()
        try:
            ipaddress.ip_address(value)
        except ValueError:
            raise ValueError("عنوان IP غير صحيح")
        return value

    @field_validator("port")
    @classmethod
    def clean_port(cls, value):
        if value < 1 or value > 65535:
            raise ValueError("المنفذ لازم يكون بين 1 و 65535")
        return value

    @field_validator("password")
    @classmethod
    def clean_password(cls, value):
        return _clean_password(value)


def _employee_name(value):
    value = " ".join((value or "").split())
    if not value:
        raise ValueError("اكتب اسم الموظف")
    if len(value.encode("utf-8")) > 24:
        raise ValueError("اسم الموظف طويل على الجهاز. اختصره، حوالي 12 حرفاً عربياً")
    return value


class EmployeeIn(BaseModel):
    name: str
    user_id: str

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        return _employee_name(value)

    @field_validator("user_id")
    @classmethod
    def clean_user_id(cls, value):
        value = (value or "").strip()
        if not value.isdigit() or value.startswith("0") or len(value) > 9:
            raise ValueError("رقم الموظف لازم يكون من 1 إلى 9 أرقام، بدون صفر في البداية")
        return value


class EmployeeUpdate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        return _employee_name(value)


class ConnectionIn(BaseModel):
    ip: str
    port: int = 4370
    password: int = 0

    @field_validator("ip")
    @classmethod
    def clean_ip(cls, value):
        value = (value or "").strip()
        try:
            ipaddress.ip_address(value)
        except ValueError:
            raise ValueError("عنوان IP غير صحيح")
        return value

    @field_validator("port")
    @classmethod
    def clean_port(cls, value):
        if value < 1 or value > 65535:
            raise ValueError("المنفذ لازم يكون بين 1 و 65535")
        return value

    @field_validator("password")
    @classmethod
    def clean_password(cls, value):
        return _clean_password(value)


@asynccontextmanager
async def lifespan(_app):
    db.init_db()
    yield


app = FastAPI(title="ZKTeco attendance", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_error(_request, exc):
    message = "تحقق من البيانات المدخلة"
    errors = exc.errors()
    if errors:
        raw = str(errors[0].get("msg", ""))
        raw = raw.removeprefix("Value error, ").strip()
        if raw and not raw.lower().startswith("input"):
            message = raw
    return JSONResponse(status_code=422, content={"detail": message})


def _device_or_404(conn, device_id):
    row = db.get_device(conn, device_id)
    if row is None:
        raise HTTPException(status_code=404, detail="الجهاز غير موجود")
    return row


def _ensure_unique(conn, ip, port, ignore_id=None):
    if db.ip_taken(conn, ip, port, ignore_id):
        raise HTTPException(status_code=409, detail="هذا العنوان والمنفذ محفوظان لجهاز آخر")


@app.get("/api/devices")
def get_devices():
    conn = db.connect()
    try:
        return [_device_out(row) for row in db.list_devices(conn)]
    finally:
        conn.close()


@app.post("/api/devices", status_code=201)
def post_device(body: DeviceIn):
    conn = db.connect()
    try:
        _ensure_unique(conn, body.ip, body.port)
        device_id = db.create_device(conn, body.name, body.ip, body.port, body.password)
        row = db.list_devices(conn)
        match = next(item for item in row if item["id"] == device_id)
        return _device_out(match)
    finally:
        conn.close()


@app.put("/api/devices/{device_id}")
def put_device(device_id: int, body: DeviceIn):
    conn = db.connect()
    try:
        _device_or_404(conn, device_id)
        _ensure_unique(conn, body.ip, body.port, device_id)
        db.update_device(conn, device_id, body.name, body.ip, body.port, body.password)
        match = next(item for item in db.list_devices(conn) if item["id"] == device_id)
        return _device_out(match)
    finally:
        conn.close()


@app.delete("/api/devices/{device_id}", status_code=204)
def remove_device(device_id: int):
    conn = db.connect()
    try:
        _device_or_404(conn, device_id)
        db.delete_device(conn, device_id)
    finally:
        conn.close()
    return Response(status_code=204)


@app.post("/api/devices/test")
def post_test(body: ConnectionIn):
    try:
        message = test_connection(body.ip, body.port, body.password)
    except DeviceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"ok": True, "message": message}


@app.post("/api/devices/{device_id}/sync")
def post_sync(device_id: int):
    conn = db.connect()
    try:
        device = _device_or_404(conn, device_id)
        try:
            users, logs = pull_device(device["ip"], device["port"], device["password"])
            added, total = db.save_pull(conn, device_id, users, logs)
            message = f"تم السحب: {added} بصمة جديدة، الإجمالي {total}"
            db.mark_sync(conn, device_id, True, message)
        except DeviceError as exc:
            db.mark_sync(conn, device_id, False, str(exc))
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            log.exception("Sync failed")
            message = "تعذر سحب البصمات من الجهاز"
            db.mark_sync(conn, device_id, False, message)
            raise HTTPException(status_code=502, detail=message) from exc
        return {"ok": True, "message": message, "added": added, "total": total, "users": len(users)}
    finally:
        conn.close()


FINGER_LABELS = {
    0: "خنصر اليد اليسرى",
    1: "بنصر اليد اليسرى",
    2: "الوسطى اليسرى",
    3: "السبابة اليسرى",
    4: "إبهام اليد اليسرى",
    5: "إبهام اليد اليمنى",
    6: "السبابة اليمنى",
    7: "الوسطى اليمنى",
    8: "بنصر اليد اليمنى",
    9: "خنصر اليد اليمنى",
}


def _fingers_payload(raw):
    if raw is None:
        return {
            "fingers_known": False,
            "enrolled": False,
            "finger_count": 0,
            "fingers": [],
        }
    try:
        ids = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        ids = []
    if not isinstance(ids, list):
        ids = []
    fingers = []
    for fid in ids:
        try:
            fid = int(fid)
        except (TypeError, ValueError):
            continue
        fingers.append({"id": fid, "name": FINGER_LABELS.get(fid, f"إصبع {fid + 1}")})
    return {
        "fingers_known": True,
        "enrolled": bool(fingers),
        "finger_count": len(fingers),
        "fingers": fingers,
    }


def _employee_out(row):
    payload = _fingers_payload(row["fingers"])
    return {
        "id": row["id"],
        "device_id": row["device_id"],
        "device_name": row["device_name"],
        "user_id": row["user_id"],
        "name": row["name"] or "",
        **payload,
    }


@app.get("/api/employees")
def get_employees(
    device_id: int | None = None,
    q: str = "",
    page: int = Query(default=1, ge=1),
):
    conn = db.connect()
    try:
        if device_id is not None:
            _device_or_404(conn, device_id)
        rows, total = db.query_employees(conn, device_id, (q or "").strip(), page)
        return {
            "items": [_employee_out(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": db.PAGE_SIZE,
        }
    finally:
        conn.close()


@app.post("/api/devices/{device_id}/employees", status_code=201)
def post_employee(device_id: int, body: EmployeeIn):
    conn = db.connect()
    try:
        device = _device_or_404(conn, device_id)
        try:
            add_device_user(device["ip"], device["port"], device["password"], body.user_id, body.name)
        except DuplicateUser as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except DeviceError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        db.upsert_employees(conn, device_id, [{"user_id": body.user_id, "name": body.name, "fingers": []}])
        conn.commit()
        row = next(item for item in db.list_employees(conn, device_id) if item["user_id"] == body.user_id)
        return _employee_out(row)
    finally:
        conn.close()


@app.put("/api/devices/{device_id}/employees/{user_id}")
def put_employee(device_id: int, user_id: str, body: EmployeeUpdate):
    user_id = (user_id or "").strip()
    if not user_id.isdigit():
        raise HTTPException(status_code=400, detail="رقم الموظف غير صحيح")
    conn = db.connect()
    try:
        device = _device_or_404(conn, device_id)
        try:
            update_device_user(device["ip"], device["port"], device["password"], user_id, body.name)
        except DeviceError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        db.upsert_employees(conn, device_id, [{"user_id": user_id, "name": body.name}])
        conn.commit()
        row = next(item for item in db.list_employees(conn, device_id) if item["user_id"] == user_id)
        return _employee_out(row)
    finally:
        conn.close()


@app.delete("/api/devices/{device_id}/employees/{user_id}", status_code=204)
def remove_employee(device_id: int, user_id: str):
    user_id = (user_id or "").strip()
    if not user_id.isdigit():
        raise HTTPException(status_code=400, detail="رقم الموظف غير صحيح")
    conn = db.connect()
    try:
        device = _device_or_404(conn, device_id)
        found = conn.execute(
            "SELECT 1 FROM employees WHERE device_id = ? AND user_id = ?",
            (device_id, user_id),
        ).fetchone()
        if found is None:
            raise HTTPException(status_code=404, detail="الموظف غير موجود")
        try:
            delete_device_user(device["ip"], device["port"], device["password"], user_id)
        except DeviceError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        db.delete_employee(conn, device_id, user_id)
        conn.commit()
    finally:
        conn.close()


@app.post("/api/devices/{device_id}/employees/refresh")
def refresh_employees(device_id: int):
    conn = db.connect()
    try:
        device = _device_or_404(conn, device_id)
        try:
            users = list_device_users(device["ip"], device["port"], device["password"])
        except DeviceError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        db.upsert_employees(conn, device_id, users)
        conn.commit()
        rows = db.list_employees(conn, device_id)
        return {
            "ok": True,
            "message": f"تم تحديث {len(users)} موظف من الجهاز",
            "items": [_employee_out(row) for row in rows],
        }
    finally:
        conn.close()


@app.get("/api/logs")
def get_logs(
    device_id: int | None = None,
    q: str = "",
    date_from: str | None = None,
    date_to: str | None = None,
    kind: str = "all",
    page: int = Query(default=1, ge=1),
):
    device_id, query, date_from, date_to, kind = _filters(device_id, q, date_from, date_to, kind)
    conn = db.connect()
    try:
        rows, total = db.query_logs(
            conn,
            device_id,
            query,
            date_from,
            date_to,
            kind,
            order="desc",
            page=page,
        )
        return {
            "items": [_log_item(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": db.PAGE_SIZE,
        }
    finally:
        conn.close()


@app.get("/api/logs/export")
def export_logs(
    device_id: int | None = None,
    q: str = "",
    date_from: str | None = None,
    date_to: str | None = None,
    kind: str = "all",
):
    device_id, query, date_from, date_to, kind = _filters(device_id, q, date_from, date_to, kind)
    conn = db.connect()
    try:
        rows, total = db.query_logs(
            conn,
            device_id,
            query,
            date_from,
            date_to,
            kind,
            order="asc",
            page=None,
        )
        if total == 0:
            raise HTTPException(status_code=400, detail="لا توجد بصمات مطابقة للتصدير")
        device_name = "كل الأجهزة"
        if device_id is not None:
            device = db.get_device(conn, device_id)
            device_name = device["name"] if device else "كل الأجهزة"
        payload = build_workbook(
            [_log_item(row) for row in rows],
            {
                "exported_at": display_stamp(now_stamp()),
                "count": f"{total:,}",
                "device": device_name,
                "date_from": display_date(date_from),
                "date_to": display_date(date_to),
                "kind": KIND_LABELS[kind],
                "query": query,
            },
        )
    finally:
        conn.close()

    filename = f"بصمات_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@app.get("/api/stats")
def get_stats():
    conn = db.connect()
    try:
        data = db.dashboard(conn)
        peak = max((day["count"] for day in data["days"]), default=0)
        device_peak = max((row["punches"] for row in data["by_device"]), default=0)
        return {
            "today": display_date(data["today"]),
            "weekday": weekday_name(data["today"]),
            "week_from": display_date(data["week_start"]),
            "month_from": display_date(data["month_start"]),
            "devices": data["devices"],
            "employees": data["employees"],
            "unnamed": data["unnamed"],
            "punches": data["punches"],
            "today_punches": data["today_punches"],
            "week_punches": data["week_punches"],
            "month_punches": data["month_punches"],
            "synced_ok": data["synced_ok"],
            "days": [
                {
                    "date": display_date(day["date"]),
                    "weekday": weekday_name(day["date"]),
                    "count": day["count"],
                    "share": 0 if peak == 0 else round(day["count"] * 100 / peak),
                }
                for day in data["days"]
            ],
            "by_device": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "employees": row["employees"],
                    "punches": row["punches"],
                    "share": 0 if device_peak == 0 else round(row["punches"] * 100 / device_peak),
                    "last_sync_at": display_stamp(row["last_sync_at"]) or None,
                    "last_ok": bool(row["last_ok"]),
                    "ever_synced": row["last_sync_at"] is not None,
                    "last_status": row["last_status"] or "",
                }
                for row in data["by_device"]
            ],
            "recent": [_log_item(row) for row in data["recent"]],
        }
    finally:
        conn.close()


@app.get("/")
def root():
    return spa("")


@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="غير موجود")
    if not DIST.exists():
        return JSONResponse(
            status_code=503,
            content={"detail": "الواجهة غير مبنية بعد. شغّل start.bat"},
        )
    candidate = (DIST / full_path).resolve()
    if candidate.is_file() and DIST.resolve() in candidate.parents:
        return FileResponse(candidate)
    return FileResponse(DIST / "index.html")
