"""Pure metadata-driven DAG builder (no Airflow import — unit-tested).

Given the platform's sources/silver/gold config, produce a task-graph spec:
sensors → ingest → silver → gold, with `dim_date` in parallel and start/end
markers. The Airflow DAG file (`supply_chain_daily.py`) turns this spec into
operators — so the *shape* of the pipeline is testable without Airflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TaskSpec:
    task_id: str
    kind: str                 # marker | sensor | ingest | silver | gold
    group: str | None = None
    upstream: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)


def build_pipeline(
    sources: list[str],
    silver_entities: dict[str, str],          # entity -> source
    gold_entities: dict[str, list[str]],      # entity -> [silver entity deps]
    file_based_sources: set[str] | None = None,
) -> list[TaskSpec]:
    file_based = file_based_sources or set()
    specs: list[TaskSpec] = [TaskSpec("start", "marker")]

    # dim_date runs independently off start.
    specs.append(TaskSpec("dim_date", "gold", group="calendar",
                          upstream=["start"], params={"entity": "dim_date"}))

    ingest_task: dict[str, str] = {}
    for src in sources:
        if src in file_based:
            sensor_id = f"wait_{src}"
            specs.append(TaskSpec(sensor_id, "sensor", group=src, upstream=["start"],
                                  params={"source": src}))
            up = [sensor_id]
        else:
            up = ["start"]
        ingest_id = f"ingest_{src}"
        specs.append(TaskSpec(ingest_id, "ingest", group=src, upstream=up,
                              params={"source": src}))
        ingest_task[src] = ingest_id

    silver_task: dict[str, str] = {}
    for entity, src in silver_entities.items():
        sid = f"silver_{entity}"
        specs.append(TaskSpec(sid, "silver", group=src, upstream=[ingest_task[src]],
                              params={"entity": entity}))
        silver_task[entity] = sid

    gold_ids: list[str] = []
    for entity, deps in gold_entities.items():
        gid = f"gold_{entity}"
        upstream = [silver_task[d] for d in deps if d in silver_task]
        specs.append(TaskSpec(gid, "gold", group="gold", upstream=upstream or ["start"],
                              params={"entity": entity}))
        gold_ids.append(gid)

    specs.append(TaskSpec("end", "marker",
                          upstream=gold_ids + ["dim_date"]))
    return specs


def edges(specs: list[TaskSpec]) -> set[tuple[str, str]]:
    """(upstream, downstream) pairs — handy for tests/visualization."""
    return {(u, s.task_id) for s in specs for u in s.upstream}


def validate_acyclic(specs: list[TaskSpec]) -> None:
    """Raise if the spec has a cycle or a dangling upstream reference."""
    ids = {s.task_id for s in specs}
    adj = {s.task_id: list(s.upstream) for s in specs}
    for s in specs:
        for u in s.upstream:
            if u not in ids:
                raise ValueError(f"Task '{s.task_id}' references unknown upstream '{u}'")

    state: dict[str, int] = {}  # 0=visiting, 1=done

    def dfs(node: str) -> None:
        if state.get(node) == 1:
            return
        if state.get(node) == 0:
            raise ValueError(f"Cycle detected at '{node}'")
        state[node] = 0
        for u in adj.get(node, []):
            dfs(u)
        state[node] = 1

    for n in ids:
        dfs(n)
