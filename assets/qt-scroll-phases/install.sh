#!/bin/bash
# Run from any directory. All persistent system changes go through setup/lab.
set -euo pipefail
src=$(cd -- "$(dirname -- "$0")" && pwd)
setup=$(cd "$src/../.." && pwd)
lab="$setup/lab/lab"
experiment=27-native-two-finger-swipe
cmake -S "$src" -B "$src/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$src/build" -j2
ctest --test-dir "$src/build" --output-on-failure
plugin=/usr/lib/qt6/plugins/generic/libqscrollphases.so
rule=/etc/udev/rules.d/70-qt-scroll-phases.rules
if ! cmp -s "$src/build/generic/libqscrollphases.so" "$plugin"; then
    # Never truncate a shared object mapped by a running application.
    "$lab" write "$experiment" "$plugin.new" < "$src/build/generic/libqscrollphases.so"
    sudo chmod 644 "$plugin.new"
    if [ -e "$plugin" ]; then
        backup=$(mktemp "$setup/lab/backups/qt-scroll-phases.XXXXXX.so")
        cp "$plugin" "$backup"
        printf -v undo 'sudo cp -- %q %q && sudo chmod 644 %q && sudo mv -- %q %q' \
            "$backup" "$plugin.restore" "$plugin.restore" "$plugin.restore" "$plugin"
    else
        printf -v undo 'sudo rm -f -- %q' "$plugin"
    fi
    "$lab" undo "$experiment" "$undo"
    sudo mv -- "$plugin.new" "$plugin"
fi
if ! cmp -s "$src/70-qt-scroll-phases.rules" "$rule"; then
    # Registered before the write, so rollback reloads *after* restoring/removing it.
    "$lab" undo "$experiment" 'sudo udevadm control --reload-rules; sudo udevadm trigger --action=change --subsystem-match=input --property-match=ID_INPUT_TOUCHPAD=1; sudo udevadm settle'
    "$lab" write "$experiment" "$rule" < "$src/70-qt-scroll-phases.rules"
    sudo chmod 644 "$rule"
fi
sudo udevadm control --reload-rules
sudo udevadm trigger --action=change --subsystem-match=input --property-match=ID_INPUT_TOUCHPAD=1
sudo udevadm settle
echo 'Installed. Enable QT_QPA_GENERIC_PLUGINS=scrollphases in the X11 session environment.'
