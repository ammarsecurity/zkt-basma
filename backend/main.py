import logging
import json
import secrets
import socket
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from urllib.parse import quote

import ipaddress
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, field_validator

import db
from excel_export import build_summary_workbook, build_workbook
from formatting import (
    KIND_LABELS,
    clock_12,
    display_date,
    display_stamp,
    duration_between,
    now_stamp,
    split_stamp,
    status_kind,
    status_label,
    weekday_name,
)
from paths import frontend_dist
from zk_service import (
    DeviceError,
    DuplicateUser,
    add_device_user,
    delete_device_user,
    list_device_users,
    pull_device,
    sync_clock,
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

LOCAL_HOSTS = {"127.0.0.1", "::1"}


def _client_host(request: Request):
    if request.client is None:
        return ""
    return request.client.host or ""


@app.middleware("http")
async def guard_remote_api(request: Request, call_next):
    path = request.url.path
    if path == "/api" or path.startswith("/api/"):
        local = _client_host(request) in LOCAL_HOSTS
        if path == "/api/v1" or path.startswith("/api/v1/"):
            provided = request.headers.get("x-api-key", "")
            conn = db.connect()
            try:
                expected = db.get_api_key(conn)
            finally:
                conn.close()
            if not provided or not secrets.compare_digest(provided, expected):
                return JSONResponse(status_code=401, content={"detail": "مفتاح الربط غير صحيح"})
        elif not local:
            return JSONResponse(status_code=403, content={"detail": "هذه الواجهة متاحة من هذه الحاسبة فقط"})
    return await call_next(request)


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


@app.post("/api/devices/{device_id}/time")
def post_time(device_id: int):
    conn = db.connect()
    try:
        device = _device_or_404(conn, device_id)
        try:
            before, after = sync_clock(device["ip"], device["port"], device["password"])
        except DeviceError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        previous = _when(before) or "غير معروفة"
        current = _when(after)
        return {
            "ok": True,
            "message": f"ضُبطت ساعة الجهاز. كانت {previous} وأصبحت {current}",
            "before": previous,
            "after": current,
        }
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
    finger: str = "all",
    page: int = Query(default=1, ge=1),
):
    if finger not in ("all", "none", "enrolled"):
        raise HTTPException(status_code=400, detail="فلتر البصمة غير صحيح")
    conn = db.connect()
    try:
        if device_id is not None:
            _device_or_404(conn, device_id)
        rows, total = db.query_employees(conn, device_id, (q or "").strip(), page, finger)
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


def _when(value):
    if not value:
        return ""
    date_text, clock = split_stamp(value)
    if not date_text:
        return ""
    if not clock:
        return date_text
    return f"{date_text} {clock_12(clock, with_seconds=True)}"


def _attendance_period(mode, day, month):
    if mode == "month":
        text = (month or "").strip()
        try:
            year_text, month_text = text.split("-")
            start = date(int(year_text), int(month_text), 1)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="الشهر غير صحيح") from None
        if start.month == 12:
            end = date(start.year + 1, 1, 1)
        else:
            end = date(start.year, start.month + 1, 1)
        label = f"{start.month:02d}/{start.year}"
        return start.isoformat(), end.isoformat(), label
    text = (day or "").strip()
    try:
        start = date.fromisoformat(text)
    except ValueError:
        raise HTTPException(status_code=400, detail="التاريخ غير صحيح") from None
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat(), display_date(start.isoformat())


def _attendance_item(row):
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "employee_name": row["employee_name"] or "",
        "device_id": row["device_id"],
        "device_name": row["device_name"],
        "present": row["punches"] > 0,
        "punches": row["punches"],
        "days": row["days"],
        "first_at": _when(row["first_punch"]),
        "last_at": _when(row["last_punch"]),
    }


def _attendance_query(mode, day, month, device_id, q, status, page):
    if mode not in ("day", "month"):
        raise HTTPException(status_code=400, detail="نوع التقرير غير صحيح")
    if status not in ("all", "present", "absent"):
        raise HTTPException(status_code=400, detail="فلتر الحضور غير صحيح")
    start, end, label = _attendance_period(mode, day, month)
    conn = db.connect()
    try:
        if device_id is not None:
            _device_or_404(conn, device_id)
        rows, total, present, absent = db.attendance_summary(
            conn,
            start,
            end,
            device_id,
            (q or "").strip(),
            status,
            page,
        )
        device_name = "كل الأجهزة"
        if device_id is not None:
            device = db.get_device(conn, device_id)
            device_name = device["name"] if device else "كل الأجهزة"
        return {
            "mode": mode,
            "label": label,
            "device": device_name,
            "items": [_attendance_item(row) for row in rows],
            "total": total,
            "present": present,
            "absent": absent,
            "page": page or 1,
            "page_size": db.PAGE_SIZE,
        }
    finally:
        conn.close()


@app.get("/api/attendance")
def get_attendance(
    mode: str = "day",
    date_value: str | None = Query(default=None, alias="date"),
    month: str | None = None,
    device_id: int | None = None,
    q: str = "",
    status: str = "all",
    page: int = Query(default=1, ge=1),
):
    return _attendance_query(mode, date_value, month, device_id, q, status, page)


@app.get("/api/attendance/export")
def export_attendance(
    mode: str = "day",
    date_value: str | None = Query(default=None, alias="date"),
    month: str | None = None,
    device_id: int | None = None,
    q: str = "",
    status: str = "all",
):
    data = _attendance_query(mode, date_value, month, device_id, q, status, None)
    if data["total"] == 0:
        raise HTTPException(status_code=400, detail="لا توجد سجلات مطابقة للتصدير")
    if mode == "month":
        headers = ["ت", "اسم الموظف", "رقم الموظف", "الجهاز", "أيام الحضور", "أول بصمة", "آخر بصمة", "عدد البصمات"]
        widths = [8, 28, 16, 22, 16, 24, 24, 16]
        title = "التقرير الشهري للحضور"
        sheet = "الحضور الشهري"
        values = [
            [
                index,
                row["employee_name"] or "—",
                row["user_id"],
                row["device_name"],
                row["days"],
                row["first_at"] or "—",
                row["last_at"] or "—",
                row["punches"],
            ]
            for index, row in enumerate(data["items"], start=1)
        ]
        filename = f"حضور_{month or 'شهر'}.xlsx"
    else:
        headers = ["ت", "اسم الموظف", "رقم الموظف", "الجهاز", "أول بصمة", "آخر بصمة", "عدد البصمات", "الحالة"]
        widths = [8, 28, 16, 22, 24, 24, 16, 14]
        title = "ملخص حضور اليوم"
        sheet = "حضور اليوم"
        values = [
            [
                index,
                row["employee_name"] or "—",
                row["user_id"],
                row["device_name"],
                row["first_at"] or "—",
                row["last_at"] or "—",
                row["punches"],
                "حضر" if row["present"] else "لم يحضر",
            ]
            for index, row in enumerate(data["items"], start=1)
        ]
        filename = f"حضور_{date_value or 'يوم'}.xlsx"
        line = f"الجهاز: {data['device']}  ·  التاريخ: {data['label']}  ·  حضر: {data['present']}  ·  لم يحضر: {data['absent']}"
    if mode == "month":
        line = f"الجهاز: {data['device']}  ·  الشهر: {data['label']}  ·  حضر: {data['present']}  ·  لم يحضر: {data['absent']}"
    payload = build_summary_workbook(
        sheet,
        title,
        headers,
        widths,
        values,
        {
            "exported_at": display_stamp(now_stamp()),
            "count": f"{data['total']:,}",
            "line": line,
        },
    )
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


def _detail_day(day):
    times = day["times"]
    clocks = []
    for stamp in times:
        _date_text, clock = split_stamp(stamp)
        clocks.append(clock_12(clock, with_seconds=True))
    gap = duration_between(times[0], times[-1]) if len(times) >= 2 else ""
    return {
        "date": display_date(day["date"]),
        "weekday": weekday_name(day["date"]),
        "times": clocks,
        "gap": gap,
        "count": len(times),
    }


def _detail_item(row):
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "employee_name": row["employee_name"] or "",
        "device_id": row["device_id"],
        "device_name": row["device_name"],
        "punches": row["punches"],
        "days": [_detail_day(day) for day in row["days"]],
    }


def _detail_query(month, device_id, q, page, user_id=""):
    start, end, label = _attendance_period("month", None, month)
    conn = db.connect()
    try:
        if device_id is not None:
            _device_or_404(conn, device_id)
        rows, total, punch_total = db.month_punch_details(
            conn,
            start,
            end,
            device_id,
            (q or "").strip(),
            page,
            (user_id or "").strip(),
        )
        device_name = "كل الأجهزة"
        if device_id is not None:
            device = db.get_device(conn, device_id)
            device_name = device["name"] if device else "كل الأجهزة"
        return {
            "label": label,
            "device": device_name,
            "items": [_detail_item(row) for row in rows],
            "total": total,
            "punches": punch_total,
            "page": page or 1,
            "page_size": db.PAGE_SIZE,
        }
    finally:
        conn.close()


@app.get("/api/attendance/details")
def get_attendance_details(
    month: str | None = None,
    device_id: int | None = None,
    q: str = "",
    user_id: str = "",
    page: int = Query(default=1, ge=1),
):
    return _detail_query(month, device_id, q, page, user_id)


@app.get("/api/attendance/details/export")
def export_attendance_details(
    month: str | None = None,
    device_id: int | None = None,
    q: str = "",
    user_id: str = "",
):
    data = _detail_query(month, device_id, q, None, user_id)
    if data["total"] == 0:
        raise HTTPException(status_code=400, detail="لا توجد سجلات مطابقة للتصدير")
    headers = ["ت", "اسم الموظف", "رقم الموظف", "الجهاز", "عدد البصمات", "اليوم", "التاريخ", "أوقات البصمات", "فرق الوقت"]
    widths = [8, 28, 16, 18, 16, 14, 16, 42, 16]
    values = []
    index = 1
    for employee in data["items"]:
        name = employee["employee_name"] or "—"
        if not employee["days"]:
            values.append([index, name, employee["user_id"], employee["device_name"], employee["punches"], "—", "—", "—", "—"])
            index += 1
            continue
        for day in employee["days"]:
            values.append([
                index,
                name,
                employee["user_id"],
                employee["device_name"],
                employee["punches"],
                day["weekday"],
                day["date"],
                " — ".join(day["times"]),
                day["gap"] or "—",
            ])
            index += 1
    one = data["items"][0] if user_id and len(data["items"]) == 1 else None
    filename = f"تفاصيل_{one['user_id']}_{month or 'شهر'}.xlsx" if one else f"تفاصيل_{month or 'شهر'}.xlsx"
    title = "تفاصيل بصمات الموظف" if one else "تفاصيل بصمات الشهر"
    who = (one["employee_name"] or one["user_id"]) if one else ""
    line = f"الجهاز: {data['device']}  ·  الشهر: {data['label']}  ·  عدد البصمات: {data['punches']}"
    if who:
        line = f"الموظف: {who}  ·  {line}"
    payload = build_summary_workbook(
        "تفاصيل الشهر",
        title,
        headers,
        widths,
        values,
        {
            "exported_at": display_stamp(now_stamp()),
            "count": f"{len(values):,}",
            "line": line,
        },
    )
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


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


def _base_urls():
    found = []

    def add(ip):
        if not ip or ip.startswith("127.") or ip.startswith("169.254."):
            return
        url = f"http://{ip}:8000/api/v1"
        if url not in found:
            found.append(url)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        add(sock.getsockname()[0])
        sock.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            add(info[4][0])
    except OSError:
        pass
    if not found:
        found.append("http://127.0.0.1:8000/api/v1")
    return found


def _integration_payload(key):
    return {"key": key, "header": "X-API-Key", "base_urls": _base_urls()}


@app.get("/api/integration")
def get_integration():
    conn = db.connect()
    try:
        return _integration_payload(db.get_api_key(conn))
    finally:
        conn.close()


@app.post("/api/integration/regenerate")
def regenerate_integration():
    conn = db.connect()
    try:
        return _integration_payload(db.regenerate_api_key(conn))
    finally:
        conn.close()


def _public_device(item):
    return {key: value for key, value in item.items() if key != "password"}


@app.get("/api/v1/devices")
def v1_devices():
    return [_public_device(item) for item in get_devices()]


@app.get("/api/v1/employees")
def v1_employees(
    device_id: int | None = None,
    q: str = "",
    finger: str = "all",
    page: int = Query(default=1, ge=1),
):
    return get_employees(device_id, q, finger, page)


@app.get("/api/v1/logs")
def v1_logs(
    device_id: int | None = None,
    q: str = "",
    date_from: str | None = None,
    date_to: str | None = None,
    kind: str = "all",
    page: int = Query(default=1, ge=1),
):
    return get_logs(device_id, q, date_from, date_to, kind, page)


@app.get("/api/v1/attendance")
def v1_attendance(
    mode: str = "day",
    date_value: str | None = Query(default=None, alias="date"),
    month: str | None = None,
    device_id: int | None = None,
    q: str = "",
    status: str = "all",
    page: int = Query(default=1, ge=1),
):
    return get_attendance(mode, date_value, month, device_id, q, status, page)


@app.get("/api/v1/attendance/details")
def v1_attendance_details(
    month: str | None = None,
    device_id: int | None = None,
    q: str = "",
    user_id: str = "",
    page: int = Query(default=1, ge=1),
):
    return get_attendance_details(month, device_id, q, user_id, page)


@app.post("/api/v1/devices/{device_id}/employees", status_code=201)
def v1_post_employee(device_id: int, body: EmployeeIn):
    return post_employee(device_id, body)


@app.post("/api/v1/devices/{device_id}/sync")
def v1_post_sync(device_id: int):
    return post_sync(device_id)


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
