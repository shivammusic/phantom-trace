"""Phantom Trace: offline semantic incident archaeology for CI/CD logs."""
from __future__ import annotations

import argparse
import json
import math
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Protocol

import numpy as np

ROOT = Path(__file__).resolve().parent
MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
LINE_RE = re.compile(r"^\s*(?P<time>[^|]+?)\s*\|\s*(?P<source>[^|]+?)\s*\|\s*(?P<message>.+?)\s*$")
SAMPLE_LOGS = """2026-10-01T09:04:12Z | deploy-api | TLS certificate expired while contacting artifact registry
2026-10-03T14:18:42Z | deploy-worker | artifact registry rejected connection because the certificate expired
2026-10-08T07:51:03Z | release-web | x509 certificate has expired for registry.internal
2026-10-10T16:20:19Z | build-api | no space left on device while extracting image layers
2026-10-12T11:02:07Z | build-worker | container image extraction failed: disk is full
2026-10-18T18:44:53Z | release-api | runner ran out of disk space while unpacking the image
2026-10-21T13:36:20Z | deploy-web | required secret DATABASE_URL was not available
2026-10-22T08:13:09Z | deploy-api | deployment stopped because DATABASE_URL is missing
2026-10-24T20:01:33Z | test-web | accessibility suite found a missing form label"""


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray: ...


@dataclass(frozen=True)
class Event:
    timestamp: str
    source: str
    message: str
    epoch: float


def parse_events(text: str) -> list[Event]:
    if not isinstance(text, str):
        raise ValueError("Logs must be text.")
    lines = [line for line in text.splitlines() if line.strip()]
    if not 2 <= len(lines) <= 200:
        raise ValueError("Provide 2 to 200 non-empty log lines.")
    events: list[Event] = []
    for number, line in enumerate(lines, 1):
        match = LINE_RE.match(line)
        if not match:
            raise ValueError(f"Line {number} must use: ISO timestamp | source | message")
        raw_time = match.group("time").strip()
        try:
            parsed = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            epoch = parsed.timestamp()
        except ValueError as exc:
            raise ValueError(f"Line {number} has an invalid ISO timestamp.") from exc
        source, message = match.group("source").strip(), match.group("message").strip()
        if len(source) > 80 or len(message) > 1000:
            raise ValueError(f"Line {number} exceeds the source or message limit.")
        events.append(Event(raw_time, source, message, epoch))
    return events


def _components(similarities: np.ndarray, threshold: float) -> list[list[int]]:
    remaining = set(range(len(similarities)))
    groups: list[list[int]] = []
    while remaining:
        stack, group = [remaining.pop()], []
        while stack:
            current = stack.pop()
            group.append(current)
            neighbors = {i for i in remaining if similarities[current, i] >= threshold}
            remaining.difference_update(neighbors)
            stack.extend(neighbors)
        groups.append(sorted(group))
    return groups


def analyze(events: list[Event], vectors: np.ndarray, threshold: float) -> dict:
    if vectors.shape[0] != len(events) or vectors.ndim != 2:
        raise ValueError("Embedding output does not match the event count.")
    if not math.isfinite(threshold) or not 0.55 <= threshold <= 0.95:
        raise ValueError("Similarity must be between 0.55 and 0.95.")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    normalized = vectors / np.maximum(norms, 1e-9)
    similarities = np.clip(normalized @ normalized.T, -1, 1)
    groups = _components(similarities, threshold)
    latest = max(event.epoch for event in events)
    clusters = []
    for group in groups:
        local = similarities[np.ix_(group, group)]
        medoid = group[int(np.argmax(local.mean(axis=1)))]
        members = sorted((events[index] for index in group), key=lambda item: item.epoch)
        sources = sorted({item.source for item in members})
        recurrence = len(group)
        age_days = max(0.0, (latest - members[-1].epoch) / 86400)
        freshness = max(0.25, 1 / (1 + age_days / 7))
        score = round(min(100, recurrence * 18 + len(sources) * 9 + freshness * 28))
        clusters.append({
            "id": f"ghost-{medoid + 1}",
            "title": events[medoid].message,
            "status": "recurring" if recurrence > 1 else "isolated",
            "haunting_score": score,
            "event_count": recurrence,
            "sources": sources,
            "first_seen": members[0].timestamp,
            "last_seen": members[-1].timestamp,
            "evidence": [item.__dict__ | {"epoch": None} for item in members],
            "centroid": normalized[group].mean(axis=0).tolist(),
        })
    clusters.sort(key=lambda item: (-item["haunting_score"], -item["event_count"], item["title"]))
    for item in clusters:
        item.pop("centroid")
        for evidence in item["evidence"]:
            evidence.pop("epoch", None)
    return {
        "schema": "phantom-trace/1",
        "model": MODEL_ID,
        "privacy": "Inference completed locally; no log text left this process.",
        "threshold": threshold,
        "event_count": len(events),
        "recurring_ghosts": sum(item["status"] == "recurring" for item in clusters),
        "clusters": clusters,
    }


class MiniLMEmbedder:
    def __init__(self, model_dir: Path = ROOT / "models") -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=256)
        self.tokenizer.enable_padding()
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(
            str(model_dir / "model.onnx"), sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self.lock = threading.Lock()

    def embed(self, texts: list[str]) -> np.ndarray:
        rows: list[np.ndarray] = []
        with self.lock:
            for start in range(0, len(texts), 16):
                batch = self.tokenizer.encode_batch(texts[start:start + 16])
                ids = np.asarray([item.ids for item in batch], dtype=np.int64)
                masks = np.asarray([item.attention_mask for item in batch], dtype=np.int64)
                feeds = {
                    "input_ids": ids,
                    "attention_mask": masks,
                    "token_type_ids": np.asarray([item.type_ids for item in batch], dtype=np.int64),
                }
                hidden = self.session.run(None, feeds)[0]
                expanded = masks[..., None].astype(np.float32)
                pooled = (hidden * expanded).sum(axis=1) / np.maximum(expanded.sum(axis=1), 1e-9)
                pooled /= np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9)
                rows.extend(pooled)
        return np.asarray(rows)


class App:
    def __init__(self, embedder: Embedder) -> None:
        self.embedder = embedder

    def run(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        events = parse_events(payload.get("logs"))
        threshold = payload.get("threshold", 0.55)
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
            raise ValueError("Similarity must be a number.")
        vectors = self.embedder.embed([event.message for event in events])
        return analyze(events, vectors, float(threshold))


def handler_factory(app: App):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, status: int, body: dict) -> None:
            encoded = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/api/analyze":
                self._json(404, {"error": "Not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 300_000:
                    raise ValueError("Request is too large.")
                payload = json.loads(self.rfile.read(length))
                self._json(200, app.run(payload))
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc)})

        def do_GET(self) -> None:  # noqa: N802
            path = "/index.html" if self.path == "/" else self.path
            target = (ROOT / "static" / path.lstrip("/")).resolve()
            static = (ROOT / "static").resolve()
            if static not in target.parents or not target.is_file():
                self._json(404, {"error": "Not found"})
                return
            content = target.read_bytes()
            content_type = {".html": "text/html", ".css": "text/css", ".js": "text/javascript"}.get(target.suffix, "application/octet-stream")
            self.send_response(200)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, _format: str, *_args) -> None:
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8766, type=int)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), handler_factory(App(MiniLMEmbedder())))
    print(f"Phantom Trace is listening at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
