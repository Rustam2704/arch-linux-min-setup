"""Google Calendar RRULE choices; unfamiliar rules survive unchanged."""
DAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")


def rule(mode, day, selected=()):
    if mode == "none":
        return []
    if mode == "custom":
        codes = [DAYS[i] for i in sorted(set(selected))]
        if not codes:
            raise ValueError("Choose at least one weekday")
        return ["RRULE:FREQ=WEEKLY;BYDAY=" + ",".join(codes)]
    freq = {"daily": "DAILY", "weekly": "WEEKLY", "monthly": "MONTHLY", "yearly": "YEARLY"}[mode]
    suffix = ";BYDAY=" + DAYS[day.weekday()] if mode == "weekly" else ""
    return ["RRULE:FREQ=" + freq + suffix]


def describe(rules, day):
    if not rules:
        return "none", {day.weekday()}
    if len(rules) != 1 or not rules[0].startswith("RRULE:"):
        return "existing", {day.weekday()}
    parts = dict(p.split("=", 1) for p in rules[0][6:].split(";") if "=" in p)
    if set(parts) - {"FREQ", "BYDAY", "INTERVAL"} or parts.get("INTERVAL", "1") != "1":
        return "existing", {day.weekday()}
    freq = parts.get("FREQ", "").lower()
    if freq == "weekly":
        codes = parts.get("BYDAY", DAYS[day.weekday()]).split(",")
        if any(code not in DAYS for code in codes):
            return "existing", {day.weekday()}
        days = {DAYS.index(code) for code in codes}
        return ("weekly" if days == {day.weekday()} else "custom"), days
    if freq in ("daily", "monthly", "yearly") and "BYDAY" not in parts:
        return freq, {day.weekday()}
    return "existing", {day.weekday()}


def capacity(available, row_height, more_height, count):
    """Reserve the disclosure row only if not all events fit."""
    slots = max(0, int(available) // max(1, int(row_height)))
    return count if count <= slots else max(0, (int(available) - int(more_height)) // max(1, int(row_height)))
