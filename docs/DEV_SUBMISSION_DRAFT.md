---
title: "Phantom Trace: an offline AI that finds the ghosts in your CI/CD logs"
published: false
tags: devchallenge, hf26challenge, opensource, ai
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 4: Ghost in the Machine](https://dev.to/challenges/hacktoberfest-week4-2026-10-26).*

## What I Built

Some failures never really leave a pipeline. They disappear for a week, return
under different wording, and make the next incident look new.

**Phantom Trace** is an offline incident-archaeology tool that finds those
recurring ghosts. You paste timestamped CI/CD events, and a local open-weight
embedding model groups failures that mean the same thing even when they share
few exact words. It then shows every source line behind the cluster.

The included fictional sample contains three incident families:

- an expired TLS certificate affecting three deployment paths;
- disk exhaustion reported three different ways; and
- a missing deployment secret observed by two services.

One accessibility failure remains isolated. That distinction matters: the app
is meant to reveal recurrence, not force every event into a pattern.

My interpretation of **Ghost in the Machine** is practical rather than
supernatural. The ghosts are old operational failures still haunting a delivery
system. The machine can surface them, but it should not pretend to know more
than its evidence.

## Demo

<!-- Replace this line with the uploaded demo image or GIF before publishing. -->

`TODO(PUBLICATION): replace with the uploaded demo image or GIF.`

In the verified sample run, Phantom Trace analyzes nine fictional events and
returns three recurring patterns plus one isolated event. Expanding a result
reveals its timestamps, sources, and original log messages.

To run it locally:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe setup_model.py
.\Start-PhantomTrace.ps1
```

Then open `http://127.0.0.1:8766`.

Model setup needs the internet once. Analysis itself does not.

## Code

<!-- Replace with the public repository URL after publication approval. -->

`TODO(PUBLICATION): replace with the approved public GitHub repository URL.`

The project is intentionally small enough to audit:

- `app.py` contains parsing, local inference, clustering, scoring, and the HTTP
  server;
- `static/` contains the accessible browser interface;
- `setup_model.py` downloads a pinned model revision;
- `tests/` exercises parsing, clustering, defaults, deterministic scoring, and
  failure cases; and
- `THIRD_PARTY_NOTICES.md` records the model and prior-work attribution.

## How I Built It

### 1. Turn each message into a local semantic vector

Phantom Trace uses
[`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
through ONNX Runtime. The tokenizer truncates messages to 256 tokens. The
server performs attention-mask-aware mean pooling and L2 normalization, so
cosine similarity becomes a dot product between unit vectors.

That open-weight model is the functional core. A keyword search for `disk
full` would miss `no space left on device while extracting image layers`.
Their embeddings can still land close enough to connect them.

### 2. Build an evidence graph, not an invented diagnosis

Each event is a node. A pair becomes connected when its cosine similarity meets
the selected threshold. Connected components become incident clusters.

For the title, Phantom Trace chooses the medoid: the real event whose vector is
most central to the cluster. It does **not** ask a language model to generate a
root cause. Every displayed claim can be traced to an input line.

The haunting score is also deliberately ordinary. It combines recurrence,
source breadth, and recency. It is a prioritization heuristic, not an AI
confidence score.

### 3. Calibrate with a real model run

My first default threshold was `0.72`. The UI looked polished, but a real model
integration run exposed a problem: it found only one of the three intended
recurring families.

I tested the same nine-event fixture across several thresholds. At `0.55`, the
model produced the intended `3, 3, 2, 1` cluster sizes: three recurring groups
and one isolated event. I changed the default, documented why, and added a
regression test for the setting.

The slider remains available because one threshold cannot fit every log corpus.
Teams can raise it when they prefer fewer, tighter matches.

### 4. Keep the boundary small and inspectable

The local server accepts only 2–200 non-empty events in this format:

```text
ISO timestamp | source | message
```

It bounds source and message lengths, rejects malformed input, listens on
`127.0.0.1`, and makes no analytics or inference API calls. Users should still
redact secrets before pasting logs; local processing is not an excuse to put
credentials into diagnostic tools.

### Validation

I ran:

- 6 unit tests: all passed;
- JavaScript syntax validation: passed;
- a real local MiniLM integration run: 9 events, 3 recurring clusters, sizes
  `3, 3, 2, 1`; and
- an end-to-end browser run in Microsoft Edge, including expansion of the
  original evidence lines.

## Why Does Open Innovation Matter?

Operational logs can contain customer names, internal hostnames, repository
paths, incident details, and secrets that should have been redacted but were
not. Shipping all of that to a closed embedding endpoint just to compare two
sentences is a poor default.

An open-weight model changes the trust boundary:

- the log text stays on the operator's machine;
- inference still works after the model is downloaded and the network is off;
- there is no per-event API charge or quota;
- the exact model revision is pinned and replaceable; and
- the pooling, similarity, grouping, and scoring logic are all inspectable.

Open also makes limitations easier to discuss honestly. Semantic similarity is
not root-cause analysis. A connected cluster can be wrong, and a real recurring
incident can be missed. Phantom Trace keeps the original evidence visible so a
human can challenge the grouping instead of trusting an opaque diagnosis.

For this project, open innovation is not a licensing footnote. It is what makes
private, offline incident archaeology possible.

## The Spirit of It

The moment the project landed was not an animation or a jump scare. It was the
first real-model run after calibration: three differently worded failure
families emerged from nine lines, while an unrelated accessibility failure
stayed alone.

That is the kind of ghost I wanted to catch—an old failure returning in a new
sentence, with enough evidence left behind for someone to finally recognize it.

## AI Assistance Disclosure

I used OpenAI Codex to help implement, test, review, and draft documentation for
this project. I reviewed the resulting code and prose, ran the stated tests and
real-model checks locally, and corrected the similarity default after the
integration result contradicted the initial assumption. The sample data is
fictional. No private production logs were used.

