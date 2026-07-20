"""Unit tests for the SCD MERGE SQL builders (no SparkSession needed)."""

from spark.transforms.scd import (
    build_scd1_merge_sql,
    build_scd2_close_sql,
    build_scd2_insert_sql,
    build_scd2_statements,
)


def test_scd1_merge_updates_and_inserts():
    sql = build_scd1_merge_sql("scb.silver.dim_wh", "src", ["warehouse_id"],
                               update_columns=["region", "state"],
                               insert_columns=["warehouse_id", "region", "state"])
    assert "MERGE INTO scb.silver.dim_wh t" in sql
    assert "ON t.`warehouse_id` = s.`warehouse_id`" in sql
    assert "WHEN MATCHED THEN UPDATE SET t.`region` = s.`region`, t.`state` = s.`state`" in sql
    assert "WHEN NOT MATCHED THEN INSERT" in sql


def test_scd2_close_only_when_hash_changes():
    sql = build_scd2_close_sql("scb.silver.dim_material", "src", ["material_id"])
    assert "t.`is_current` = true" in sql
    assert "t.`row_hash` <> s.`row_hash`" in sql
    assert "UPDATE SET t.`is_current` = false, t.`effective_to` = s.`effective_from`" in sql


def test_scd2_insert_new_and_changed():
    sql = build_scd2_insert_sql("scb.silver.dim_material", "src", ["material_id"],
                                insert_columns=["material_sk", "material_id", "row_hash"])
    assert "INSERT INTO scb.silver.dim_material (`material_sk`, `material_id`, `row_hash`)" in sql
    assert "LEFT JOIN scb.silver.dim_material t" in sql
    assert "WHERE t.`material_id` IS NULL OR t.`row_hash` <> s.`row_hash`" in sql


def test_scd2_statements_are_close_then_insert():
    stmts = build_scd2_statements("tbl", "src", ["k"], ["k", "row_hash"])
    assert len(stmts) == 2
    assert stmts[0].startswith("MERGE INTO")   # close first
    assert stmts[1].startswith("INSERT INTO")  # then insert
