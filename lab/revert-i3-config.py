#!/usr/bin/env python3
"""Undo the lab's edits to ~/.config/i3/config (OSD on media keys, focus_on_window_activation)."""
p = '/home/fanatic/.config/i3/config'
s = open(p).read()
s = s.replace(' && ~/.local/bin/osd vol', '').replace(' && ~/.local/bin/osd brightness', '')
s = s.replace('''# Clicking a window in the taskbar (or any app asking for focus) switches to it,
# instead of i3's default of only marking it urgent when it sits on another workspace.
focus_on_window_activation focus

''', '')
s = s.replace('bindsym $mod+c exec --no-startup-id ~/.local/bin/mini-calendar',
              'bindsym $mod+c exec --no-startup-id ~/.local/bin/google-calendar')
open(p, 'w').write(s)
print('i3 config reverted')
