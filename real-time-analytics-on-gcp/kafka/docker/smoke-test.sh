#!/usr/bin/env bash
# Proves the cluster is up and a topic is writable/readable end-to-end.
# This does NOT validate schemas — that's the producer/consumer's job
# (Phase 3/4). This only proves the Kafka plumbing itself works.
set -euo pipefail

# See create-topics.sh for why: stops Git Bash (MSYS) mangling the
# container-side /opt/kafka/... paths. No-op on macOS/Linux.
export MSYS_NO_PATHCONV=1

TOPIC="supplychain.orders.v1"
BOOTSTRAP="kafka-1:19092"

echo "Producing one test message to ${TOPIC}..."
echo '{"smoke_test": true}' | docker exec -i kafka-1 \
  /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server "${BOOTSTRAP}" --topic "${TOPIC}"

echo "Consuming it back (10s timeout)..."
docker exec kafka-1 \
  /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server "${BOOTSTRAP}" --topic "${TOPIC}" \
  --from-beginning --max-messages 1 --timeout-ms 10000

echo "OK: cluster is reachable and the topic round-trips messages."
