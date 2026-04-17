"""Computation service for graph geometry roll-ups."""

import logging
import time
from typing import Annotated

from fastapi import Depends
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import JSONB as PgJSONB

from src.app.database import DatabaseSession
from src.models.graph import LayerModel
from src.services.base import BaseService

logger = logging.getLogger(__name__)


class ComputationService(BaseService):
    """Compute derived geometry and data for graph nodes."""

    def bulk_recompute_layer(self, layer_id: int, force: bool = False) -> dict[str, object]:
        """Bulk recompute geometries for all parent nodes in a layer.

        For order=1 layers, children are zip_assignments joined to geography_zip_codes.
        For order>1 layers, children are nodes (standard recursive union).

        Signature hashing detects which parents need recompute unless force=True.
        Returns timing metrics and counts.
        """
        layer = self.db.get(LayerModel, layer_id)
        if layer is None:
            return {"layer_id": layer_id, "error": "Layer not found"}

        start = time.perf_counter()

        if layer.order == 1:
            # Children live in zip_assignments; signature is sorted zip_codes (geography
            # geometries are static so the zip set fully determines the inputs hash).
            grouping_sql = text("""
                WITH child_groups AS (
                  SELECT za.parent_node_id AS pid,
                         STRING_AGG(za.zip_code, ';' ORDER BY za.zip_code) AS signature,
                         COUNT(*) AS child_count
                  FROM zip_assignments za
                  JOIN nodes p ON p.id = za.parent_node_id
                  WHERE p.layer_id = :layer_id
                    AND za.parent_node_id IS NOT NULL
                  GROUP BY za.parent_node_id
                )
                SELECT cg.pid,
                       md5(cg.signature) AS inputs_hash,
                       p.geom_inputs_cache_key AS existing_hash,
                       cg.child_count
                FROM child_groups cg
                JOIN nodes p ON p.id = cg.pid
            """)
        else:
            # Children are nodes; signature is node IDs + their geom_cache_keys.
            grouping_sql = text("""
                WITH child_groups AS (
                  SELECT c.parent_node_id AS pid,
                         STRING_AGG(c.id::text || ':' || COALESCE(c.geom_cache_key,'null'), ';' ORDER BY c.id) AS signature,
                         COUNT(*) AS child_count
                  FROM nodes c
                  JOIN nodes p ON p.id = c.parent_node_id
                  WHERE p.layer_id = :layer_id
                  GROUP BY c.parent_node_id
                )
                SELECT cg.pid,
                       md5(cg.signature) AS inputs_hash,
                       p.geom_inputs_cache_key AS existing_hash,
                       cg.child_count
                FROM child_groups cg
                JOIN nodes p ON p.id = cg.pid
            """)

        rows = self.db.execute(grouping_sql, {"layer_id": layer_id}).mappings().all()
        grouping_ms = (time.perf_counter() - start) * 1000.0

        if force:
            changed_parent_ids = [r["pid"] for r in rows]
        else:
            changed_parent_ids = [
                r["pid"] for r in rows if r["existing_hash"] != r["inputs_hash"] or r["existing_hash"] is None
            ]

        if not changed_parent_ids:
            total_ms = (time.perf_counter() - start) * 1000.0
            return {
                "layer_id": layer_id,
                "parents_considered": len(rows),
                "parents_recomputed": 0,
                "timing_ms": {
                    "grouping": round(grouping_ms, 2),
                    "union_and_update": 0.0,
                    "total": round(total_ms, 2),
                    "avg_per_parent": 0.0,
                },
                "notes": {"message": "No parents needed recompute", "force": force},
            }

        union_start = time.perf_counter()

        if layer.order == 1:
            # Union geometries directly from geography_zip_codes via zip_assignments.
            # md5(signature) is recomputed inline so the UPDATE condition is self-contained.
            union_update_sql = text("""
                WITH changed AS (
                  SELECT p.id AS pid
                  FROM nodes p
                  WHERE p.id = ANY(:changed_ids)
                ), calc AS (
                  SELECT ch.pid,
                         STRING_AGG(za.zip_code, ';' ORDER BY za.zip_code) AS signature,
                         ST_UnaryUnion(ST_Collect(ST_MakeValid(gz.geom))) AS union_geom
                  FROM changed ch
                  JOIN zip_assignments za ON za.parent_node_id = ch.pid
                  JOIN geography_zip_codes gz ON gz.zip_code = za.zip_code
                  WHERE gz.geom IS NOT NULL
                  GROUP BY ch.pid
                ), upd AS (
                  UPDATE nodes p
                  SET geom     = calc.union_geom,
                      geom_z3  = ST_Transform(ST_MakeValid(ST_SnapToGrid(ST_Transform(calc.union_geom, 3857), 19568.0)), 4326),
                      geom_z7  = ST_Transform(ST_MakeValid(ST_SnapToGrid(ST_Transform(calc.union_geom, 3857),  1223.0)), 4326),
                      geom_z11 = ST_Transform(ST_MakeValid(ST_SnapToGrid(ST_Transform(calc.union_geom, 3857),    76.0)), 4326),
                      geom_z15 = ST_Transform(ST_MakeValid(ST_SnapToGrid(ST_Transform(calc.union_geom, 3857),     4.8)), 4326),
                      geom_inputs_cache_key = md5(calc.signature),
                      geom_cache_key        = md5(ST_AsEWKB(calc.union_geom)::text)
                  FROM calc
                  WHERE p.id = calc.pid
                    AND calc.union_geom IS NOT NULL
                    AND (
                      p.geom_inputs_cache_key IS DISTINCT FROM md5(calc.signature)
                      OR p.geom IS NULL
                      OR :force
                    )
                  RETURNING p.id
                )
                SELECT COUNT(*) AS updated_count FROM upd;
            """)
        else:
            union_update_sql = text("""
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
                  SET geom     = calc.union_geom,
                      geom_z3  = ST_Transform(ST_MakeValid(ST_SnapToGrid(ST_Transform(calc.union_geom, 3857), 19568.0)), 4326),
                      geom_z7  = ST_Transform(ST_MakeValid(ST_SnapToGrid(ST_Transform(calc.union_geom, 3857),  1223.0)), 4326),
                      geom_z11 = ST_Transform(ST_MakeValid(ST_SnapToGrid(ST_Transform(calc.union_geom, 3857),    76.0)), 4326),
                      geom_z15 = ST_Transform(ST_MakeValid(ST_SnapToGrid(ST_Transform(calc.union_geom, 3857),     4.8)), 4326),
                      geom_inputs_cache_key = calc.inputs_hash,
                      geom_cache_key        = md5(ST_AsEWKB(calc.union_geom)::text)
                  FROM calc
                  WHERE p.id = calc.pid
                    AND calc.union_geom IS NOT NULL
                    AND (
                      p.geom_inputs_cache_key IS DISTINCT FROM calc.inputs_hash
                      OR p.geom IS NULL
                      OR :force
                    )
                  RETURNING p.id
                )
                SELECT COUNT(*) AS updated_count FROM upd;
            """)

        updated_count = (
            self.db.execute(union_update_sql, {"changed_ids": changed_parent_ids, "force": force}).scalar() or 0
        )
        if updated_count:
            self.db.flush()

        union_ms = (time.perf_counter() - union_start) * 1000.0
        total_ms = (time.perf_counter() - start) * 1000.0
        avg_per_parent = union_ms / updated_count if updated_count else 0.0

        return {
            "layer_id": layer_id,
            "parents_considered": len(rows),
            "parents_recomputed": int(updated_count),
            "timing_ms": {
                "grouping": round(grouping_ms, 2),
                "union_and_update": round(union_ms, 2),
                "total": round(total_ms, 2),
                "avg_per_parent": round(avg_per_parent, 2),
            },
            "notes": {"changed_parent_ids_sample": changed_parent_ids[:10], "force": force},
        }

    def bulk_recompute_data_layer(
        self,
        layer_id: int,
        data_field_config: list[dict[str, object]],
        force: bool = False,
    ) -> dict[str, object]:
        """Bulk recompute aggregated data for all parent nodes in a layer.

        For order=1 layers, leaf data is read from zip_assignments.
        For order>1 layers, leaf data is read from child nodes.

        Uses cache-key diffing to skip unchanged parents unless force=True.
        """
        numeric_fields: list[dict[str, object]] = [
            f for f in data_field_config if f.get("type") == "number" and f.get("aggregations")
        ]
        if not numeric_fields:
            return {"layer_id": layer_id, "parents_recomputed": 0, "notes": {"message": "No numeric fields"}}

        layer = self.db.get(LayerModel, layer_id)
        if layer is None:
            return {"layer_id": layer_id, "error": "Layer not found"}

        start = time.perf_counter()

        if layer.order == 1:
            agg_expr = self._build_agg_expr(numeric_fields, child_alias="za")
            grouping_sql = text(
                f"""
                WITH child_groups AS (
                  SELECT za.parent_node_id AS pid,
                         STRING_AGG(za.zip_code || ':' || COALESCE(za.data_cache_key,'null'), ';' ORDER BY za.zip_code) AS signature,
                         {agg_expr} AS agg_data
                  FROM zip_assignments za
                  JOIN nodes p ON p.id = za.parent_node_id
                  WHERE p.layer_id = :layer_id
                    AND za.parent_node_id IS NOT NULL
                    AND za.data IS NOT NULL
                  GROUP BY za.parent_node_id
                )
                SELECT cg.pid,
                       md5(cg.signature) AS inputs_hash,
                       p.data_inputs_cache_key AS existing_hash,
                       cg.agg_data
                FROM child_groups cg
                JOIN nodes p ON p.id = cg.pid
                """  # noqa: S608
            )
        else:
            agg_expr = self._build_agg_expr(numeric_fields, child_alias="c")
            grouping_sql = text(
                f"""
                WITH child_groups AS (
                  SELECT c.parent_node_id AS pid,
                         STRING_AGG(c.id::text || ':' || COALESCE(c.data_cache_key,'null'), ';' ORDER BY c.id) AS signature,
                         {agg_expr} AS agg_data
                  FROM nodes c
                  JOIN nodes p ON p.id = c.parent_node_id
                  WHERE p.layer_id = :layer_id
                    AND c.data IS NOT NULL
                  GROUP BY c.parent_node_id
                )
                SELECT cg.pid,
                       md5(cg.signature) AS inputs_hash,
                       p.data_inputs_cache_key AS existing_hash,
                       cg.agg_data
                FROM child_groups cg
                JOIN nodes p ON p.id = cg.pid
                """  # noqa: S608
            )

        rows = self.db.execute(grouping_sql, {"layer_id": layer_id}).mappings().all()
        grouping_ms = (time.perf_counter() - start) * 1000.0

        if force:
            to_update = [(r["pid"], r["inputs_hash"], r["agg_data"]) for r in rows]
        else:
            to_update = [
                (r["pid"], r["inputs_hash"], r["agg_data"])
                for r in rows
                if r["existing_hash"] != r["inputs_hash"] or r["existing_hash"] is None
            ]

        if not to_update:
            total_ms = (time.perf_counter() - start) * 1000.0
            return {
                "layer_id": layer_id,
                "parents_considered": len(rows),
                "parents_recomputed": 0,
                "timing_ms": {"total": round(total_ms, 2)},
                "notes": {"message": "No parents needed recompute", "force": force},
            }

        update_start = time.perf_counter()
        update_sql = text(
            """
            UPDATE nodes
            SET data = vals.agg_data,
                data_inputs_cache_key = vals.inputs_hash,
                data_cache_key = md5(vals.agg_data::text)
            FROM (SELECT unnest(:pids) AS pid,
                         unnest(:hashes) AS inputs_hash,
                         unnest(:agg_datas) AS agg_data) AS vals
            WHERE nodes.id = vals.pid
            """
        ).bindparams(bindparam("agg_datas", type_=ARRAY(PgJSONB())))

        self.db.execute(
            update_sql,
            {
                "pids": [r[0] for r in to_update],
                "hashes": [r[1] for r in to_update],
                "agg_datas": [r[2] for r in to_update],
            },
        )
        self.db.flush()

        update_ms = (time.perf_counter() - update_start) * 1000.0
        total_ms = (time.perf_counter() - start) * 1000.0

        return {
            "layer_id": layer_id,
            "parents_considered": len(rows),
            "parents_recomputed": len(to_update),
            "timing_ms": {
                "grouping": round(grouping_ms, 2),
                "update": round(update_ms, 2),
                "total": round(total_ms, 2),
            },
            "notes": {"force": force},
        }

    @staticmethod
    def _build_agg_expr(numeric_fields: list[dict[str, object]], child_alias: str) -> str:
        """Build a jsonb_build_object(...) expression aggregating data fields from child_alias.

        child_alias is the SQL alias of the child table (either 'c' for nodes or 'za' for
        zip_assignments). Both tables store data as JSONB under the same suffixed keys
        (e.g. 'customers_sum'), so the expression is identical except for the table alias.
        """
        agg_parts: list[str] = []
        for field in numeric_fields:
            field_name = str(field["field"])
            for agg in list(field.get("aggregations", [])):  # type: ignore[arg-type]
                key = f"{field_name}_{agg}"
                if agg == "sum":
                    expr = f"'{key}', SUM(({child_alias}.data->>'{key}')::numeric)"
                else:  # avg
                    expr = f"'{key}', AVG(({child_alias}.data->>'{key}')::numeric)"
                agg_parts.append(expr)
        return f"jsonb_build_object({', '.join(agg_parts)})"


def get_computation_service(db: DatabaseSession) -> ComputationService:
    """Get computation service."""
    return ComputationService(db=db)


ComputationServiceDependency = Annotated[ComputationService, Depends(get_computation_service)]
