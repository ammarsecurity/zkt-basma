from datetime import datetime

STATUS_LABELS = {
    0: "دخول",
    1: "خروج",
    2: "خروج استراحة",
    3: "عودة من استراحة",
    4: "دخول إضافي",
    5: "خروج إضافي",
}

KIND_LABELS = {
    "all": "الكل",
    "in": "دخول",
    "out": "خروج",
}


def now_stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def status_label(status):
    try:
        code = int(status)
    except (TypeError, ValueError):
        return "غير معروف"
    return STATUS_LABELS.get(code, f"حالة {code}")


def status_kind(status):
    try:
        code = int(status)
    except (TypeError, ValueError):
        return "other"
    if code == 0:
        return "in"
    if code == 1:
        return "out"
    return "other"


WEEKDAYS = (
    "الاثنين",
    "الثلاثاء",
    "الأربعاء",
    "الخميس",
    "الجمعة",
    "السبت",
    "الأحد",
)


def weekday_name(value):
    if not value or len(value) < 10:
        return ""
    try:
        day = datetime.strptime(value[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    return WEEKDAYS[day.weekday()]


def split_stamp(value):
    if not value or len(value) < 10:
        return "", ""
    year, month, day = value[:10].split("-")
    clock = value[11:19] if len(value) >= 19 else ""
    return f"{day}/{month}/{year}", clock


def clock_12(clock, with_seconds=True):
    if not clock or len(clock) < 5:
        return clock or ""
    try:
        hour = int(clock[0:2])
    except ValueError:
        return clock
    minute = clock[3:5]
    second = clock[6:8] if len(clock) >= 8 else ""
    suffix = "ص" if hour < 12 else "م"
    hour12 = hour % 12 or 12
    text = f"{hour12:02d}:{minute}"
    if with_seconds and second:
        text = f"{text}:{second}"
    return f"{text} {suffix}"


def display_stamp(value):
    date_text, clock = split_stamp(value)
    if not date_text:
        return ""
    if not clock:
        return date_text
    return f"{date_text} {clock_12(clock, with_seconds=False)}"


def display_date(value):
    if not value:
        return "غير محدد"
    date_text, _clock = split_stamp(f"{value} 00:00:00")
    return date_text or "غير محدد"
