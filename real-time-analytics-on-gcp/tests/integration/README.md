# Integration Tests

Not yet implemented — flagged explicitly in
[docs/lessons-learned.md](../../docs/lessons-learned.md) as a known gap
rather than left silently empty.

**Planned scope:** a CI job that stands up
`kafka/docker/docker-compose.yml`, runs the real producer against it, runs
the real consumer, and asserts: (a) valid events are consumed correctly,
(b) a deliberately malformed event lands on the correct `.dlq` topic with
the expected `reason`, (c) a duplicate `event_id` is observable at the
Kafka level (this layer's dedup is Beam's job, not the consumer's — an
integration test here should assert the consumer does NOT dedup, only
routes/logs, to keep that responsibility boundary honest).

Not run against real GCP resources (Pub/Sub, BigQuery) — that's
deliberately out of scope for automated CI; see
[docs/testing-guide.md](../../docs/testing-guide.md) for why.
