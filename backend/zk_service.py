import logging

from zk import ZK

log = logging.getLogger("zkt")


class DeviceError(Exception):
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


def pull_device(ip, port, password):
    conn = _open(ip, port, password, timeout=120)
    disabled = False
    try:
        try:
            conn.disable_device()
            disabled = True
        except Exception:
            log.debug("disable_device skipped", exc_info=True)

        users = []
        seen_users = set()
        try:
            for user in conn.get_users() or []:
                user_id = _clean_text(getattr(user, "user_id", ""))
                if not user_id or user_id in seen_users:
                    continue
                seen_users.add(user_id)
                name = _clean_text(getattr(user, "name", ""))
                if name == f"NN-{user_id}":
                    name = ""
                users.append({"user_id": user_id, "name": name})
        except Exception:
            log.warning("Reading users failed", exc_info=True)

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
