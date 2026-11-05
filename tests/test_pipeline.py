"""Run: python -m unittest discover tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from promo_finder.candidates import EpisodeScorer, find_promos  # noqa: E402
from promo_finder.llm import _refine, judge_episode, quotes_ok  # noqa: E402
from promo_finder.parse import load_show  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "show"


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.eps = load_show(FIXTURE)
        self.by_num = {e.number: e for e in self.eps}

    def test_parse(self):
        self.assertEqual([e.number for e in self.eps], [1, 2])
        ep = self.eps[0]
        vane = ep.lines[0]
        self.assertEqual((vane.speaker, vane.tones, vane.start), ("LORD VANE", ["cold", "menacing"], 4.5))
        self.assertEqual(ep.duration, 44.0)

    def test_promos_obey_hard_rules(self):
        promos, scorers, _ = find_promos(self.eps)
        self.assertTrue(promos)
        for p in promos:
            self.assertTrue(20 <= p.length <= 60, p.length)
            for seg in p.segments:
                for t in (seg.start, seg.end):
                    self.assertFalse(any(l.start < t - 0.15 and l.end > t + 0.15
                                         for l in self.by_num[seg.episode].lines))

    def test_best_promo_ends_on_cliffhanger(self):
        promos, _, _ = find_promos(self.eps)
        best = max((p for p in promos if p.main.episode == 1), key=lambda p: p.score)
        self.assertEqual(best.main.end, 44.0)            # the dungeon ending, not mid-scene
        self.assertGreaterEqual(best.scores["cliffhanger"], 0.6)

    def test_llm_cannot_invent_timestamps_or_quotes(self):
        promos, scorers, _ = find_promos(self.eps)
        p = next(p for p in promos if p.main.episode == 1)
        sc = scorers[1]
        self.assertIsNone(_refine(p, sc, "E9999", None))      # unknown ID
        self.assertIsNone(_refine(p, sc, "E0", "E3"))          # would be under 20 s
        self.assertTrue(quotes_ok('Opens on "You were told never to come back here"', self.by_num, {1}))
        self.assertFalse(quotes_ok('Opens on "I am your real mother"', self.by_num, {1}))

    def test_mock_llm_judge(self):
        promos, scorers, _ = find_promos(self.eps)
        ep1 = [p for p in promos if p.main.episode == 1]
        judge_episode("mock:test", self.by_num[1], ep1, scorers, self.by_num, log=lambda *_: None)
        self.assertTrue(all(p.judged_by == "mock:test" and "llm_hook" in p.scores for p in ep1))

    def test_cli(self):
        with tempfile.TemporaryDirectory() as out:
            subprocess.run([sys.executable, str(ROOT / "find_promos.py"), str(FIXTURE), "--out", out],
                           check=True, capture_output=True)
            data = json.loads((Path(out) / "promos.json").read_text())
            self.assertTrue(data["promos"])
            self.assertIn("Hard checks", (Path(out) / "quality_report.md").read_text())


if __name__ == "__main__":
    unittest.main()
