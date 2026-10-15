import sys
"""light-year — Google Calendar and Zoom, without a browser.

Only the Python standard library. Credentials and tokens live in
~/.config/light-year/ (mode 600):
    credentials.json   {"google": {client_id, client_secret},
                        "zoom": {account_id, client_id, client_secret}}
    tokens.json        written by this module

Google: an OAuth "Desktop" client; sign-in opens the browser once, and a tiny
loopback server on 127.0.0.1:8412 exists only for the few seconds of that sign-in.
Zoom: a Server-to-Server OAuth app (create, update, delete meetings).
"""
import base64
import datetime as dt
import http.server
import json
import os
import secrets
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
sys.path.insert(0, os.path.expanduser("~/.local/share/sky-desktop"))
from sky_theme import THEME  # noqa: E402

CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                          "light-year")
CREDENTIALS = os.path.join(CONFIG_DIR, "credentials.json")
TOKENS = os.path.join(CONFIG_DIR, "tokens.json")

HOST, PORT = "127.0.0.1", 8412
REDIRECT = f"http://{HOST}:{PORT}/oauth2callback"
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_API = "https://www.googleapis.com/calendar/v3"
SCOPE = "https://www.googleapis.com/auth/calendar.events"
ZOOM_TOKEN = "https://zoom.us/oauth/token"
ZOOM_API = "https://api.zoom.us/v2"

_lock = threading.RLock()


class ApiError(RuntimeError):
    pass


def local_timezone():
    """IANA name of this machine's timezone; Google and Zoom both want it by name."""
    try:
        return os.path.realpath("/etc/localtime").split("zoneinfo/", 1)[1]
    except IndexError:
        return "UTC"


TZ = local_timezone()


# ------------------------------------------------------------------ storage
def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def credentials():
    return read_json(CREDENTIALS)


def tokens():
    return read_json(TOKENS)


# ------------------------------------------------------------------ http
def request(url, method="GET", data=None, headers=None, form=False):
    headers = dict(headers or {})
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        else:
            body = json.dumps(data).encode()
            headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            text = r.read().decode()
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:300]
        raise ApiError(f"{e.code} {e.reason}: {detail}") from None
    except urllib.error.URLError as e:
        raise ApiError(f"No connection ({e.reason})") from None


# ------------------------------------------------------------------ google
def google_token():
    with _lock:
        store = tokens()
        g = store.get("google", {})
        if g.get("access_token") and g.get("expires_at", 0) > time.time() + 60:
            return g["access_token"]
        if not g.get("refresh_token"):
            return None
        creds = credentials().get("google", {})
        try:
            fresh = request(GOOGLE_TOKEN, "POST", {
                "client_id": creds.get("client_id", ""), "client_secret": creds.get("client_secret", ""),
                "refresh_token": g["refresh_token"], "grant_type": "refresh_token"}, form=True)
        except ApiError as e:
            if "invalid_grant" not in str(e):
                raise
            store.pop("google", None)
            write_json(TOKENS, store)
            raise ApiError("Google sign-in expired - press Connect Google") from None
        g.update(access_token=fresh["access_token"], expires_at=time.time() + fresh.get("expires_in", 3600))
        store["google"] = g
        write_json(TOKENS, store)
        return g["access_token"]


def google(path, method="GET", data=None, params=None, etag=None):
    token = google_token()
    if not token:
        raise ApiError("Google is not connected")
    url = GOOGLE_API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    headers = {"Authorization": f"Bearer {token}"}
    if etag:
        headers["If-Match"] = etag          # 412 if the event changed since
    return request(url, method, data, headers)


def google_sign_in(done):
    """Open the Google consent page in the browser and wait (in a thread) for the
    redirect on the loopback port. Calls done(error_or_None)."""
    creds = credentials().get("google", {})
    if not creds.get("client_id"):
        done(f"Add a Google client_id to {CREDENTIALS}")
        return

    result = {}
    state_token = secrets.token_urlsafe(32)

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(url.query)
            if (url.path != urllib.parse.urlparse(REDIRECT).path
                    or not secrets.compare_digest(q.get("state", [""])[0], state_token)):
                self.send_error(404)
                return
            if not q.get("code") and not q.get("error"):
                self.send_error(400)
                return
            result["code"] = q.get("code", [""])[0]
            result["error"] = q.get("error", [""])[0]
            msg = ("light-year is connected to Google. You can close this tab."
                   if result["code"] else f"Sign-in failed: {result['error'] or 'no code'}")
            body = (f"<!doctype html><meta charset=utf-8><body style='background:#0a0e11;"
                    f"color:{THEME['foreground']};font:16px {THEME['font']},sans-serif;padding:40px'>{msg}</body>").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def run():
        try:
            server = http.server.HTTPServer((HOST, PORT), Handler)
        except OSError as e:
            done(f"Port {PORT} is busy: {e}")
            return
        params = urllib.parse.urlencode({
            "client_id": creds["client_id"], "redirect_uri": REDIRECT, "response_type": "code",
            "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": state_token})
        try:
            subprocess.Popen(["xdg-open", f"{GOOGLE_AUTH}?{params}"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline = time.monotonic() + 300
            while not result and time.monotonic() < deadline:
                server.timeout = min(1, max(0, deadline - time.monotonic()))
                server.handle_request()
        except Exception as e:                  # noqa: BLE001 - shown in the window
            done(str(e))
            return
        finally:
            server.server_close()
        if not result.get("code"):
            done(result.get("error") or "Google sign-in was cancelled or timed out")
            return
        try:
            fresh = request(GOOGLE_TOKEN, "POST", {
                "code": result["code"], "client_id": creds["client_id"],
                "client_secret": creds["client_secret"], "redirect_uri": REDIRECT,
                "grant_type": "authorization_code"}, form=True)
            with _lock:
                store = tokens()
                store["google"] = {"refresh_token": fresh["refresh_token"],
                                   "access_token": fresh["access_token"],
                                   "expires_at": time.time() + fresh.get("expires_in", 3600)}
                write_json(TOKENS, store)
            done(None)
        except Exception as e:                  # noqa: BLE001 - shown in the window
            done(str(e))

    threading.Thread(target=run, daemon=True).start()


# ------------------------------------------------------------------ zoom
def zoom_token():
    creds = credentials().get("zoom", {})
    if not creds.get("client_id"):
        return None
    with _lock:
        store = tokens()
        z = store.get("zoom", {})
        if z.get("access_token") and z.get("expires_at", 0) > time.time() + 60:
            return z["access_token"]
        basic = base64.b64encode(f"{creds['client_id']}:{creds['client_secret']}".encode()).decode()
        fresh = request(ZOOM_TOKEN, "POST", {"grant_type": "account_credentials",
                                             "account_id": creds["account_id"]},
                        {"Authorization": f"Basic {basic}"}, form=True)
        store["zoom"] = {"access_token": fresh["access_token"],
                         "expires_at": time.time() + fresh.get("expires_in", 3600)}
        write_json(TOKENS, store)
        return store["zoom"]["access_token"]


def zoom(path, method, data=None):
    token = zoom_token()
    if not token:
        return None
    return request(ZOOM_API + path, method, data, {"Authorization": f"Bearer {token}"})


# ------------------------------------------------------------------ calendar
def state():
    creds = credentials()
    return {"google": bool(tokens().get("google", {}).get("refresh_token")),
            "google_configured": bool(creds.get("google", {}).get("client_id")),
            "zoom": bool(creds.get("zoom", {}).get("client_id"))}


def parse_time(value):
    """Google start/end -> (local aware datetime or date, all_day)."""
    if "T" in value:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(), False
    return dt.date.fromisoformat(value), True


def list_events(start, end):
    """Events between two local dates (inclusive start, exclusive end)."""
    tmin = dt.datetime.combine(start, dt.time()).astimezone().isoformat()
    tmax = dt.datetime.combine(end, dt.time()).astimezone().isoformat()
    params = {"timeMin": tmin, "timeMax": tmax, "singleEvents": "true",
              "orderBy": "startTime", "maxResults": "250"}
    items = []
    while True:
        page = google("/calendars/primary/events", params=params)
        items.extend(page.get("items", []))
        if not page.get("nextPageToken"):
            break
        params["pageToken"] = page["nextPageToken"]
    out = []
    for e in items:
        s, all_day = parse_time(e["start"].get("dateTime") or e["start"]["date"])
        f, _ = parse_time(e["end"].get("dateTime") or e["end"]["date"])
        text = e.get("location", "") + " " + e.get("description", "")
        link = next((w for w in text.split() if "zoom.us/" in w), "")
        orig = e.get("originalStartTime") or {}
        out.append({"id": e["id"], "summary": e.get("summary") or "(untitled)",
                    "start": s, "end": f, "all_day": all_day,
                    "description": e.get("description", ""), "zoom": link,
                    "recurring_id": e.get("recurringEventId"),
                    "original_start": orig.get("dateTime") or orig.get("date")})
    return out


def event_days(event, first, last):
    """Visible local dates covered by an event; Google all-day ends are exclusive."""
    start, end = event["start"], event["end"]
    if event["all_day"]:
        begin, finish = start, end - dt.timedelta(days=1)
    else:
        begin = start.date()
        finish = (end - dt.timedelta(microseconds=1)).date()
    day = max(first, begin)
    while day <= min(last, finish):
        yield day
        day += dt.timedelta(days=1)


def _iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:00")


def _event_times(start, end):
    if isinstance(start, dt.datetime) and isinstance(end, dt.datetime):
        return {"dateTime": _iso(start), "timeZone": TZ}, {"dateTime": _iso(end), "timeZone": TZ}
    if (isinstance(start, dt.date) and not isinstance(start, dt.datetime)
            and isinstance(end, dt.date) and not isinstance(end, dt.datetime)):
        return {"date": start.isoformat()}, {"date": end.isoformat()}
    raise ValueError("Event start and end must both be dates or times")


def _patch_times(start, end):
    """_event_times for a PATCH body: PATCH merges nested objects, so the other kind of time is nulled."""
    start_body, end_body = _event_times(start, end)
    cleared = {"dateTime": None, "timeZone": None} if "date" in start_body else {"date": None}
    return {**start_body, **cleared}, {**end_body, **cleared}


MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _path(event_id):
    return f"/calendars/primary/events/{urllib.parse.quote(event_id)}"


def _short(day):
    return f"{day.day} {MONTHS[day.month - 1]}"


class Change:
    """One saved action: the event it left behind, and how to take it back.

    `steps` run last first. ("PATCH" or "DELETE", event id, body, etag) is a request;
    the etag is the event's right after the action, so an undo stops instead of
    overwriting a change made on the phone in the meantime. ("REAPPLY", series id,
    exceptions) puts back cancelled, moved and edited occurrences, which Google
    forgets whenever a series' times or rule change."""
    def __init__(self, label, event=None):
        self.label, self.event = label, event
        self.steps = []
        self.meetings = []          # Zoom meetings to delete once this can no longer be undone
        self.new_meetings = []      # Zoom meetings it created: deleted if it is undone
        self.warning = None

    def inverse(self, *step):
        self.steps.append(step)

    def touches(self):
        return {step[1].split("_")[0] for step in self.steps}     # an occurrence counts as its series

    def loosen(self, ids):
        """A later change of ours touched these events as well, so their etags no
        longer tell anything about edits made elsewhere: undo them without the check."""
        self.steps = [step if step[0] == "REAPPLY" or step[1].split("_")[0] not in ids
                      else step[:3] + (None,) for step in self.steps]


def _restore_time(value):
    """A Google start/end as it was, for a PATCH that puts it back."""
    if "date" in value:
        return {"date": value["date"], "dateTime": None, "timeZone": None}
    return {"dateTime": value["dateTime"], "timeZone": value.get("timeZone"), "date": None}


def _inverse_body(before, body):
    return {k: _restore_time(before[k]) if k in ("start", "end") else before.get(k) for k in body}


def create_event(summary, start, end, description="", with_zoom=False, recurrence=None):
    event_start, event_end = _event_times(start, end)
    body = {"summary": summary or "Untitled",
            "start": event_start, "end": event_end,
            "description": description}
    if recurrence:
        body["recurrence"] = recurrence
    meeting = None
    if with_zoom:
        if not isinstance(start, dt.datetime):
            raise ValueError("Zoom meetings need a start time")
        minutes = max(15, int((end - start).total_seconds() // 60))
        meeting = zoom("/users/me/meetings", "POST", {
            "topic": body["summary"], "type": 2, "start_time": _iso(start), "timezone": TZ,
            "duration": minutes, "settings": {"join_before_host": True, "waiting_room": False}})
        if meeting:
            if not meeting.get("id"):
                raise ApiError("Zoom did not return a meeting ID")
            body["location"] = meeting.get("join_url", "")
            body["description"] = (description + "\n\n" + body["location"]).strip()
            body["extendedProperties"] = {"private": {"zoomMeetingId": str(meeting.get("id"))}}
    try:
        created = google("/calendars/primary/events", "POST", body)
    except Exception as error:
        if meeting and meeting.get("id"):
            try:
                if zoom(f"/meetings/{meeting['id']}", "DELETE") is None:
                    raise ApiError("Zoom is not connected")
            except Exception as cleanup_error:
                raise ApiError(f"Google event creation failed: {error}; Zoom meeting {meeting['id']} could not be deleted: {cleanup_error}") from error
        raise
    change = Change(f"created “{body['summary']}”", created)
    change.inverse("DELETE", created["id"], None, created.get("etag"))
    if meeting:
        change.new_meetings.append(str(meeting["id"]))
    return change


def _meeting_id(event):
    return ((event.get("extendedProperties") or {}).get("private") or {}).get("zoomMeetingId")


def _follow_zoom(event):
    """A one-off event's own Zoom meeting moves with it. A series shares one meeting
    between all its lessons - a room rather than an appointment - so moving one
    lesson, or the whole series, leaves the meeting alone."""
    mid = _meeting_id(event)
    if (not mid or event.get("status") == "cancelled" or event.get("recurringEventId")
            or event.get("recurrence") or "dateTime" not in event.get("start", {})):
        return
    start = parse_time(event["start"]["dateTime"])[0]
    end = parse_time(event["end"]["dateTime"])[0]
    try:
        zoom(f"/meetings/{mid}", "PATCH", {"start_time": _iso(start), "timezone": TZ,
                                            "duration": max(15, int((end - start).total_seconds() // 60))})
    except ApiError:
        pass


def release_meeting(mid):
    """Delete a Zoom meeting once no event refers to it (the two halves of a split
    series share one)."""
    users = google("/calendars/primary/events",
                   params={"privateExtendedProperty": f"zoomMeetingId={mid}", "maxResults": "1"})
    if users.get("items"):
        return
    try:
        zoom(f"/meetings/{mid}", "DELETE")
    except ApiError as e:
        if not str(e).startswith("404"):
            raise


def update_event(event_id, summary=None, start=None, end=None, description=None, recurrence=None):
    body = {}
    if summary is not None:
        body["summary"] = summary
    if description is not None:
        body["description"] = description
    if start is not None:
        body["start"], body["end"] = _patch_times(start, end)
    if recurrence is not None:
        body["recurrence"] = recurrence
    before = google(_path(event_id))
    updated = google(_path(event_id), "PATCH", body)
    change = Change(f"edited “{before.get('summary', '')}”", updated)
    change.inverse("PATCH", event_id, _inverse_body(before, body), updated.get("etag"))
    _follow_zoom(updated)
    return change


def delete_event(event_id):
    before = google(_path(event_id))
    google(_path(event_id), "DELETE")
    change = Change(f"deleted “{before.get('summary', '')}”")
    change.inverse("PATCH", event_id, {"status": "confirmed"}, None)   # Google keeps deleted events
    mid = _meeting_id(before)
    if mid and not before.get("recurringEventId"):   # one lesson keeps the series' meeting
        change.meetings.append(mid)
    return change


def revert(change):
    """Undo a Change. Raises ApiError if an event was changed elsewhere since."""
    for step in reversed(change.steps):
        if step[0] == "REAPPLY":
            _reapply(step[1], step[2])
            continue
        method, event_id, body, etag = step
        try:
            result = google(_path(event_id), method, body, etag=etag)
        except ApiError as e:
            if str(e).startswith("412"):
                raise ApiError("Not undone: the event was changed elsewhere since") from None
            if method == "DELETE" and str(e).startswith("410"):
                continue                    # already deleted
            raise
        if method == "PATCH":
            _follow_zoom(result)
    for mid in change.new_meetings:
        release_meeting(mid)


# ------------------------------------------------------------------ recurring events
# Changing one occurrence of a series offers the same choices as Zoom / Google:
#   "this"      only this occurrence
#   "following" this and all later ones: the series is cut before this occurrence and a
#               new series starts here with the change applied
#   "all"       the whole series (a move to another weekday moves the weekdays too)
WEEKDAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def _rrule_parts(rule):
    head, _, body = rule.partition(":")
    parts = dict(p.split("=", 1) for p in body.split(";") if "=" in p)
    return head, parts


def _rrule_join(head, parts):
    return head + ":" + ";".join(f"{k}={v}" for k, v in parts.items())


def _shift_weekdays(rules, days):
    """Move BYDAY=MO,WE by `days` (a series dragged to another weekday)."""
    if not days % 7:
        return rules
    out = []
    for rule in rules:
        if rule.startswith("RRULE"):
            head, parts = _rrule_parts(rule)
            if "BYDAY" in parts:
                moved = []
                for d in parts["BYDAY"].split(","):
                    prefix, code = d[:-2], d[-2:]
                    moved.append(prefix + WEEKDAYS[(WEEKDAYS.index(code) + days) % 7])
                parts["BYDAY"] = ",".join(moved)
            rule = _rrule_join(head, parts)
        out.append(rule)
    return out


def _until(rules, until_value):
    """Same rules, ending at until_value (drops COUNT)."""
    out = []
    for rule in rules:
        if rule.startswith("RRULE"):
            head, parts = _rrule_parts(rule)
            parts.pop("COUNT", None)
            parts["UNTIL"] = until_value
            rule = _rrule_join(head, parts)
        out.append(rule)
    return out


def _until_before(original_start):
    """UNTIL that ends a series just before the occurrence starting at original_start."""
    if "T" in original_start:
        t = dt.datetime.fromisoformat(original_start.replace("Z", "+00:00")) - dt.timedelta(seconds=1)
        return t.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (dt.date.fromisoformat(original_start) - dt.timedelta(days=1)).strftime("%Y%m%d")


def _series_end(rid, rules):
    """UNTIL value for the end of a series; for COUNT series, its last occurrence."""
    for rule in rules:
        if rule.startswith("RRULE"):
            _, parts = _rrule_parts(rule)
            if "UNTIL" in parts:
                return parts["UNTIL"]
            if "COUNT" in parts:
                items = google(f"/calendars/primary/events/{urllib.parse.quote(rid)}/instances",
                               params={"maxResults": "2500"}).get("items", [])
                if items:
                    # not in time order (changed occurrences are listed apart): take the latest
                    # ORIGINAL start, i.e. where the series itself ends
                    v = max(parse_time((i.get("originalStartTime") or i["start"]).get("dateTime")
                                       or (i.get("originalStartTime") or i["start"])["date"])[0]
                            for i in items).isoformat()
                    if "T" in v:
                        return dt.datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(
                            dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    return v.replace("-", "")
    return None


def _without_count(rules):
    out = []
    for rule in rules:
        if rule.startswith("RRULE"):
            head, parts = _rrule_parts(rule)
            parts.pop("COUNT", None)
            rule = _rrule_join(head, parts)
        out.append(rule)
    return out


def _is_first(master, event):
    """Is this occurrence the first of its series?"""
    if not event.get("original_start"):
        return False
    a = parse_time(master["start"].get("dateTime") or master["start"]["date"])[0]
    b = parse_time(event["original_start"])[0]
    return a == b


def get_recurrence(event):
    rid = event.get("recurring_id") or event["id"]
    return google(f"/calendars/primary/events/{urllib.parse.quote(rid)}").get("recurrence", [])


def _local(value):
    """A Google start/end/originalStartTime -> local naive datetime, or a date."""
    t, all_day = parse_time(value.get("dateTime") or value["date"])
    return t if all_day else t.replace(tzinfo=None)


def _day(value):
    t = _local(value)
    return t.date() if isinstance(t, dt.datetime) else t


def _original(event):
    """Where an occurrence sits in its series' rule: local naive time, or a date."""
    t = parse_time(event["original_start"])[0]
    return t.replace(tzinfo=None) if isinstance(t, dt.datetime) else t


def _moment(t):
    """A local date or naive datetime as RFC 3339, for timeMin/timeMax."""
    if not isinstance(t, dt.datetime):
        t = dt.datetime.combine(t, dt.time())
    return t.astimezone().isoformat()


def _instances(series_id, first, last=None, deleted=False):
    """Occurrences of a series between two local times (or dates); with no end, an
    endless series is looked at two years past today or past `first`, if later."""
    last = last or max(_as_time(first), dt.datetime.now()) + dt.timedelta(days=730)
    params = {"timeMin": _moment(first), "timeMax": _moment(last), "maxResults": "2500"}
    if deleted:
        params["showDeleted"] = "true"
    items = []
    while True:
        page = google(_path(series_id) + "/instances", params=params)
        items.extend(page.get("items", []))
        if not page.get("nextPageToken"):
            return items
        params["pageToken"] = page["nextPageToken"]


EXCEPTION_FIELDS = ("summary", "description", "location", "colorId")


def _exceptions(master, since=None):
    """The occurrences of a series that differ from its rule - cancelled, moved or
    edited - from the occurrence originally at `since` on. Google forgets them for
    good whenever the series' times or rule change (and when it is cut short), so
    they are noted first and put back afterwards."""
    length = _local(master["end"]) - _local(master["start"])
    first = _local(master["start"]) if since is None else since
    found = []
    for inst in _instances(master["id"], first, deleted=True):
        orig = inst.get("originalStartTime")
        if not orig or _local(orig) < first:
            continue
        ex = {"day": _day(orig)}
        if inst.get("status") == "cancelled":
            ex["cancelled"] = True
        else:
            begin, finish = _local(inst["start"]), _local(inst["end"])
            if begin != _local(orig) or finish - begin != length:
                ex["start"], ex["end"] = inst["start"], inst["end"]
            fields = {f: inst.get(f) for f in EXCEPTION_FIELDS if inst.get(f) != master.get(f)}
            if fields:
                ex["fields"] = fields
            if len(ex) == 1:
                continue                    # an ordinary occurrence
        found.append(ex)
    return found


def _reapply(series_id, exceptions, day_shift=0):
    """Put noted exceptions back onto a series whose occurrences moved by
    `day_shift` days. A moved lesson keeps the time it was moved to. Returns how
    many found no occurrence to land on."""
    if not exceptions:
        return 0
    days = [ex["day"] + dt.timedelta(days=day_shift) for ex in exceptions]
    by_day = {}
    for inst in _instances(series_id, min(days) - dt.timedelta(days=1), max(days) + dt.timedelta(days=2)):
        if inst.get("originalStartTime"):
            by_day.setdefault(_day(inst["originalStartTime"]), inst)
    missed = 0
    for ex, day in zip(exceptions, days):
        inst = by_day.get(day)
        if inst is None:
            missed += not ex.get("cancelled")  # a cancelled one with nothing there is done
            continue
        if ex.get("cancelled"):
            google(_path(inst["id"]), "DELETE")
            continue
        body = dict(ex.get("fields", {}))
        if "start" in ex:
            body["start"], body["end"] = _restore_time(ex["start"]), _restore_time(ex["end"])
        google(_path(inst["id"]), "PATCH", body)
    return missed


# Everything a new series carries over from the one it continues: guests,
# reminders, colour, the Zoom/Meet data in extendedProperties and conferenceData.
COPIED = ("summary", "description", "location", "colorId", "transparency", "visibility", "attendees",
          "guestsCanInviteOthers", "guestsCanModify", "guestsCanSeeOtherGuests", "anyoneCanAddSelf",
          "reminders", "extendedProperties", "source", "conferenceData", "attachments")


def _insert_copy(body):
    params = {"supportsAttachments": "true"}
    if "conferenceData" in body:
        params["conferenceDataVersion"] = "1"
    try:
        return google("/calendars/primary/events", "POST", body, params=params)
    except ApiError as e:
        if "conferenceData" not in body or not str(e).startswith("400"):
            raise
        body = {k: v for k, v in body.items() if k != "conferenceData"}   # a conference that cannot be copied
        return google("/calendars/primary/events", "POST", body, params={"supportsAttachments": "true"})


def _as_time(t):
    return t if isinstance(t, dt.datetime) else dt.datetime.combine(t, dt.time())


def _until_for(until, all_day, delta):
    """An UNTIL for a series that moved by `delta`: later by as much (a series moved
    later must not lose its last occurrence) and of the series' own kind - a date
    for all-day events, a UTC time for timed ones."""
    if "T" in until:
        t = dt.datetime.strptime(until, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
    else:
        t = dt.datetime.combine(dt.datetime.strptime(until, "%Y%m%d").date(), dt.time(23, 59, 59)).astimezone()
    t += max(delta, dt.timedelta(0))
    if all_day:
        return t.astimezone().strftime("%Y%m%d")
    return t.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def change_occurrence(event, scope, summary=None, start=None, end=None, description=None, recurrence=None):
    """Edit or move one occurrence of a recurring event with the chosen scope."""
    if recurrence is not None and event.get("recurring_id") and scope == "this":
        raise ValueError("Repeat changes apply to this and following events or all events")
    if scope == "this" or not event.get("recurring_id"):
        return update_event(event["id"], summary, start, end, description, recurrence)
    rid = event["recurring_id"]
    path = _path(rid)
    master = google(path)
    rules = master.get("recurrence", [])
    first = _is_first(master, event)
    # the change, expressed as a shift of the occurrence
    shift = (start - event["start"].replace(tzinfo=None)) if isinstance(start, dt.datetime) and not event["all_day"] else None
    length = (end - start) if start is not None else None
    if scope == "all" or first:
        body = {}
        if summary is not None:
            body["summary"] = summary
        if description is not None:
            body["description"] = description
        if shift:
            ms = parse_time(master["start"].get("dateTime") or master["start"]["date"])[0]
            new_start = ms.replace(tzinfo=None) + shift
            body["start"], body["end"] = _patch_times(new_start, new_start + length)
            body["recurrence"] = _shift_weekdays(rules, (new_start.date() - ms.date()).days)
        elif isinstance(start, dt.date) and not isinstance(start, dt.datetime):
            master_start = parse_time(master["start"].get("dateTime") or master["start"]["date"])[0]
            master_day = master_start.date() if isinstance(master_start, dt.datetime) else master_start
            event_day = event["start"].date() if isinstance(event["start"], dt.datetime) else event["start"]
            moved = master_day + (start - event_day)
            body["start"], body["end"] = _patch_times(moved, moved + length)
            body["recurrence"] = _shift_weekdays(rules, (moved - master_day).days)
        elif isinstance(start, dt.datetime) and event["all_day"]:
            master_day = parse_time(master["start"]["date"])[0]
            moved_day = master_day + (start.date() - event["start"])
            moved = dt.datetime.combine(moved_day, start.time())
            body["start"], body["end"] = _patch_times(moved, moved + length)
            body["recurrence"] = _shift_weekdays(rules, (moved_day - master_day).days)
        elif start is not None and length is not None:
            body["end"] = {"dateTime": _iso(parse_time(master["start"]["dateTime"])[0].replace(tzinfo=None)
                                             + length), "timeZone": TZ, "date": None}
        if recurrence is not None:
            body["recurrence"] = recurrence
        # a new time or rule makes Google drop every exception of the series
        kept = _exceptions(master) if {"start", "end", "recurrence"} & set(body) else []
        updated = google(path, "PATCH", body)
        change = Change(f"edited “{master.get('summary', '')}”", updated)
        if kept:
            missed = _reapply(rid, kept, (_day(updated["start"]) - _day(master["start"])).days)
            if missed:
                change.warning = f"{missed} changed occurrence(s) found no place in the new series"
            change.inverse("REAPPLY", rid, kept)
            updated = google(path)          # changed occurrences move the series' etag
        change.inverse("PATCH", rid, _inverse_body(master, body), updated.get("etag"))
        return change
    # "following": cut the old series, start a new one here
    since = _original(event)
    kept = _exceptions(master, since)
    s0 = start if start is not None else (event["start"] if event["all_day"]
                                         else event["start"].replace(tzinfo=None))
    e0 = end if end is not None else (event["end"] if event["all_day"]
                                     else event["end"].replace(tzinfo=None))
    all_day = not isinstance(s0, dt.datetime)
    delta = _as_time(s0) - _as_time(since)
    end_of_series = _series_end(rid, rules)
    new_rules = (_until(rules, _until_for(end_of_series, all_day, delta)) if end_of_series
                 else _without_count(rules))
    old_day = since.date() if isinstance(since, dt.datetime) else since
    new_day = s0.date() if isinstance(s0, dt.datetime) else s0
    new_rules = _shift_weekdays(new_rules, (new_day - old_day).days)
    event_start, event_end = _event_times(s0, e0)
    body = {k: master[k] for k in COPIED if k in master}
    body.update(start=event_start, end=event_end, recurrence=new_rules if recurrence is None else recurrence)
    if summary is not None:
        body["summary"] = summary
    if description is not None:
        body["description"] = description
    # Create first: an API failure must not silently delete the later occurrences.
    created = _insert_copy(body)
    try:
        missed = _reapply(created["id"], kept, (new_day - old_day).days)
        trimmed = google(path, "PATCH", {"recurrence": _until(rules, _until_before(event["original_start"]))})
    except Exception:
        try:
            google(_path(created["id"]), "DELETE")
        except Exception as cleanup_error:
            raise ApiError("Series update failed; a duplicate series may remain: " + created["id"]) from cleanup_error
        raise
    change = Change(f"changed “{master.get('summary', '')}” from {_short(old_day)}", created)
    if missed:
        change.warning = f"{missed} changed occurrence(s) found no place in the new series"
    change.inverse("REAPPLY", rid, kept)
    change.inverse("PATCH", rid, {"recurrence": rules}, trimmed.get("etag"))
    change.inverse("DELETE", created["id"], None, google(_path(created["id"])).get("etag"))
    return change


def delete_occurrence(event, scope):
    if scope == "this" or not event.get("recurring_id"):
        return delete_event(event["id"])
    rid = event["recurring_id"]
    path = _path(rid)
    master = google(path)
    if scope == "all" or _is_first(master, event):
        return delete_event(rid)
    rules = master.get("recurrence", [])
    since = _original(event)
    kept = _exceptions(master, since)       # cut off with the series; noted for an undo
    trimmed = google(path, "PATCH", {"recurrence": _until(rules, _until_before(event["original_start"]))})
    day = since.date() if isinstance(since, dt.datetime) else since
    change = Change(f"deleted “{master.get('summary', '')}” from {_short(day)}")
    change.inverse("REAPPLY", rid, kept)
    change.inverse("PATCH", rid, {"recurrence": rules}, trimmed.get("etag"))
    return change
