# Google Calendar as your calendar & meeting scheduler

## What was set up
| Piece | Where |
|---|---|
| App launcher (opens it, or jumps to it if open) | **`Super + C`**, or "Google Calendar" in `Super + D` |
| Separate Firefox profile — no address bar, dark, one process, no telemetry | `~/.local/share/google-calendar/profile/` (`user.js`, `chrome/userChrome.css`) |
| Launcher script | `~/.local/bin/google-calendar` |
| Menu entry | `~/.local/share/applications/google-calendar.desktop` |
| Always fully opaque (picom) | `"100:class_g = 'GoogleCalendar'"` |

It runs independently of your normal Firefox (`--no-remote`, own profile). Closing the window quits it.
The tab strip stays hidden and only appears if a second tab opens (e.g. a Zoom join page) — close that tab with `Ctrl+W`.
Memory: ~470 MB before sign-in, one process (per-site process isolation is off in this profile). Zoom's own Calendar tab stays disabled, saving ~1.8 GB.

---

## One-time setup (≈5 minutes)
1. **Open it:** `Super + C` → **Sign in** → your Google account.
2. **Dark theme:** gear icon (top right) → **Appearance** → **Device default** (follows the system dark setting) or **Dark**.
3. **Keyboard shortcuts:** gear → **Settings** → **General → Keyboard shortcuts** → enable.
4. **Zoom add-on:**
   - Right side panel of Calendar (if hidden, click the small arrow at the bottom right) → **+ Get add-ons**.
   - Search **"Zoom for Google Workspace"** → **Install** → allow the Google permissions.
   - Click the Zoom icon in the side panel → **Sign in** with your Zoom account → authorize.
5. **Default video call (optional):** Settings → **Event settings** → pick whether new events get Google Meet or Zoom automatically.
6. **Reminders on this laptop:** Settings → **Notification settings** → desktop notifications; when Firefox asks, **Allow**.
   Reminders only fire while the calendar window is open.
7. **First "Join Zoom Meeting" click:** Firefox asks how to open the link → choose **Zoom**, tick **Always allow**.

---

## Everyday use

### Create a meeting
- Press **`C`**, or **click-drag** on the time grid over the slot you want.
- In the quick box: title → **More options** for the full editor.
- **Video call:** only in the **full editor** (More options): the **"Add Google Meet video conferencing"** button has a small **▾ arrow** beside it → **Zoom Meeting**. The quick box you get from clicking a date only offers Meet.
- **Guests:** type emails in the Guests panel.
- **Save** → **Send** invitations.

### Make it recurring
Full editor → the **"Does not repeat"** dropdown → *Daily / Weekly on … / Monthly … / Every weekday* or **Custom** (every N days/weeks, specific weekdays, end on a date or after N times).
A recurring Zoom series gets **one Zoom link** for all occurrences.

### Move or change a meeting
- **Move:** drag the event to another time or day.
- **Change length:** drag its bottom edge.
- **Edit details:** click the event → pencil icon.
- **Recurring event:** Calendar asks **This event / This and following / All events** → choose → then **Send** update emails.
- **Delete:** click → trash icon (same three choices for recurring).

### Join
Click the event → **Join Zoom Meeting** (opens the Zoom app) or **Join with Google Meet** (opens in the calendar window).
After a Zoom meeting, **quit Zoom from its tray icon** — closing the window leaves it running.

### Keys (after enabling shortcuts)
| Key | Action | Key | Action |
|---|---|---|---|
| `C` | create event | `T` | jump to today |
| `D` `W` `M` | day / week / month view | `J` `K` | next / previous period |
| `X` | 4-day view | `A` | schedule (list) view |
| `/` | search | `E` | edit selected event |
| `?` | all shortcuts | `Esc` | close popup |

---

## Sync rules — read once
- **Google Calendar is the master.** Changing a meeting's **title, date, time or time zone** in Calendar updates the Zoom meeting automatically.
- **Don't edit or delete these meetings inside the Zoom app** — changes made there are not guaranteed to flow back to Google, so the two can drift apart.
- Zoom meeting options (waiting room, mute on entry, etc.) are set from the Zoom add-on panel while the event is open, or in the Zoom web settings.
- Google Meet links are native to Google Calendar — nothing to install.

---

## Troubleshooting: Zoom missing from the video-call list
0. **What actually fixed it here (2026-09-17):** the add-on was installed and signed in, but Calendar only loads its list of video-call providers when the page loads. **Reload Calendar with `F5`** after installing or signing in to an add-on — the button then changes from "Add Google Meet video conferencing" to **"Add video conferencing ▾"**, with **Zoom Meeting** under *Add-ons*.
1. Use the full editor (More options) and the **▾ arrow**, not the quick box.
2. Side panel → Zoom icon: if it says **Sign in**, the sign-in didn't complete. The calendar profile allows popups (`dom.disable_open_during_load=false`) because Zoom's sign-in uses one — restart the calendar app (close the window, `Super+C`) after changing profile settings.
3. After signing in, reload Calendar (`F5`) so the conferencing list refreshes.

## Undo / remove
```bash
rm -rf ~/.local/share/google-calendar ~/.local/bin/google-calendar ~/.local/share/applications/google-calendar.desktop
# and delete the "$mod+c" line from ~/.config/i3/config and the GoogleCalendar line from ~/.config/picom/picom.conf
```
