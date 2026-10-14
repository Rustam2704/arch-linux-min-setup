"""The panel image contract: fixed canvases and the requested fill direction."""
import sys
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop/share/sky-desktop"))
from sky_theme import THEME  # noqa: E402
from sysicons import level, outlines, svg  # noqa: E402


class SysiconsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.glyphs = outlines()

    def test_segment_boundaries(self):
        self.assertEqual([level(p) for p in (0, 1, 25, 26, 50, 51, 75, 76, 100)],
                         [1, 1, 1, 2, 2, 3, 3, 4, 4])

    def test_canvas_and_colours_do_not_move(self):
        ns = {"s": "http://www.w3.org/2000/svg"}
        palette = [THEME[key] for key in ("light", "success", "warning", "danger")]
        for name in ("cpu", "memory", "swap"):
            with self.subTest(name=name):
                roots = [ET.fromstring(svg(name, count * 25, self.glyphs))
                         for count in range(1, 5)]
                self.assertEqual(len({(r.get("width"), r.get("height"), r.get("viewBox"))
                                      for r in roots}), 1)
                for count, root in enumerate(roots, 1):
                    self.assertIsNotNone(root.find(".//s:clipPath/s:path", ns))
                    rects = root.findall(".//s:g/s:rect", ns)
                    self.assertEqual(len(rects), 4)
                    self.assertEqual([r.get("fill") for r in rects],
                                     palette[:count] + [THEME["muted"]] * (4 - count))
                    coord = "x" if name == "memory" else "y"
                    positions = [float(r.get(coord)) for r in rects]
                    self.assertEqual(positions, sorted(positions, reverse=name != "memory"))


if __name__ == "__main__":
    unittest.main()
