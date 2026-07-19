# Pipeline (End-to-End) Tests

DoFn-level and windowing tests for the Beam transforms live in
[dataflow/tests/](../../dataflow/tests/), co-located with the pipeline
code they test — see [docs/testing-guide.md](../../docs/testing-guide.md)
for what's covered there (23 passing tests across the whole repo).

This directory is reserved for a true end-to-end pipeline test:
`build_domain_pipeline()` run with `DirectRunner` against a `TestStream`
simulating Pub/Sub input (valid, malformed, duplicate, and late events in
one stream) with assertions on the DLQ output, the deduplicated output,
and correct audit-column population — the full graph, not one transform
at a time. Not yet built; the individual-transform tests in
`dataflow/tests/` were prioritized first since they isolate failures to a
specific transform, which is more useful during active development than a
single all-or-nothing end-to-end assertion.
