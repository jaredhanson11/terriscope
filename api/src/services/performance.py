"""Performance and benchmarking utilities for geometry recomputation.

These helpers execute set-based SQL to measure timing of stages:
1. Child grouping & signature hashing
2. Union aggregation per parent
3. Conditional update write-back

They are intended for diagnostic use only and should not be exposed publicly
without authentication.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class GeometryBenchmarkResult:
    parent_layer_id: int | None
    total_parents_considered: int
    parents_recomputed: int
    grouping_ms: float
    union_ms: float
    update_ms: float
    total_ms: float
    notes: dict[str, Any]


def benchmark_layer_union(db: Session, parent_layer_id: int) -> GeometryBenchmarkResult:
    """Benchmark recompute for all parents in a given layer.

    Assumes parent nodes have children in the next deeper layer. Measures
    three phases using EXPLAIN-less wall clock timing (lower overhead):
    - grouping/hash identification of changed parents
    - union aggregation
    - update write-back
    """
    t0 = time.perf_counter()

    # Phase 1: identify parents needing recompute
    grouping_sql = text(
        """
        WITH child_groups AS (
          SELECT c.parent_node_id AS pid,
                 STRING_AGG(c.id::text || ':' || COALESCE(c.geom_cache_key,'null'), ';' ORDER BY c.id) AS signature,
                 COUNT(*) AS child_count
          FROM nodes c
          JOIN nodes p ON p.id = c.parent_node_id
          WHERE p.layer_id = :parent_layer_id
          GROUP BY c.parent_node_id
        )
        SELECT cg.pid,
               md5(cg.signature) AS inputs_hash,
               p.geom_inputs_cache_key AS existing_hash,
               cg.child_count
        FROM child_groups cg
        JOIN nodes p ON p.id = cg.pid
        """
    )
    rows = db.execute(grouping_sql, {"parent_layer_id": parent_layer_id}).mappings().all()
    grouping_ms = (time.perf_counter() - t0) * 1000.0

    changed_parent_ids: list[int] = [
        r["pid"] for r in rows if r["existing_hash"] != r["inputs_hash"] or r["existing_hash"] is None
    ]

    # Early return if nothing changed
    if not changed_parent_ids:
        total_ms = (time.perf_counter() - t0) * 1000.0
        return GeometryBenchmarkResult(
            parent_layer_id=parent_layer_id,
            total_parents_considered=len(rows),
            parents_recomputed=0,
            grouping_ms=grouping_ms,
            union_ms=0.0,
            update_ms=0.0,
            total_ms=total_ms,
            notes={"message": "No parents needed recompute"},
        )

    # Phase 2 + 3 combined: union + conditional update in one statement
    union_start = time.perf_counter()
    # Use ANY(:changed_ids) instead of unnest parameter casting to avoid syntax error
    union_update_sql = text(
        """
        WITH changed AS (
          SELECT p.id AS pid
          FROM nodes p
          WHERE p.id = ANY(:changed_ids)
        ), child_data AS (
          SELECT ch.pid,
                 STRING_AGG(c.id::text || ':' || COALESCE(c.geom_cache_key,'null'), ';' ORDER BY c.id) AS signature
          FROM changed ch
          JOIN nodes c ON c.parent_node_id = ch.pid
          GROUP BY ch.pid
        ), calc AS (
          SELECT pid,
                 md5(signature) AS inputs_hash,
                 (
                   SELECT ST_UnaryUnion(ST_Collect(ST_MakeValid(n.geom)))
                   FROM nodes n WHERE n.parent_node_id = pid AND n.geom IS NOT NULL
                 ) AS union_geom
          FROM child_data
        ), upd AS (
          UPDATE nodes p
          SET geom = calc.union_geom,
              geom_inputs_cache_key = calc.inputs_hash,
              geom_cache_key = md5(ST_AsEWKB(calc.union_geom)::text)
          FROM calc
          WHERE p.id = calc.pid
            AND calc.union_geom IS NOT NULL
            AND (
              p.geom_inputs_cache_key IS DISTINCT FROM calc.inputs_hash OR p.geom IS NULL
            )
          RETURNING p.id
        )
        SELECT COUNT(*) AS updated_count FROM upd;
        """
    )
    # SQLAlchemy will adapt list -> array parameter for ANY() on Postgres
    updated_count = db.execute(union_update_sql, {"changed_ids": changed_parent_ids}).scalar() or 0
    update_ms = (time.perf_counter() - union_start) * 1000.0
    total_ms = (time.perf_counter() - t0) * 1000.0

    return GeometryBenchmarkResult(
        parent_layer_id=parent_layer_id,
        total_parents_considered=len(rows),
        parents_recomputed=int(updated_count),
        grouping_ms=grouping_ms,
        union_ms=update_ms,  # combined
        update_ms=update_ms,
        total_ms=total_ms,
        notes={"changed_parent_ids_sample": changed_parent_ids[:10]},
    )


def summarize_benchmark(result: GeometryBenchmarkResult) -> dict[str, Any]:
    """Summarize a geometry benchmark result.

    Returns key timing metrics and efficiency ratios derived from the
    `GeometryBenchmarkResult` dataclass for convenient JSON serialization.
    """
    return {
        "layer_id": result.parent_layer_id,
        "parents_considered": result.total_parents_considered,
        "parents_recomputed": result.parents_recomputed,
        "timing_ms": {
            "grouping": round(result.grouping_ms, 2),
            "union_and_update": round(result.union_ms, 2),
            "total": round(result.total_ms, 2),
        },
        "notes": result.notes,
    }
