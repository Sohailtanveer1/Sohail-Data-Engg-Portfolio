# Local Kafka Cluster

3-broker KRaft cluster (no ZooKeeper) + Kafka UI, for local development only.

## Prerequisites

Docker Desktop (or Docker Engine + Compose v2) must be installed and running.
This machine doesn't have it yet — install it before running the commands
below: https://www.docker.com/products/docker-desktop/

## Bring the cluster up

```bash
cd kafka/docker
docker compose up -d
docker compose ps            # all 4 containers should be "running"/"healthy"
```

## Create topics

```bash
./create-topics.sh
```

## Verify it works

```bash
./smoke-test.sh
```

Or browse visually at Kafka UI: http://localhost:8080

## Tear down

```bash
docker compose down          # keeps volumes (topic data persists)
docker compose down -v       # also wipes volumes — full reset
```

## Bootstrap servers

From your host machine (producers/consumers running outside Docker):
`localhost:9092,localhost:9094,localhost:9095`

From another container on the `supplychain-net` network:
`kafka-1:19092,kafka-2:19092,kafka-3:19092`
