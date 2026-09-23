"""The modifier chords of osd-daemon (Alt+Shift, Ctrl+Shift), as key sequences.
The class is lifted out of the script by its source so no display is needed."""
import ast
from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[1] / "desktop/bin/osd-daemon"
tree = ast.parse(SRC.read_text())
ns = {}
exec(compile(ast.Module([n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Chords"], []),
             str(SRC), "exec"), ns)
Chords = ns["Chords"]

ALT, SHIFT, CTRL, A, B = 64, 50, 37, 38, 56
CATS = {ALT: "alt", SHIFT: "shift", CTRL: "ctrl"}


def play(chords, *steps):
    """'+kc' press, '-kc' release, 'btn' click; returns the chords that fired."""
    fired = []
    for step in steps:
        if step == "btn":
            chords.button()
        elif step[0] == "+":
            chords.press(step[1])
        else:
            combo = chords.release(step[1])
            if combo:
                fired.append(combo)
    return fired


class ChordTest(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(play(Chords(CATS), ("+", ALT), ("+", SHIFT), ("-", SHIFT), ("-", ALT)), ["alt_shift"])

    def test_either_order_and_either_release(self):
        self.assertEqual(play(Chords(CATS), ("+", SHIFT), ("+", ALT), ("-", ALT), ("-", SHIFT)), ["alt_shift"])
        self.assertEqual(play(Chords(CATS), ("+", CTRL), ("+", SHIFT), ("-", CTRL), ("-", SHIFT)), ["ctrl_shift"])

    def test_letter_in_between_cancels(self):
        self.assertEqual(play(Chords(CATS), ("+", ALT), ("+", SHIFT), ("+", A), ("-", A), ("-", SHIFT), ("-", ALT)), [])
        self.assertEqual(play(Chords(CATS), ("+", ALT), ("+", SHIFT), "btn", ("-", SHIFT), ("-", ALT)), [])

    def test_letter_still_held_from_typing(self):
        # fast typing overlaps keys: the letter goes up after Alt went down
        self.assertEqual(play(Chords(CATS), ("+", A), ("+", ALT), ("-", A), ("+", SHIFT), ("-", SHIFT), ("-", ALT)),
                         ["alt_shift"])

    def test_letter_before_chord(self):
        self.assertEqual(play(Chords(CATS), ("+", B), ("-", B), ("+", ALT), ("+", SHIFT), ("-", ALT), ("-", SHIFT)),
                         ["alt_shift"])

    def test_three_modifiers_do_not_fire(self):
        self.assertEqual(play(Chords(CATS), ("+", CTRL), ("+", ALT), ("+", SHIFT), ("-", SHIFT), ("-", ALT), ("-", CTRL)), [])

    def test_lost_release_is_forgotten(self):
        # the Ctrl release was never seen (suspend, VT switch): the keymap says it is up
        really = {ALT}
        chords = Chords(CATS, lambda: really)
        chords.press(CTRL)
        self.assertEqual(play(chords, ("+", ALT), ("+", SHIFT), ("-", SHIFT), ("-", ALT)), ["alt_shift"])

    def test_twice_in_a_row(self):
        c = Chords(CATS)
        seq = (("+", ALT), ("+", SHIFT), ("-", SHIFT), ("-", ALT))
        self.assertEqual(play(c, *seq, *seq), ["alt_shift", "alt_shift"])


if __name__ == "__main__":
    unittest.main()
