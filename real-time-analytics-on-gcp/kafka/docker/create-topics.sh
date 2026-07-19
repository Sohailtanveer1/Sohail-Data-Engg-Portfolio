#!/usr/bin/env bash
# Creates the supply-chain event topics + their dead-letter counterparts.
# Explicit creation (not auto-create) so partition/replication/retention are
# reviewed decisions, not accidents of whatever a producer happened to send first.
set -euo pipefail

# On Windows/Git Bash (MSYS), any argument that looks like a Unix path is
# auto-rewritten to a Windows path before being passed to docker.exe — which
# breaks paths meant to be resolved INSIDE the Linux container (e.g.
# /opt/kafka/bin/...). Disabling that conversion keeps container-side paths
# intact. Harmless on macOS/Linux where the variable is simply ignored.
export MSYS_NO_PATHCONV=1

BOOTSTRAP="kafka-1:19092"
TOPICS_SH="/opt/kafka/bin/kafka-topics.sh"

# name                          partitions  retention.ms
DOMAIN_TOPICS=(
  "supplychain.orders.v1        6           604800000"
  "supplychain.inventory.v1     6           604800000"
  "supplychain.shipments.v1     3           604800000"
  "supplychain.returns.v1       3           604800000"
  "supplychain.suppliers.v1     3           1209600000"
)

create_topic() {
  local name=$1 partitions=$2 retention_ms=$3
  echo "Creating ${name} (partitions=${partitions}, retention.ms=${retention_ms})"
  docker exec kafka-1 "${TOPICS_SH}" --bootstrap-server "${BOOTSTRAP}" \
    --create --if-not-exists \
    --topic "${name}" \
    --partitions "${partitions}" \
    --replication-factor 3 \
    --config min.insync.replicas=2 \
    --config retention.ms="${retention_ms}" \
    --config cleanup.policy=delete
}

for row in "${DOMAIN_TOPICS[@]}"; do
  read -r name partitions retention_ms <<< "${row}"
  create_topic "${name}" "${partitions}" "${retention_ms}"

  # DLQ: single partition is enough (low volume by design — a growing DLQ is
  # an alert condition, not a throughput problem), kept longer for investigation.
  create_topic "${name}.dlq" 1 1209600000
done

echo ""
echo "Topics on the cluster:"
docker exec kafka-1 "${TOPICS_SH}" --bootstrap-server "${BOOTSTRAP}" --list
