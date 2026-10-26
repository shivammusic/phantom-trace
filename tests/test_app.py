import json
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import App, Event, analyze, parse_events  # noqa: E402


class FakeEmbedder:
    def embed(self, texts):
        mapping = {
            "certificate expired": [1.0, 0.0, 0.0],
            "x509 expiry": [0.99, 0.05, 0.0],
            "disk full": [0.0, 1.0, 0.0],
        }
        return np.asarray([mapping[text] for text in texts], dtype=np.float32)


class PhantomTraceTests(unittest.TestCase):
    def test_parse_events_accepts_iso_source_message(self):
        events = parse_events("2026-10-01T00:00:00Z | build | disk full\n2026-10-02T00:00:00Z | deploy | x509 expiry")
        self.assertEqual([event.source for event in events], ["build", "deploy"])

    def test_parse_events_rejects_unstructured_and_unbounded_input(self):
        for value in ("one line", "bad\ninput"):
            with self.assertRaises(ValueError):
                parse_events(value)

    def test_semantic_neighbors_form_recurring_ghost(self):
        payload = {
            "logs": "2026-10-01T00:00:00Z | a | certificate expired\n2026-10-02T00:00:00Z | b | x509 expiry\n2026-10-03T00:00:00Z | c | disk full",
            "threshold": 0.8,
        }
        result = App(FakeEmbedder()).run(payload)
        self.assertEqual(result["recurring_ghosts"], 1)
        self.assertEqual(result["clusters"][0]["event_count"], 2)
        self.assertEqual(result["clusters"][0]["sources"], ["a", "b"])

    def test_default_similarity_matches_documented_demo_setting(self):
        payload = {
            "logs": "2026-10-01T00:00:00Z | a | certificate expired\n2026-10-02T00:00:00Z | b | x509 expiry\n2026-10-03T00:00:00Z | c | disk full",
        }
        result = App(FakeEmbedder()).run(payload)
        self.assertEqual(result["threshold"], 0.55)
        self.assertEqual(result["recurring_ghosts"], 1)

    def test_gate_score_is_deterministic_and_bounded(self):
        events = [
            Event("2026-10-01T00:00:00Z", "a", "one", 1),
            Event("2026-10-02T00:00:00Z", "b", "two", 86401),
        ]
        first = analyze(events, np.asarray([[1, 0], [.99, .01]], dtype=float), .8)
        second = analyze(events, np.asarray([[1, 0], [.99, .01]], dtype=float), .8)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertLessEqual(first["clusters"][0]["haunting_score"], 100)

    def test_invalid_similarity_and_embedding_shape_fail_closed(self):
        events = [Event("a", "a", "a", 1), Event("b", "b", "b", 2)]
        with self.assertRaises(ValueError):
            analyze(events, np.ones((1, 3)), .7)
        with self.assertRaises(ValueError):
            analyze(events, np.ones((2, 3)), .2)


if __name__ == "__main__":
    unittest.main()
