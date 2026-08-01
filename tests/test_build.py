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


class TestSupabaseConfig(unittest.TestCase):
    def read(self, cfg):
        import tempfile, unittest.mock
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "supabase.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(cfg, fh)
            with unittest.mock.patch.object(build, "HERE", d):
                return build.read_supabase()

    def test_missing_file_means_offline_only(self):
        import tempfile, unittest.mock
        with tempfile.TemporaryDirectory() as d:
            with unittest.mock.patch.object(build, "HERE", d):
                self.assertIsNone(build.read_supabase())

    def test_plain_project_url_is_kept(self):
        cfg = self.read({"url": "https://abc.supabase.co", "anonKey": "k"})
        self.assertEqual(cfg["url"], "https://abc.supabase.co")

    def test_rest_endpoint_url_is_trimmed_to_the_origin(self):
        # This is what the dashboard's "Data API" panel actually shows.
        for pasted in ("https://abc.supabase.co/rest/v1/",
                       "https://abc.supabase.co/rest/v1",
                       "https://abc.supabase.co/auth/v1/",
                       "  https://abc.supabase.co/  "):
            cfg = self.read({"url": pasted, "anonKey": "k"})
            self.assertEqual(cfg["url"], "https://abc.supabase.co", pasted)

    def test_non_https_url_is_rejected(self):
        with self.assertRaises(SystemExit):
            self.read({"url": "abc.supabase.co", "anonKey": "k"})

    def test_secret_keys_are_refused(self):
        # index.html is public; a secret key there would bypass RLS entirely.
        for bad in ("sb_secret_abc123", "eyJ.service_role.xyz"):
            with self.assertRaises(SystemExit, msg=bad):
                self.read({"url": "https://abc.supabase.co", "anonKey": bad})

    def test_publishable_and_anon_keys_are_accepted(self):
        for ok in ("sb_publishable_abc123", "eyJhbGciOiJIUzI1NiJ9.abc.def"):
            cfg = self.read({"url": "https://abc.supabase.co", "anonKey": ok})
            self.assertEqual(cfg["anonKey"], ok)

    def test_incomplete_config_is_refused(self):
        with self.assertRaises(SystemExit):
            self.read({"url": "https://abc.supabase.co"})


class TestBuild(unittest.TestCase):
    def test_build_emits_self_contained_html(self):
        # The page must load and run with no network. Requests to Supabase are
        # made at runtime by fetch; what is banned is anything the *browser*
        # would have to fetch before the app can start.
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        html = build.build(cards, 1, supa={"url": "https://abc.supabase.co",
                                           "anonKey": "k"})
        self.assertNotIn("<script src", html)
        self.assertNotIn("<link ", html)
        self.assertNotIn("http://", html)
        # The Supabase project origin is the only allowed absolute URL.
        for url in re.findall(r"https://[\w.-]+", html):
            self.assertEqual(url, "https://abc.supabase.co", f"unexpected host {url}")

    def test_build_without_config_disables_the_cloud(self):
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        html = build.build(cards, 1, supa=None)
        self.assertIn("const SUPA = null", html)
        self.assertNotIn("/*__SUPABASE__*/", html)

    def test_build_with_config_inlines_url_and_key(self):
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        html = build.build(cards, 1, supa={"url": "https://abc.supabase.co",
                                           "anonKey": "anon-key-here"})
        self.assertIn("https://abc.supabase.co", html)
        self.assertIn("anon-key-here", html)

    def test_build_inlines_the_sync_module(self):
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        html = build.build(cards, 1)
        self.assertIn("function mergeMarks(", html)
        self.assertIn("gisa-cards-v2", html)
        self.assertNotIn("/*__SYNC__*/", html)

    def test_build_inlines_the_cloud_module(self):
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        html = build.build(cards, 1)
        self.assertIn("function pushProgress(", html)
        self.assertNotIn("/*__CLOUD__*/", html)

    def test_build_strips_the_node_only_module_export(self):
        # The CommonJS tail exists for `node --test`. Leaving it in the browser
        # bundle is harmless but dead; assert we drop it so it cannot rot.
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        html = build.build(cards, 1)
        self.assertNotIn("module.exports", html)

    def test_build_includes_every_pilot_card_title(self):
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        html = build.build(cards, 1)
        by_id = {c["id"]: c for c in cards}
        for cid in PILOTS:
            self.assertIn(by_id[cid]["title"], html)


if __name__ == "__main__":
    unittest.main()
