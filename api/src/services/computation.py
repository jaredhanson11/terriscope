"""Computation service for geometry roll-ups and data aggregations."""

import logging
import re
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import delete, select, text

from src.app.database import DatabaseSession
from src.models.cache import MvtTileCacheModel
from src.models.graph import LayerModel, MapModel, NodeModel
from src.services.base import BaseService

_SAFE_FIELD_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SAFE_AGG_RE = re.compile(r"^(sum|avg|min|max)$")

logger = logging.getLogger(__name__)


class ComputationService(BaseService):
    """Recompute pre-baked node geometry and invalidate the MVT tile cache."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recompute_from(self, affected_node_ids: set[int]) -> None:
        """Recompute geometry for the given nodes and all their ancestors.

        Walks upward layer by layer until no parents remain, then invalidates
        the MVT tile cache for every layer touched.
        Call before db.commit() so everything lands in one transaction.
        """
        current_ids = set(affected_node_ids)
        while current_ids:
            order_groups = self._get_layer_order_groups(current_ids)
            for order, (layer_id, ids) in sorted(order_groups.items()):
                if order == 1:
                    self._recompute_zip_layer(ids)
                else:
                    self._recompute_node_layer(ids)
                self._invalidate_tiles_for_nodes(layer_id, ids)
            current_ids = self._get_parent_ids(current_ids)

    def recompute_all_layers(self, map_id: str) -> list[LayerModel]:
        """Full geometry recompute for every order>=1 layer in a map, bottom to top.

        Used by the import task. Wipes the entire tile cache for each layer
        since every node is being computed from scratch.
        Returns the layer list in case the caller needs it.
        """
        layers = list(
            self.db.execute(
                select(LayerModel)
                .where(LayerModel.map_id == map_id, LayerModel.order >= 1)
                .order_by(LayerModel.order.asc())
            )
            .scalars()
            .all()
        )
        for layer in layers:
            node_ids = set(
                self.db.execute(select(NodeModel.id).where(NodeModel.layer_id == layer.id)).scalars().all()
            )
            if node_ids:
                if layer.order == 1:
                    self._recompute_zip_layer(node_ids)
                else:
                    self._recompute_node_layer(node_ids)

        layer_ids = {layer.id for layer in layers}
        self.invalidate_cache_for_layers(layer_ids)
        return layers

    # ------------------------------------------------------------------
    # Data aggregation
    # ------------------------------------------------------------------

    def compute_data_from(self, affected_node_ids: set[int], map_id: str) -> None:
        """Recompute data aggregations for the given nodes and all their ancestors.

        Mirrors recompute_from but for data instead of geometry — only touches
        the affected set and propagates upward, not the entire map.
        """
        map_model = self.db.get(MapModel, map_id)
        if not map_model or not map_model.data_field_config:
            return
        number_fields = [
            f for f in map_model.data_field_config
            if f.get("type") == "number" and f.get("aggregations")
        ]
        if not number_fields:
            return

        current_ids = set(affected_node_ids)
        while current_ids:
            order_groups = self._get_layer_order_groups(current_ids)
            for order, (_layer_id, ids) in sorted(order_groups.items()):
                if order == 1:
                    self._compute_data_zip_layer(ids, number_fields)
                else:
                    self._compute_data_node_layer(ids, number_fields)
            current_ids = self._get_parent_ids(current_ids)

    def compute_data_for_map(self, map_id: str) -> None:
        """Aggregate numeric data fields bottom-to-top for all layers in a map.

        Reads data_field_config from the map, then for each order>=1 layer
        (bottom to top) aggregates child data into parent nodes using SUM and
        naive AVG-of-AVGs. Skips maps with no number fields configured.
        """
        map_model = self.db.get(MapModel, map_id)
        if not map_model or not map_model.data_field_config:
            logger.info("compute_data_for_map: no data_field_config for map %s, skipping", map_id)
            return

        number_fields: list[dict[str, Any]] = [
            f for f in map_model.data_field_config
            if f.get("type") == "number" and f.get("aggregations")
        ]
        if not number_fields:
            return

        for field in number_fields:
            fname = field["field"]
            if not _SAFE_FIELD_RE.match(fname):
                raise ValueError(f"Unsafe field key in data_field_config: {fname!r}")

        layers = list(
            self.db.execute(
                select(LayerModel)
                .where(LayerModel.map_id == map_id, LayerModel.order >= 1)
                .order_by(LayerModel.order.asc())
            )
            .scalars()
            .all()
        )

        for layer in layers:
            node_ids = set(
                self.db.execute(
                    select(NodeModel.id).where(NodeModel.layer_id == layer.id)
                )
                .scalars()
                .all()
            )
            if not node_ids:
                continue
            if layer.order == 1:
                self._compute_data_zip_layer(node_ids, number_fields)
            else:
                self._compute_data_node_layer(node_ids, number_fields)

    def compute_summary_for_selection(
        self,
        layer: LayerModel,
        fields: list[dict[str, Any]],
        node_ids: list[int] | None = None,
        zip_codes: list[str] | None = None,
    ) -> dict[str, dict[str, float]]:
        """Aggregate `data` for a live selection set and return a dict shaped like NodeModel.data.

        For order=0 layers, pass zip_codes; rows are read from zip_assignments
        (flat scalars) for the given layer + zip set. For order>=1 layers, pass
        node_ids; rows are read from nodes (nested {sum,avg,min,max}). The
        rollup math mirrors the parent recompute exactly (sum-of-sums,
        avg-of-avgs, min-of-mins, max-of-maxes), so a selection of children
        produces the same numbers their shared parent would carry.
        """
        if not fields:
            return {}

        for f in fields:
            if not _SAFE_FIELD_RE.match(f["field"]):
                raise ValueError(f"Unsafe field key: {f['field']!r}")

        if layer.order == 0:
            if not zip_codes:
                return {}
            from_clause = "zip_assignments za"
            alias = "za"
            flat = True
            where_sql = "za.layer_id = :layer_id AND za.zip_code = ANY(:keys)"
            params: dict[str, Any] = {"layer_id": layer.id, "keys": list(zip_codes)}
        else:
            if not node_ids:
                return {}
            from_clause = "nodes n"
            alias = "n"
            flat = False
            where_sql = "n.id = ANY(:keys)"
            params = {"keys": list(node_ids)}

        select_parts: list[str] = []
        for f in fields:
            fname = f["field"]
            precision = f.get("precision", 4)
            exprs = self._field_rollup_exprs(fname, alias, flat=flat, precision=precision)
            for key, expr in exprs.items():
                select_parts.append(f"{expr} AS \"{fname}__{key}\"")

        sql = text(  # noqa: S608 — field names validated; identifiers fixed.
            f"SELECT {', '.join(select_parts)} FROM {from_clause} WHERE {where_sql}"
        )
        row = self.db.execute(sql, params).mappings().one_or_none()
        if not row:
            return {}

        out: dict[str, dict[str, float]] = {}
        for f in fields:
            fname = f["field"]
            sum_val = row[f"{fname}__sum_val"]
            avg_val = row[f"{fname}__avg_val"]
            min_val = row[f"{fname}__min_val"]
            max_val = row[f"{fname}__max_val"]
            if sum_val is None and avg_val is None and min_val is None and max_val is None:
                continue
            out[fname] = {
                "sum": float(sum_val) if sum_val is not None else 0.0,
                "avg": float(avg_val) if avg_val is not None else 0.0,
                "min": float(min_val) if min_val is not None else 0.0,
                "max": float(max_val) if max_val is not None else 0.0,
            }
        return out

    @staticmethod
    def _field_value_expr(fname: str, alias: str, agg: str, flat: bool) -> str:
        """SQL expression that reads a single (field, agg) value from a row's data JSONB.

        fname must be pre-validated against _SAFE_FIELD_RE; agg must be one of
        sum/avg/min/max. flat=True reads a scalar directly (leaf zip rows); flat=False
        reads from the nested {sum,avg,min,max} shape (rolled-up node rows).
        """
        if flat:
            return f"({alias}.data->>'{fname}')::numeric"
        return f"({alias}.data->'{fname}'->>'{agg}')::numeric"

    @classmethod
    def _field_rollup_exprs(cls, fname: str, alias: str, flat: bool, precision: int = 4) -> dict[str, str]:
        """Build SUM/AVG/MIN/MAX rollup expressions for a single field.

        Returns {sum_val, avg_val, min_val, max_val} -> SQL expression. Both the
        bulk parent rollup (compute_data_*) and the live selection summary
        (compute_summary_for_selection) read the same per-row data through these,
        so the JSONB shape lives in one place.
        """
        return {
            "sum_val": f"ROUND(SUM({cls._field_value_expr(fname, alias, 'sum', flat)}), {precision})",
            "avg_val": f"ROUND(AVG({cls._field_value_expr(fname, alias, 'avg', flat)}), {precision})",
            "min_val": f"MIN({cls._field_value_expr(fname, alias, 'min', flat)})",
            "max_val": f"MAX({cls._field_value_expr(fname, alias, 'max', flat)})",
        }

    @classmethod
    def _data_branch(cls, fname: str, from_clause: str, alias: str, flat: bool = False, precision: int = 4) -> str:
        """Build one UNION ALL branch for a single data field.

        fname is pre-validated against _SAFE_FIELD_RE — no injection risk.
        from_clause is e.g. "zip_assignments za" or "nodes c".
        alias is the table alias used for column references, e.g. "za" or "c".
        flat=True reads a scalar value directly (zip layer); flat=False reads nested {sum,avg,min,max}.
        precision controls ROUND() applied to sum and avg before storage (min/max preserve full precision).
        """
        exprs = cls._field_rollup_exprs(fname, alias, flat=flat, precision=precision)
        return (
            f"SELECT {alias}.parent_node_id, '{fname}'::text AS key_name,"  # noqa: S608
            f" {exprs['sum_val']} AS sum_val,"
            f" {exprs['avg_val']} AS avg_val,"
            f" {exprs['min_val']} AS min_val,"
            f" {exprs['max_val']} AS max_val"
            f" FROM {from_clause}"
            f" WHERE {alias}.parent_node_id = ANY(:node_ids) AND {alias}.data ? '{fname}'"
            f" GROUP BY {alias}.parent_node_id"
        )

    def _run_data_agg(
        self, node_ids: set[int], fields: list[dict[str, Any]], from_clause: str, alias: str, flat: bool = False
    ) -> None:
        branches = " UNION ALL ".join(
            self._data_branch(f["field"], from_clause, alias, flat=flat, precision=f.get("precision", 4))
            for f in fields
        )
        sql_str = (
            f"WITH field_aggs AS ({branches}),"  # noqa: S608
            " node_data AS ("
            "   SELECT parent_node_id,"
            "          jsonb_object_agg(key_name, jsonb_build_object('sum', sum_val, 'avg', avg_val, 'min', min_val, 'max', max_val)) AS data"
            "   FROM field_aggs GROUP BY parent_node_id"
            " )"
            " UPDATE nodes n SET data = nd.data"
            " FROM node_data nd WHERE n.id = nd.parent_node_id"
        )
        self.db.execute(text(sql_str), {"node_ids": list(node_ids)})
        self.db.flush()

    def _compute_data_zip_layer(self, node_ids: set[int], fields: list[dict[str, Any]]) -> None:
        """Aggregate zip_assignments.data (flat scalars) into order=1 territory nodes."""
        self._run_data_agg(node_ids, fields, "zip_assignments za", "za", flat=True)

    def _compute_data_node_layer(self, node_ids: set[int], fields: list[dict[str, Any]]) -> None:
        """Aggregate child node data into order>1 nodes."""
        self._run_data_agg(node_ids, fields, "nodes c", "c")

    # ------------------------------------------------------------------
    # Layer data stats — for client-side dot magnitude normalization
    # ------------------------------------------------------------------

    def compute_layer_data_stats(
        self,
        layer_id: int,
        order: int,
        fields: list[dict[str, Any]],
    ) -> dict[str, dict[str, float]]:
        """Return MVT-property-name → {min, max, p5, p95} for every (field, agg) on a layer.

        Single-pass scan of zip_assignments (order=0) or nodes (order>=1) that
        computes MIN/MAX and the 5th/95th percentiles for every field × aggregation
        combo at once. Percentiles drive winsorized client-side normalization so
        a single outlier doesn't crush the bulk of the distribution; min/max are
        kept alongside for reference (tooltips, future encodings).

        Keys mirror the MVT property names (flat field for zip layer,
        "{field}_{agg}" for node layers) so the frontend uses the same string
        when reading feature properties and looking up the range.
        """
        if not fields:
            return {}

        select_parts: list[str] = []
        result_keys: list[tuple[str, str | None]] = []
        for f in fields:
            fname = f["field"]
            if not _SAFE_FIELD_RE.match(fname):
                raise ValueError(f"Unsafe field key: {fname!r}")
            if order == 0:
                expr = f"(data->>'{fname}')::numeric"
                select_parts.append(f"MIN({expr}) AS \"{fname}__min\"")
                select_parts.append(f"MAX({expr}) AS \"{fname}__max\"")
                select_parts.append(
                    f"percentile_cont(0.05) WITHIN GROUP (ORDER BY {expr}) AS \"{fname}__p5\""
                )
                select_parts.append(
                    f"percentile_cont(0.95) WITHIN GROUP (ORDER BY {expr}) AS \"{fname}__p95\""
                )
                result_keys.append((fname, None))
            else:
                aggs: list[Any] = list(f.get("aggregations") or [])
                for agg_raw in aggs:
                    agg = str(agg_raw)
                    if not _SAFE_AGG_RE.match(agg):
                        continue
                    expr = f"(data->'{fname}'->>'{agg}')::numeric"
                    select_parts.append(f"MIN({expr}) AS \"{fname}_{agg}__min\"")
                    select_parts.append(f"MAX({expr}) AS \"{fname}_{agg}__max\"")
                    select_parts.append(
                        f"percentile_cont(0.05) WITHIN GROUP (ORDER BY {expr}) AS \"{fname}_{agg}__p5\""
                    )
                    select_parts.append(
                        f"percentile_cont(0.95) WITHIN GROUP (ORDER BY {expr}) AS \"{fname}_{agg}__p95\""
                    )
                    result_keys.append((fname, agg))

        if not select_parts:
            return {}

        from_clause = "zip_assignments" if order == 0 else "nodes"
        sql = text(  # noqa: S608 — field/agg names validated above
            f"SELECT {', '.join(select_parts)} FROM {from_clause} WHERE layer_id = :layer_id"
        )
        row = self.db.execute(sql, {"layer_id": layer_id}).mappings().one_or_none()
        if not row:
            return {}

        out: dict[str, dict[str, float]] = {}
        for fname, agg in result_keys:
            key = fname if agg is None else f"{fname}_{agg}"
            mn = row[f"{key}__min"]
            mx = row[f"{key}__max"]
            p5 = row[f"{key}__p5"]
            p95 = row[f"{key}__p95"]
            if mn is None or mx is None or p5 is None or p95 is None:
                continue
            out[key] = {
                "min": float(mn),
                "max": float(mx),
                "p5": float(p5),
                "p95": float(p95),
            }
        return out

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def _recompute_zip_layer(self, node_ids: set[int]) -> None:
        """Set geometry on order=1 nodes (territories) by unioning their assigned zips.

        Each zoom column on geography_zip_codes is already pre-simplified, so we
        union them directly into the matching column on the territory node.
        LEFT JOIN means a territory with no zips gets NULL geometry.
        """
        sql = text("""
            WITH zip_unions AS (
                SELECT za.parent_node_id AS pid,
                       ST_CollectionExtract(ST_UnaryUnion(ST_Collect(gz.geom_z3_merc)),  3) AS g3,
                       ST_CollectionExtract(ST_UnaryUnion(ST_Collect(gz.geom_z7_merc)),  3) AS g7,
                       ST_CollectionExtract(ST_UnaryUnion(ST_Collect(gz.geom_z11_merc)), 3) AS g11
                FROM zip_assignments za
                JOIN geography_zip_codes gz ON gz.zip_code = za.zip_code
                WHERE za.parent_node_id = ANY(:node_ids)
                GROUP BY za.parent_node_id
            ), affected AS (
                SELECT id FROM nodes WHERE id = ANY(:node_ids)
            )
            UPDATE nodes p
            SET geom_z3_merc  = zu.g3,
                geom_z7_merc  = zu.g7,
                geom_z11_merc = zu.g11
            FROM affected a
            LEFT JOIN zip_unions zu ON zu.pid = a.id
            WHERE p.id = a.id
        """)
        self.db.execute(sql, {"node_ids": list(node_ids)})
        self.db.flush()

    def _recompute_node_layer(self, node_ids: set[int]) -> None:
        """Set geometry on order>1 nodes (regions, areas) by unioning their child nodes.

        Children already have correct pre-simplified geometry per zoom level, so we
        union each column directly — no extra simplification math needed.
        LEFT JOIN means a node with no geometry-bearing children gets NULL geometry.
        """
        sql = text("""
            WITH child_unions AS (
                SELECT c.parent_node_id AS pid,
                       ST_CollectionExtract(ST_UnaryUnion(ST_Collect(c.geom_z3_merc)),  3) AS g3,
                       ST_CollectionExtract(ST_UnaryUnion(ST_Collect(c.geom_z7_merc)),  3) AS g7,
                       ST_CollectionExtract(ST_UnaryUnion(ST_Collect(c.geom_z11_merc)), 3) AS g11
                FROM nodes c
                WHERE c.parent_node_id = ANY(:node_ids)
                GROUP BY c.parent_node_id
            ), affected AS (
                SELECT id FROM nodes WHERE id = ANY(:node_ids)
            )
            UPDATE nodes p
            SET geom_z3_merc  = cu.g3,
                geom_z7_merc  = cu.g7,
                geom_z11_merc = cu.g11
            FROM affected a
            LEFT JOIN child_unions cu ON cu.pid = a.id
            WHERE p.id = a.id
        """)
        self.db.execute(sql, {"node_ids": list(node_ids)})
        self.db.flush()

    # ------------------------------------------------------------------
    # Tile cache invalidation
    # ------------------------------------------------------------------

    def invalidate_cache_for_layers(self, layer_ids: set[int]) -> None:
        """Delete ALL cached MVT tiles for the given layers.

        Use for full recomputes (import). For incremental edits use recompute_from,
        which scopes cache deletes to the bounding box of changed nodes.
        Does not commit — caller owns the transaction.
        """
        if not layer_ids:
            return
        self.db.execute(delete(MvtTileCacheModel).where(MvtTileCacheModel.layer_id.in_(layer_ids)))
        self.db.flush()

    def _invalidate_tiles_for_nodes(self, layer_id: int, node_ids: set[int]) -> None:
        """Delete MVT cache tiles for layer_id that cover the bounding box of the given nodes.

        Computes tile (x, y) ranges for z=3..11 from the nodes' updated 3857 geometry.
        Tile coords come straight from the meter offset into the Mercator world square,
        so no trig or degree math is needed.
        Does not commit — caller owns the transaction.
        """
        sql = text("""
            WITH bbox AS (
                SELECT ST_Extent(COALESCE(n.geom_z11_merc, n.geom_z7_merc, n.geom_z3_merc)) AS geom
                FROM nodes n
                WHERE n.id = ANY(:node_ids)
            ),
            tile_ranges AS (
                SELECT
                    z::smallint,
                    GREATEST(0, FLOOR((ST_XMin(b.geom) + 20037508.3427892) / 40075016.6855784 * POW(2, z))::int) AS x_min,
                    FLOOR((ST_XMax(b.geom) + 20037508.3427892) / 40075016.6855784 * POW(2, z))::int             AS x_max,
                    GREATEST(0, FLOOR((20037508.3427892 - ST_YMax(b.geom)) / 40075016.6855784 * POW(2, z))::int) AS y_min,
                    FLOOR((20037508.3427892 - ST_YMin(b.geom)) / 40075016.6855784 * POW(2, z))::int             AS y_max
                FROM bbox b, generate_series(3, 11) z
                WHERE b.geom IS NOT NULL
            )
            DELETE FROM mvt_tile_cache c
            USING tile_ranges tr
            WHERE c.layer_id = :layer_id
              AND c.z = tr.z
              AND c.x BETWEEN tr.x_min AND tr.x_max
              AND c.y BETWEEN tr.y_min AND tr.y_max
        """)
        self.db.execute(sql, {"layer_id": layer_id, "node_ids": list(node_ids)})
        self.db.flush()

    # ------------------------------------------------------------------
    # Propagation helpers
    # ------------------------------------------------------------------

    def _get_layer_order_groups(self, node_ids: set[int]) -> dict[int, tuple[int, set[int]]]:
        """Group node IDs by their layer's order. Returns {order: (layer_id, node_ids)}."""
        rows = self.db.execute(
            select(NodeModel.id, LayerModel.id, LayerModel.order)
            .join(LayerModel, NodeModel.layer_id == LayerModel.id)
            .where(NodeModel.id.in_(node_ids))
        ).all()
        groups: dict[int, tuple[int, set[int]]] = {}
        for node_id, layer_id, order in rows:
            if order not in groups:
                groups[order] = (layer_id, set())
            groups[order][1].add(node_id)
        return groups

    def _get_parent_ids(self, node_ids: set[int]) -> set[int]:
        """Return the non-null parent_node_ids of the given nodes."""
        rows = (
            self.db.execute(
                select(NodeModel.parent_node_id)
                .where(NodeModel.id.in_(node_ids), NodeModel.parent_node_id.isnot(None))
            )
            .scalars()
            .all()
        )
        return {r for r in rows if r is not None}


def get_computation_service(db: DatabaseSession) -> ComputationService:
    """Get computation service."""
    return ComputationService(db=db)


ComputationServiceDependency = Annotated[ComputationService, Depends(get_computation_service)]
