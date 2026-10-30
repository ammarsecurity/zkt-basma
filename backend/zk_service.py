import logging

from zk import ZK

log = logging.getLogger("zkt")


class DeviceError(Exception):
    pass


class DuplicateUser(DeviceError):
    pass


def _clean_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        for encoding in ("utf-8", "cp1256", "gbk", "latin-1"):
            try:
                value = value.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            value = value.decode("latin-1", errors="ignore")
    return str(value).replace("\x00", "").strip()


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _stamp(value):
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    text = _clean_text(value)
    return text[:19]


def _open(ip, port, password, timeout):
    try:
        zk = ZK(
            ip,
            port=int(port),
            timeout=timeout,
            password=int(password),
            force_udp=False,
            ommit_ping=True,
            verbose=False,
            encoding="UTF-8",
        )
        return zk.connect()
    except DeviceError:
        raise
    except Exception as exc:
        log.warning("ZK connection failed for %s:%s (%s)", ip, port, exc)
        message = str(exc).lower()
        if "unauth" in message or "password" in message:
            raise DeviceError("رفض الجهاز الاتصال. تحقق من كلمة مرور الاتصال") from exc
        if "timed out" in message or "timeout" in message or "can't reach" in message:
            raise DeviceError(
                "انتهت مهلة الاتصال. تأكد أن الكمبيوتر والجهاز على نفس الشبكة وأن المنفذ مفتوح"
            ) from exc
        raise DeviceError("تعذر الاتصال بالجهاز. تحقق من عنوان IP والمنفذ") from exc


def _close(conn):
    try:
        conn.enable_device()
    except Exception:
        pass
    try:
        conn.disconnect()
    except Exception:
        pass


def test_connection(ip, port, password):
    conn = _open(ip, port, password, timeout=8)
    try:
        name = ""
        try:
            name = _clean_text(conn.get_device_name())
        except Exception:
            log.debug("Device name unavailable", exc_info=True)
        if name:
            return f"تم الاتصال بالجهاز بنجاح: {name}"
        return "تم الاتصال بالجهاز بنجاح"
    finally:
        _close(conn)


def _enrolled_fingers(conn):
    try:
        templates = conn.get_templates() or []
    except Exception:
        log.warning("Reading fingerprint templates failed", exc_info=True)
        return None
    grouped = {}
    for finger in templates:
        size = int(getattr(finger, "size", 0) or 0)
        if size <= 0:
            continue
        uid = int(getattr(finger, "uid", 0) or 0)
        fid = int(getattr(finger, "fid", 0) or 0)
        grouped.setdefault(uid, set()).add(fid)
    return {uid: sorted(fids) for uid, fids in grouped.items()}


def _read_users(conn, with_fingers=False):
    finger_map = _enrolled_fingers(conn) if with_fingers else None
    users = []
    seen = set()
    for user in conn.get_users() or []:
        user_id = _clean_text(getattr(user, "user_id", ""))
        if not user_id or user_id in seen:
            continue
        seen.add(user_id)
        name = _clean_text(getattr(user, "name", ""))
        if name == f"NN-{user_id}":
            name = ""
        item = {"user_id": user_id, "name": name}
        if finger_map is not None:
            uid = int(getattr(user, "uid", 0) or 0)
            item["fingers"] = finger_map.get(uid, [])
        users.append(item)
    return users


def _use_device(ip, port, password, timeout):
    conn = _open(ip, port, password, timeout)
    try:
        conn.disable_device()
    except Exception:
        log.debug("disable_device skipped", exc_info=True)
    return conn


def list_device_users(ip, port, password):
    conn = _use_device(ip, port, password, timeout=30)
    try:
        return _read_users(conn, with_fingers=True)
    except DeviceError:
        raise
    except Exception as exc:
        log.warning("Reading users failed for %s:%s", ip, port, exc_info=True)
        raise DeviceError("تعذر قراءة الموظفين من الجهاز") from exc
    finally:
        _close(conn)


def add_device_user(ip, port, password, user_id, name):
    conn = _use_device(ip, port, password, timeout=30)
    try:
        try:
            existing = _read_users(conn)
        except Exception as exc:
            log.warning("Reading users before add failed", exc_info=True)
            raise DeviceError("تعذر قراءة الموظفين من الجهاز") from exc
        if any(user["user_id"] == user_id for user in existing):
            raise DuplicateUser("رقم الموظف موجود على الجهاز")
        try:
            conn.set_user(
                uid=None,
                name=name,
                privilege=0,
                password="",
                group_id="",
                user_id=user_id,
                card=0,
            )
        except DeviceError:
            raise
        except Exception as exc:
            log.warning("set_user failed for %s", user_id, exc_info=True)
            raise DeviceError("تعذر إضافة الموظف على الجهاز") from exc
    finally:
        _close(conn)


def update_device_user(ip, port, password, user_id, name):
    conn = _use_device(ip, port, password, timeout=30)
    try:
        try:
            users = conn.get_users() or []
        except Exception as exc:
            log.warning("Reading users before update failed", exc_info=True)
            raise DeviceError("تعذر قراءة الموظفين من الجهاز") from exc
        match = next((user for user in users if _clean_text(getattr(user, "user_id", "")) == user_id), None)
        if match is None:
            raise DeviceError("الموظف غير موجود على الجهاز")
        try:
            conn.set_user(
                uid=int(match.uid),
                name=name,
                privilege=int(getattr(match, "privilege", 0) or 0),
                password=str(getattr(match, "password", "") or ""),
                group_id=str(getattr(match, "group_id", "") or ""),
                user_id=user_id,
                card=int(getattr(match, "card", 0) or 0),
            )
        except DeviceError:
            raise
        except Exception as exc:
            log.warning("set_user update failed for %s", user_id, exc_info=True)
            raise DeviceError("تعذر تعديل الموظف على الجهاز") from exc
    finally:
        _close(conn)


def delete_device_user(ip, port, password, user_id):
    conn = _use_device(ip, port, password, timeout=30)
    try:
        try:
            users = conn.get_users() or []
        except Exception as exc:
            log.warning("Reading users before delete failed", exc_info=True)
            raise DeviceError("تعذر قراءة الموظفين من الجهاز") from exc
        match = next((user for user in users if _clean_text(getattr(user, "user_id", "")) == user_id), None)
        if match is None:
            return False
        try:
            conn.delete_user(uid=int(match.uid))
        except Exception as exc:
            log.warning("delete_user failed for %s", user_id, exc_info=True)
            raise DeviceError("تعذر حذف الموظف من الجهاز") from exc
        return True
    finally:
        _close(conn)


def pull_device(ip, port, password):
    conn = _open(ip, port, password, timeout=120)
    disabled = False
    try:
        try:
            conn.disable_device()
            disabled = True
        except Exception:
            log.debug("disable_device skipped", exc_info=True)

        try:
            users = _read_users(conn)
        except Exception:
            log.warning("Reading users failed", exc_info=True)
            users = []

        logs = []
        seen_logs = set()
        for record in conn.get_attendance() or []:
            user_id = _clean_text(getattr(record, "user_id", ""))
            timestamp = _stamp(getattr(record, "timestamp", None))
            if not user_id or len(timestamp) < 19:
                continue
            key = (user_id, timestamp)
            if key in seen_logs:
                continue
            seen_logs.add(key)
            logs.append(
                {
                    "user_id": user_id,
                    "timestamp": timestamp,
                    "status": _as_int(getattr(record, "status", 0)),
                    "punch": _as_int(getattr(record, "punch", 0)),
                }
            )
        return users, logs
    finally:
        if not disabled:
            try:
                conn.disconnect()
            except Exception:
                pass
        else:
            _close(conn)
