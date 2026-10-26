# Third-party notices

Phantom Trace uses `sentence-transformers/all-MiniLM-L6-v2`, pinned to revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. The model card identifies the
model as Apache-2.0 licensed. Model files are downloaded separately and are not
committed to this repository.

The local inference stack uses NumPy, ONNX Runtime, Hugging Face Tokenizers,
and huggingface_hub under their respective upstream licenses.

The embedding runtime structure was informed by the author's earlier MIT-licensed
Steady Inbox project, but Phantom Trace's incident schema, clustering, scoring,
evidence interface, tests, and visual design were created during the Week 4
challenge window.
