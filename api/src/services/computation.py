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
            # Union pre-simplified zip geometries directly from geography_zip_codes.
            # Each zoom level unions the already-simplified column (gz.geom_zN) rather than
            # simplifying the full-res union result — avoids per-parent Transform+SnapToGrid+MakeValid.
            # geom_cache_key uses md5(signature) instead of md5(ST_AsEWKB(geom)) since the union
            # is deterministic: same zip set → identical geometry.
            combined_sql = text("""
                WITH child_groups AS (
                  SELECT za.parent_node_id AS pid,
                         STRING_AGG(za.zip_code, ';' ORDER BY za.zip_code) AS signature,
                         COUNT(*) AS child_count
                  FROM zip_assignments za
                  JOIN nodes p ON p.id = za.parent_node_id
                  WHERE p.layer_id = :layer_id
                    AND za.parent_node_id IS NOT NULL
                  GROUP BY za.parent_node_id
                ), candidates AS (
                  SELECT cg.pid,
                         md5(cg.signature) AS inputs_hash,
                         p.geom_inputs_cache_key AS existing_hash,
                         cg.child_count
                  FROM child_groups cg
                  JOIN nodes p ON p.id = cg.pid
                ), changed AS (
                  SELECT pid, inputs_hash, child_count
                  FROM candidates
                  WHERE :force
                     OR existing_hash IS DISTINCT FROM inputs_hash
                     OR existing_hash IS NULL
                ), calc AS (
                  SELECT ch.pid,
                         ch.inputs_hash AS signature_hash,
                         ST_UnaryUnion(ST_Collect(gz.geom))     AS union_geom,
                         ST_UnaryUnion(ST_Collect(gz.geom_z3))  AS union_z3,
                         ST_UnaryUnion(ST_Collect(gz.geom_z7))  AS union_z7,
                         ST_UnaryUnion(ST_Collect(gz.geom_z11)) AS union_z11
                  FROM changed ch
                  JOIN zip_assignments za ON za.parent_node_id = ch.pid
                  JOIN geography_zip_codes gz ON gz.zip_code = za.zip_code
                  GROUP BY ch.pid, ch.inputs_hash
                ), upd AS (
                  UPDATE nodes p
                  SET geom                  = calc.union_geom,
                      geom_z3               = calc.union_z3,
                      geom_z7               = calc.union_z7,
                      geom_z11              = calc.union_z11,
                      geom_inputs_cache_key = calc.signature_hash,
                      geom_cache_key        = calc.signature_hash
                  FROM calc
                  WHERE p.id = calc.pid
                  RETURNING p.id
                )
                SELECT
                  (SELECT COUNT(*) FROM candidates) AS parents_considered,
                  (SELECT COUNT(*) FROM upd)        AS updated_count;
            """)
        else:
            # Children are nodes; signature is node IDs + their geom_cache_keys.
            # order>1 nodes don't have pre-simplified zip columns to draw from, so we simplify
            # the union result. geom_cache_key still uses md5(signature) for the same reason.
            combined_sql = text("""
                WITH child_groups AS (
                  SELECT c.parent_node_id AS pid,
                         STRING_AGG(c.id::text || ':' || COALESCE(c.geom_cache_key,'null'), ';' ORDER BY c.id) AS signature,
                         COUNT(*) AS child_count
                  FROM nodes c
                  JOIN nodes p ON p.id = c.parent_node_id
                  WHERE p.layer_id = :layer_id
                  GROUP BY c.parent_node_id
                ), candidates AS (
                  SELECT cg.pid,
                         md5(cg.signature) AS inputs_hash,
                         p.geom_inputs_cache_key AS existing_hash,
                         cg.child_count
                  FROM child_groups cg
                  JOIN nodes p ON p.id = cg.pid
                ), changed AS (
                  SELECT pid, inputs_hash, child_count
                  FROM candidates
                  WHERE :force
                     OR existing_hash IS DISTINCT FROM inputs_hash
                     OR existing_hash IS NULL
                ), calc AS (
                  SELECT ch.pid,
                         ch.inputs_hash AS signature_hash,
                         ST_UnaryUnion(ST_Collect(n.geom)) AS union_geom
                  FROM changed ch
                  JOIN nodes n ON n.parent_node_id = ch.pid AND n.geom IS NOT NULL
                  GROUP BY ch.pid, ch.inputs_hash
                ), upd AS (
                  UPDATE nodes p
                  SET geom                  = calc.union_geom,
                      geom_z3               = CASE WHEN ST_IsEmpty(ST_MakeValid(ST_SnapToGrid(ST_Transform(calc.union_geom, 3857), 19568.0))) THEN NULL ELSE ST_Transform(ST_MakeValid(ST_SnapToGrid(ST_Transform(calc.union_geom, 3857), 19568.0)), 4326) END,
                      geom_z7               = CASE WHEN ST_IsEmpty(ST_MakeValid(ST_SnapToGrid(ST_Transform(calc.union_geom, 3857),  1223.0))) THEN NULL ELSE ST_Transform(ST_MakeValid(ST_SnapToGrid(ST_Transform(calc.union_geom, 3857),  1223.0)), 4326) END,
                      geom_z11              = CASE WHEN ST_IsEmpty(ST_MakeValid(ST_SnapToGrid(ST_Transform(calc.union_geom, 3857),    76.0))) THEN NULL ELSE ST_Transform(ST_MakeValid(ST_SnapToGrid(ST_Transform(calc.union_geom, 3857),    76.0)), 4326) END,
                      geom_z15              = CASE WHEN ST_IsEmpty(ST_MakeValid(ST_SnapToGrid(ST_Transform(calc.union_geom, 3857),     4.8))) THEN NULL ELSE ST_Transform(ST_MakeValid(ST_SnapToGrid(ST_Transform(calc.union_geom, 3857),     4.8)), 4326) END,
                      geom_inputs_cache_key = calc.signature_hash,
                      geom_cache_key        = calc.signature_hash
                  FROM calc
                  WHERE p.id = calc.pid
                    AND calc.union_geom IS NOT NULL
                  RETURNING p.id
                )
                SELECT
                  (SELECT COUNT(*) FROM candidates) AS parents_considered,
                  (SELECT COUNT(*) FROM upd)        AS updated_count;
            """)

        row = self.db.execute(combined_sql, {"layer_id": layer_id, "force": force}).mappings().one()
        parents_considered = int(row["parents_considered"])
        updated_count = int(row["updated_count"])

        if updated_count:
            self.db.flush()

        total_ms = (time.perf_counter() - start) * 1000.0
        avg_per_parent = total_ms / updated_count if updated_count else 0.0

        return {
            "layer_id": layer_id,
            "parents_considered": parents_considered,
            "parents_recomputed": updated_count,
            "timing_ms": {
                "total": round(total_ms, 2),
                "avg_per_parent": round(avg_per_parent, 2),
            },
            "notes": {"force": force},
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
