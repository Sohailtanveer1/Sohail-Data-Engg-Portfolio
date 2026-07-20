"""Unit tests for the pure DAG builder (no Airflow needed)."""

import pytest
from dag_builder import TaskSpec, build_pipeline, edges, validate_acyclic

SOURCES = ["sap_erp", "wms"]
FILE_BASED = {"sap_erp"}  # wms is JDBC -> no sensor
SILVER = {"material_master": "sap_erp", "inventory": "wms"}
GOLD = {"fact_purchase_order": ["material_master"]}


def _spec():
    return build_pipeline(SOURCES, SILVER, GOLD, FILE_BASED)


def test_expected_tasks_present():
    ids = {t.task_id for t in _spec()}
    assert {
        "start",
        "end",
        "dim_date",
        "wait_sap_erp",
        "ingest_sap_erp",
        "ingest_wms",
        "silver_material_master",
        "silver_inventory",
        "gold_fact_purchase_order",
    } <= ids


def test_jdbc_source_has_no_sensor():
    ids = {t.task_id for t in _spec()}
    assert "wait_wms" not in ids  # wms is not file-based
    assert "wait_sap_erp" in ids


def test_dependency_wiring():
    e = edges(_spec())
    assert ("start", "wait_sap_erp") in e
    assert ("wait_sap_erp", "ingest_sap_erp") in e
    assert ("ingest_sap_erp", "silver_material_master") in e
    assert ("silver_material_master", "gold_fact_purchase_order") in e
    assert ("gold_fact_purchase_order", "end") in e
    assert ("dim_date", "end") in e


def test_graph_is_acyclic():
    validate_acyclic(_spec())  # should not raise


def test_dangling_upstream_detected():
    with pytest.raises(ValueError, match="unknown upstream"):
        validate_acyclic([TaskSpec("a", "marker", upstream=["ghost"])])


def test_cycle_detected():
    cyclic = [TaskSpec("a", "marker", upstream=["b"]), TaskSpec("b", "marker", upstream=["a"])]
    with pytest.raises(ValueError, match="Cycle"):
        validate_acyclic(cyclic)
