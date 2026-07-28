import json, os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PILOTS = ["001", "002", "006", "008", "016", "019", "021", "022"]


class TestSceneParsing(unittest.TestCase):
    SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 300">'
           '<rect x="1" y="2"/></svg>')

    def test_scene_height_read_from_viewbox(self):
        self.assertEqual(build.scene_height(self.SVG), 300)

    def test_scene_inner_strips_outer_svg_tags(self):
        self.assertEqual(build.scene_inner(self.SVG), '<rect x="1" y="2"/>')

    def test_wrap_scene_adds_header_height(self):
        card = {"id": "002", "title": "폭포수 모형"}
        out = build.wrap_scene(card, self.SVG)
        self.assertIn(f'viewBox="0 0 720 {300 + build.HEADER_H}"', out)

    def test_wrap_scene_translates_body_below_header(self):
        card = {"id": "002", "title": "폭포수 모형"}
        out = build.wrap_scene(card, self.SVG)
        self.assertIn(f'<g transform="translate(0,{build.HEADER_H})">', out)

    def test_wrap_scene_draws_id_and_title(self):
        card = {"id": "002", "title": "폭포수 모형"}
        out = build.wrap_scene(card, self.SVG)
        self.assertIn(">002<", out)
        self.assertIn("폭포수 모형", out)

    def test_wrap_scene_escapes_xml_special_chars_in_title(self):
        card = {"id": "017", "title": "겹화살괄호(<< >>)"}
        out = build.wrap_scene(card, self.SVG)
        self.assertIn("&lt;&lt; &gt;&gt;", out)
        self.assertNotIn("(<< >>)", out)


class TestPilotScenes(unittest.TestCase):
    def test_pilot_scene_files_exist(self):
        for cid in PILOTS:
            path = os.path.join(ROOT, "scenes", f"{cid}.svg")
            self.assertTrue(os.path.exists(path), f"missing {path}")

    def test_every_pilot_scene_declares_width_720(self):
        for cid in PILOTS:
            svg = open(os.path.join(ROOT, "scenes", f"{cid}.svg"), encoding="utf-8").read()
            self.assertRegex(svg, r'viewBox="0 0 720 \d+"', f"{cid} has a bad viewBox")

    def test_no_scene_draws_its_own_header(self):
        # The header is build.py's job. A scene drawing #0b8ad4 at y=14 is
        # duplicating it and will double up in the output.
        for cid in PILOTS:
            svg = open(os.path.join(ROOT, "scenes", f"{cid}.svg"), encoding="utf-8").read()
            self.assertNotIn('y="14" width="72" height="46"', svg,
                             f"{cid} draws its own number badge")

    def test_scenes_use_only_the_approved_palette(self):
        allowed = {"#0b8ad4", "#0a3d5c", "#e8f4fc", "#d3d5d8", "#4a5560",
                   "#eef1f4", "#9aa4ae", "#e03131", "#fff3d6", "#e8b33a",
                   "#1a1a1a", "#fff", "#ffffff"}
        for cid in PILOTS:
            svg = open(os.path.join(ROOT, "scenes", f"{cid}.svg"), encoding="utf-8").read()
            for hexcode in re.findall(r"#[0-9a-fA-F]{3,6}", svg):
                self.assertIn(hexcode.lower(), allowed, f"{cid} uses {hexcode}")


class TestBuild(unittest.TestCase):
    def test_build_emits_self_contained_html(self):
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        html = build.build(cards, 1)
        self.assertNotIn("<script src", html)
        self.assertNotIn("<link ", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)

    def test_build_includes_every_pilot_card_title(self):
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        html = build.build(cards, 1)
        by_id = {c["id"]: c for c in cards}
        for cid in PILOTS:
            self.assertIn(by_id[cid]["title"], html)


if __name__ == "__main__":
    unittest.main()
