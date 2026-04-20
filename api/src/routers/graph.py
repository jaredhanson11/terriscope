"""Graph router."""

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, HTTPException
from geoalchemy2.functions import ST_X, ST_Y, ST_Centroid
from sqlalchemy import and_, delete, func, select
from sqlalchemy.orm import undefer

from src.app.database import DatabaseSession
from src.exceptions import TerramapsException
from src.models.geography import ZipCodeGeography
from src.models.graph import LayerModel, MapModel, NodeModel, ZipAssignmentModel
from src.models.jobs import MapJobModel
from src.schemas.dtos.graph import (
    AssignZip,
    BulkAssignZips,
    BulkDeleteNodes,
    BulkUpdateNode,
    CreateLayer,
    CreateNode,
    MergeNodes,
    NodeQuery,
    ReparentNodes,
    UpdateNode,
    ZipQuery,
)
from src.schemas.graph import (
    Layer,
    Node,
    NodeAncestor,
    PaginatedNodes,
    PaginatedZipAssignments,
    SearchResultItem,
    SearchResults,
    ZipAssignment,
)
from src.services.auth import CurrentUserDependency
from src.services.graph import GraphServiceDependency
from src.services.permissions import PermissionsServiceDependency

graph_router = APIRouter(prefix="", tags=["Graph"])


def _enqueue_recompute(db: DatabaseSession, map_id: str) -> str:
    """Stage a recompute_geometry job record in the current session and return its ID.

    The caller MUST commit before dispatching the Celery task so the worker
    always sees both the structural changes and the job row.

    Usage pattern::

        <service call that mutates nodes/zips>
        job_id = _enqueue_recompute(db, map_id)
        db.commit()                                           # persists everything
        from src.workers.tasks.maps import recompute_geometry_task
        recompute_geometry_task.delay(job_id, map_id)
    """
    job_id = str(uuid.uuid4())
    job = MapJobModel(
        id=job_id,
        map_id=map_id,
        job_type="recompute_geometry",
        status="pending",
        step=None,
        error=None,
    )
    db.add(job)
    return job_id


def _bump_tile_version(db: DatabaseSession, map_id: str) -> None:
    """Increment tile_version so clients know to re-fetch tiles after an attribute change."""
    map_model = db.get(MapModel, map_id)
    if map_model:
        map_model.tile_version += 1



# ---------------------------------------------------------------------------
# Layers
# ---------------------------------------------------------------------------


@graph_router.post("/layers", response_model=Layer)
def create_layer(
    layer_data: CreateLayer,
    graph_service: GraphServiceDependency,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
):
    """Create layer."""
    if not permission_service.check_for_map_access(
        user_id=current_user.id,
        map_id=layer_data.map_id,
        map_roles=["OWNER"],
    ):
        raise HTTPException(403, "User does not have permission to this map.")
    new_layer = graph_service.create_layer(layer_data)
    db.commit()
    return Layer(id=new_layer.id, name=new_layer.name, order=new_layer.order, map_id=new_layer.map_id)


@graph_router.get("/layers", response_model=list[Layer])
def list_layers(
    db: DatabaseSession,
    map_id: str,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
) -> list[Layer]:
    """List layers."""
    if not permission_service.check_for_map_access(
        user_id=current_user.id,
        map_id=map_id,
        map_roles=["OWNER"],
    ):
        raise HTTPException(403, "User does not have permission to this map.")
    return [
        Layer(id=layer.id, map_id=map_id, name=layer.name, order=layer.order)
        for layer in db.execute(select(LayerModel).where(LayerModel.map_id == map_id)).scalars().all()
    ]


@graph_router.get("/layers/{layer_id}", response_model=Layer)
def get_layer(
    layer_id: int,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
):
    """Get a layer by id."""
    layer = db.get(LayerModel, layer_id)
    if layer and permission_service.check_for_map_access(
        user_id=current_user.id,
        map_id=layer.map_id,
        map_roles=["OWNER"],
    ):
        return Layer(id=layer.id, name=layer.name, order=layer.order, map_id=layer.map_id)
    raise HTTPException(404)


# ---------------------------------------------------------------------------
# Nodes (order >= 1 only)
# ---------------------------------------------------------------------------


@graph_router.post("/nodes", response_model=Node)
def create_node(
    node_data: CreateNode,
    db: DatabaseSession,
    graph_service: GraphServiceDependency,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
):
    """Create node."""
    layer = db.get(LayerModel, node_data.layer_id)
    if not layer or not permission_service.check_for_map_access(
        user_id=current_user.id,
        map_id=layer.map_id,
        map_roles=["OWNER"],
    ):
        raise HTTPException(403)
    try:
        new_node = graph_service.create_node(node_data=node_data)
    except TerramapsException as e:
        if e.code == 400 or e.code == 402:
            raise HTTPException(404, e.msg) from e
        raise HTTPException(400, e.msg) from e
    db.commit()
    return Node(
        id=new_node.id,
        layer_id=new_node.layer_id,
        color=new_node.color,
        name=new_node.name,
        parent_node_id=new_node.parent_node_id,
        child_count=new_node.child_count,
    )


def _resolve_node_query_map_id(db: DatabaseSession, body: NodeQuery) -> str:
    """Derive map_id from whichever anchor field is present in a NodeQuery."""
    if body.layer_id is not None:
        layer = db.get(LayerModel, body.layer_id)
        if not layer:
            raise HTTPException(404, "Layer not found")
        if layer.order == 0:
            raise HTTPException(400, "Layer order=0 is the zip layer. Use /zip-assignments instead.")
        return layer.map_id
    if body.parent_node_id is not None:
        parent = db.get(NodeModel, body.parent_node_id)
        layer = db.get(LayerModel, parent.layer_id) if parent else None
        if not layer:
            raise HTTPException(404, "Parent node not found")
        return layer.map_id
    # ids-only path
    anchor = db.get(NodeModel, body.ids[0])  # type: ignore[index]
    layer = db.get(LayerModel, anchor.layer_id) if anchor else None
    if not layer:
        raise HTTPException(404, "Node not found")
    return layer.map_id


@graph_router.post("/nodes/query", response_model=PaginatedNodes)
def query_nodes(
    body: NodeQuery,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
    page: int = 1,
    page_size: int = 50,
):
    """Query nodes with optional filters. At least one of layer_id, parent_node_id, or ids required.

    All provided filters are combined with AND. Results are ordered by name.
    Replaces GET /nodes — use this for layer listing, parent picking, and selection detail.
    """
    if body.layer_id is None and body.parent_node_id is None and not body.ids:
        raise HTTPException(400, "Provide at least one of: layer_id, parent_node_id, ids")

    map_id = _resolve_node_query_map_id(db, body)
    if not permission_service.check_for_map_access(
        user_id=current_user.id, map_id=map_id, map_roles=["OWNER"]
    ):
        raise HTTPException(403)

    conditions = []
    if body.layer_id is not None:
        conditions.append(NodeModel.layer_id == body.layer_id)
    if body.parent_node_id is not None:
        conditions.append(NodeModel.parent_node_id == body.parent_node_id)
    if body.ids:
        conditions.append(NodeModel.id.in_(body.ids))
    if body.search:
        conditions.append(NodeModel.name.ilike(f"%{body.search}%"))

    total = db.execute(select(func.count(NodeModel.id)).where(*conditions)).scalar() or 0
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    offset = (page - 1) * page_size
    nodes = (
        db.execute(
            select(NodeModel).where(*conditions).order_by(NodeModel.name).offset(offset).limit(page_size)
        )
        .scalars()
        .all()
    )

    return PaginatedNodes(
        nodes=[
            Node(id=n.id, layer_id=n.layer_id, color=n.color, name=n.name, parent_node_id=n.parent_node_id, child_count=n.child_count)
            for n in nodes
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@graph_router.get("/nodes/{node_id}", response_model=Node)
def get_node(
    node_id: int,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
):
    """Get node by id, including computed data and full ancestor chain."""
    result = (
        db.execute(
            select(NodeModel, LayerModel)
            .join(LayerModel, NodeModel.layer_id == LayerModel.id)
            .filter(NodeModel.id == node_id)
            .options(undefer(NodeModel.data))
        )
        .tuples()
        .one_or_none()
    )
    if not result:
        raise HTTPException(404)
    node, layer = result
    if not permission_service.check_for_map_access(
        user_id=current_user.id,
        map_id=layer.map_id,
        map_roles=["OWNER"],
    ):
        raise HTTPException(403)

    # Walk parent_node_id chain upward to build the full ancestor list.
    # Hierarchies are shallow (3-4 levels max) so N+1 is acceptable here.
    ancestors: list[NodeAncestor] = []
    current_parent_id = node.parent_node_id
    while current_parent_id is not None:
        parent_result = (
            db.execute(
                select(NodeModel, LayerModel)
                .join(LayerModel, NodeModel.layer_id == LayerModel.id)
                .filter(NodeModel.id == current_parent_id)
            )
            .tuples()
            .one_or_none()
        )
        if not parent_result:
            break
        parent_node, parent_layer = parent_result
        ancestors.append(
            NodeAncestor(
                layer_id=parent_layer.id,
                layer_name=parent_layer.name,
                node_id=parent_node.id,
                node_name=parent_node.name,
                node_color=parent_node.color,
            )
        )
        current_parent_id = parent_node.parent_node_id

    return Node(
        id=node.id,
        layer_id=node.layer_id,
        color=node.color,
        name=node.name,
        parent_node_id=node.parent_node_id,
        child_count=node.child_count,
        data=node.data,
        ancestors=ancestors if ancestors else None,
    )


@graph_router.put("/nodes/{node_id}", response_model=Node)
def update_node(
    db: DatabaseSession,
    graph_service: GraphServiceDependency,
    permission_service: PermissionsServiceDependency,
    current_user: CurrentUserDependency,
    node_id: int,
    node_data: UpdateNode,
):
    """Update node."""
    result = (
        db.execute(
            select(NodeModel, LayerModel)
            .join(LayerModel, NodeModel.layer_id == LayerModel.id)
            .filter(NodeModel.id == node_id)
        )
        .tuples()
        .one_or_none()
    )
    if not result:
        raise HTTPException(404)
    node, layer = result
    if not permission_service.check_for_map_access(
        user_id=current_user.id,
        map_id=layer.map_id,
        map_roles=["OWNER"],
    ):
        raise HTTPException(403)
    try:
        graph_service.update_node(node=node, node_data=node_data, layer=layer)
    except TerramapsException as e:
        raise HTTPException(400, e.msg) from e
    _bump_tile_version(db, layer.map_id)

    db.commit()
    return Node(
        id=node.id,
        layer_id=node.layer_id,
        color=node.color,
        name=node.name,
        parent_node_id=node.parent_node_id,
        child_count=node.child_count,
    )


@graph_router.delete("/nodes/{node_id}", status_code=204)
def delete_node(
    node_id: int,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
):
    """Delete a node (order>=1 only). Cascades to child nodes via FK."""
    result = (
        db.execute(
            select(NodeModel, LayerModel)
            .join(LayerModel, NodeModel.layer_id == LayerModel.id)
            .filter(NodeModel.id == node_id)
        )
        .tuples()
        .one_or_none()
    )
    if not result:
        raise HTTPException(404)
    node, layer = result
    if not permission_service.check_for_map_access(
        user_id=current_user.id,
        map_id=layer.map_id,
        map_roles=["OWNER"],
    ):
        raise HTTPException(403)
    if layer.order == 0:
        raise HTTPException(400, "Cannot delete zip-layer entries via this endpoint. Use DELETE /zip-assignments.")
    _bump_tile_version(db, layer.map_id)

    db.execute(delete(NodeModel).where(NodeModel.id == node_id))
    db.commit()


@graph_router.put("/nodes/bulk", response_model=list[Node])
def bulk_update_node(
    node_datas: Sequence[BulkUpdateNode],
    db: DatabaseSession,
    graph_service: GraphServiceDependency,
    current_user: CurrentUserDependency,
):
    """Bulk update nodes."""
    nodes_and_layers = (
        db.execute(
            select(NodeModel, LayerModel)
            .join(target=LayerModel, onclause=NodeModel.layer_id == LayerModel.id)
            .filter(NodeModel.id.in_([n.id for n in node_datas]))
        )
        .tuples()
        .all()
    )
    if len(nodes_and_layers) != len(node_datas):
        found_ids = {n.id for n, _ in nodes_and_layers}
        wanted_ids = [n.id for n in node_datas]
        if len(wanted_ids) != len(set(wanted_ids)):
            raise HTTPException(400, f"Can't update the same node twice: {wanted_ids}")
        raise HTTPException(404, f"Can't find nodes: {set(wanted_ids) - found_ids}")

    updated: list[Node] = []
    map_ids: set[str] = set()
    for (node, layer), node_data in zip(nodes_and_layers, node_datas, strict=True):
        graph_service.update_node(node=node, node_data=node_data, layer=layer)
        map_ids.add(layer.map_id)
        updated.append(
            Node(
                id=node.id,
                layer_id=node.layer_id,
                color=node.color,
                name=node.name,
                child_count=node.child_count,
            )
        )
    for map_id in map_ids:
        _bump_tile_version(db, map_id)
    db.commit()
    return updated


@graph_router.put("/nodes/bulk/reparent", response_model=list[Node])
def bulk_reparent_nodes(
    data: ReparentNodes,
    db: DatabaseSession,
    graph_service: GraphServiceDependency,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
):
    """Bulk reparent nodes to a new parent (or orphan them).

    All nodes must be in the same layer. parent_node_id must be in the layer
    directly above, or null to remove the parent assignment.
    """
    # Permission check — all nodes must be in the same layer (validated by service),
    # so check map access once we know the layer.
    nodes_and_layers = (
        db.execute(
            select(NodeModel, LayerModel)
            .join(LayerModel, NodeModel.layer_id == LayerModel.id)
            .where(NodeModel.id.in_(data.node_ids))
        )
        .tuples()
        .all()
    )

    map_ids = {layer.map_id for _, layer in nodes_and_layers}
    for map_id in map_ids:
        if not permission_service.check_for_map_access(user_id=current_user.id, map_id=map_id, map_roles=["OWNER"]):
            raise HTTPException(403)

    map_id = next(iter(map_ids))
    try:
        updated = graph_service.reparent_nodes(data)
    except TerramapsException as e:
        raise HTTPException(e.code if e.code in (400, 404) else 400, e.msg) from e
    job_id = _enqueue_recompute(db, map_id)

    db.commit()
    from src.workers.tasks.maps import recompute_geometry_task

    recompute_geometry_task.delay(job_id, map_id)
    return [
        Node(
            id=n.id,
            layer_id=n.layer_id,
            name=n.name,
            color=n.color,
            parent_node_id=n.parent_node_id,
            child_count=n.child_count,
        )
        for n in updated
    ]


@graph_router.post("/nodes/merge", response_model=Node)
def merge_nodes(
    data: MergeNodes,
    db: DatabaseSession,
    graph_service: GraphServiceDependency,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
):
    """Merge multiple nodes into a new node in the same layer.

    Creates a new node with the given name/parent, reparents all children
    to the new node, and deletes the originals. Only valid for order>=1 layers.
    """
    nodes_and_layers = (
        db.execute(
            select(NodeModel, LayerModel)
            .join(LayerModel, NodeModel.layer_id == LayerModel.id)
            .where(NodeModel.id.in_(data.node_ids))
        )
        .tuples()
        .all()
    )

    map_ids = {layer.map_id for _, layer in nodes_and_layers}
    for map_id in map_ids:
        if not permission_service.check_for_map_access(user_id=current_user.id, map_id=map_id, map_roles=["OWNER"]):
            raise HTTPException(403)

    map_id = next(iter(map_ids))
    try:
        new_node = graph_service.merge_nodes(data)
    except TerramapsException as e:
        raise HTTPException(e.code if e.code in (400, 404) else 400, e.msg) from e
    job_id = _enqueue_recompute(db, map_id)

    db.commit()
    from src.workers.tasks.maps import recompute_geometry_task

    recompute_geometry_task.delay(job_id, map_id)
    return Node(
        id=new_node.id,
        layer_id=new_node.layer_id,
        name=new_node.name,
        color=new_node.color,
        parent_node_id=new_node.parent_node_id,
        child_count=new_node.child_count,
    )


@graph_router.delete("/nodes/bulk", status_code=204)
def bulk_delete_nodes(
    data: BulkDeleteNodes,
    db: DatabaseSession,
    graph_service: GraphServiceDependency,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
):
    """Bulk delete nodes, orphaning or reparenting their children first.

    child_action='orphan'   → children lose their parent assignment.
    child_action='reparent' → children are moved to reparent_node_id (same layer).
    Only valid for order>=1 layers. Use PUT /zip-assignments/{layer_id}/bulk to
    unassign zip codes instead.
    """
    nodes_and_layers = (
        db.execute(
            select(NodeModel, LayerModel)
            .join(LayerModel, NodeModel.layer_id == LayerModel.id)
            .where(NodeModel.id.in_(data.node_ids))
        )
        .tuples()
        .all()
    )

    map_ids = {layer.map_id for _, layer in nodes_and_layers}
    for map_id in map_ids:
        if not permission_service.check_for_map_access(user_id=current_user.id, map_id=map_id, map_roles=["OWNER"]):
            raise HTTPException(403)

    map_id = next(iter(map_ids))
    try:
        graph_service.bulk_delete_nodes(data)
    except TerramapsException as e:
        raise HTTPException(e.code if e.code in (400, 404) else 400, e.msg) from e
    job_id = _enqueue_recompute(db, map_id)

    db.commit()
    from src.workers.tasks.maps import recompute_geometry_task

    recompute_geometry_task.delay(job_id, map_id)


# ---------------------------------------------------------------------------
# Zip assignments (order=0 layer)
# ---------------------------------------------------------------------------


def _check_layer_access(
    db: DatabaseSession,
    layer_id: int,
    current_user_id: int,
    permission_service: PermissionsServiceDependency,
) -> LayerModel:
    """Load layer and verify OWNER access. Raises 403/404 as appropriate."""
    layer = db.get(LayerModel, layer_id)
    if not layer:
        raise HTTPException(404)
    if not permission_service.check_for_map_access(
        user_id=current_user_id,
        map_id=layer.map_id,
        map_roles=["OWNER"],
    ):
        raise HTTPException(403)
    return layer


@graph_router.get("/zip-assignments", response_model=PaginatedZipAssignments)
def list_zip_assignments(
    layer_id: int,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
    parent_node_id: int | None = None,
    page: int = 1,
    page_size: int = 100,
):
    """List zip assignments for an order=0 layer, optionally filtered by parent territory."""
    _check_layer_access(db, layer_id, current_user.id, permission_service)

    filter_conditions = [ZipAssignmentModel.layer_id == layer_id]
    if parent_node_id is not None:
        filter_conditions.append(ZipAssignmentModel.parent_node_id == parent_node_id)

    total = db.execute(select(func.count(ZipAssignmentModel.id)).where(*filter_conditions)).scalar() or 0
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    offset = (page - 1) * page_size

    assignments = (
        db.execute(select(ZipAssignmentModel).where(*filter_conditions).offset(offset).limit(page_size)).scalars().all()
    )

    return PaginatedZipAssignments(
        zip_assignments=[
            ZipAssignment(
                zip_code=za.zip_code,
                layer_id=za.layer_id,
                parent_node_id=za.parent_node_id,
                color=za.color,
            )
            for za in assignments
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@graph_router.post("/zip-assignments/query", response_model=PaginatedZipAssignments)
def query_zip_assignments(
    body: ZipQuery,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
    page: int = 1,
    page_size: int = 50,
):
    """Query zip codes, joining against zip_assignments for the given layer.

    Zips without an assignment row are returned with implicit defaults
    (color=#FFFFFF, parent_node_id=null) — same contract as the single-zip
    /geography endpoint. layer_id is always required; zip_codes narrows to a
    specific set (e.g. a lasso selection); search filters by zip code substring.
    Results are ordered by zip code.
    """
    _check_layer_access(db, body.layer_id, current_user.id, permission_service)

    join_cond = and_(
        ZipAssignmentModel.zip_code == ZipCodeGeography.zip_code,
        ZipAssignmentModel.layer_id == body.layer_id,
    )
    geo_conditions = []
    if body.zip_codes:
        geo_conditions.append(ZipCodeGeography.zip_code.in_(body.zip_codes))
    if body.search:
        geo_conditions.append(ZipCodeGeography.zip_code.contains(body.search))

    base = (
        select(
            ZipCodeGeography.zip_code,
            ZipAssignmentModel.parent_node_id,
            func.coalesce(ZipAssignmentModel.color, "#FFFFFF").label("color"),
        )
        .outerjoin(ZipAssignmentModel, join_cond)
        .where(*geo_conditions)
    )

    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    offset = (page - 1) * page_size
    rows = db.execute(base.order_by(ZipCodeGeography.zip_code).offset(offset).limit(page_size)).all()

    return PaginatedZipAssignments(
        zip_assignments=[
            ZipAssignment(zip_code=row.zip_code, layer_id=body.layer_id, parent_node_id=row.parent_node_id, color=row.color)
            for row in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@graph_router.put("/zip-assignments/{layer_id}/bulk", response_model=dict)
def bulk_assign_zips(
    layer_id: int,
    data: BulkAssignZips,
    db: DatabaseSession,
    graph_service: GraphServiceDependency,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
):
    """Bulk assign or unassign zip codes to a territory.

    Primary operation after lasso selection. Passing parent_node_id=null
    unassigns all provided zip codes (preserves rows and colors).
    Enqueues a geometry recompute for the affected territories after commit.
    """
    layer = _check_layer_access(db, layer_id, current_user.id, permission_service)
    try:
        count = graph_service.bulk_assign_zips(layer_id=layer_id, data=data)
    except TerramapsException as e:
        raise HTTPException(e.code if e.code in (400, 404) else 400, e.msg) from e
    job_id = _enqueue_recompute(db, layer.map_id)

    db.commit()
    from src.workers.tasks.maps import recompute_geometry_task

    recompute_geometry_task.delay(job_id, layer.map_id)
    return {"updated": count}


@graph_router.put("/zip-assignments/{layer_id}/{zip_code}", response_model=ZipAssignment)
def assign_zip(
    layer_id: int,
    zip_code: str,
    data: AssignZip,
    db: DatabaseSession,
    graph_service: GraphServiceDependency,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
):
    """Assign a zip code to a territory, or update an existing assignment.

    Passing parent_node_id=null unassigns the zip (preserves the row and color).
    """
    layer = _check_layer_access(db, layer_id, current_user.id, permission_service)
    try:
        za = graph_service.assign_zip(layer_id=layer_id, zip_code=zip_code.zfill(5), data=data)
    except TerramapsException as e:
        raise HTTPException(e.code if e.code in (400, 404) else 400, e.msg) from e
    _bump_tile_version(db, layer.map_id)

    db.commit()
    return ZipAssignment(
        zip_code=za.zip_code,
        layer_id=za.layer_id,
        parent_node_id=za.parent_node_id,
        color=za.color,
    )


@graph_router.delete("/zip-assignments/{layer_id}/{zip_code}", status_code=204)
def reset_zip(
    layer_id: int,
    zip_code: str,
    db: DatabaseSession,
    graph_service: GraphServiceDependency,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
):
    """Reset a zip code to its default state (removes the assignment row).

    The zip remains implicitly present on the map but reverts to white with no territory.
    """
    layer = _check_layer_access(db, layer_id, current_user.id, permission_service)
    graph_service.reset_zip(layer_id=layer_id, zip_code=zip_code.zfill(5))
    _bump_tile_version(db, layer.map_id)

    db.commit()


@graph_router.get("/zip-assignments/{layer_id}/{zip_code}", response_model=ZipAssignment)
def get_zip_assignment(
    layer_id: int,
    zip_code: str,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
):
    """Get the assignment state of a specific zip code. Returns 404 if the zip is implicitly unassigned."""
    _check_layer_access(db, layer_id, current_user.id, permission_service)
    za = db.execute(
        select(ZipAssignmentModel).where(
            ZipAssignmentModel.layer_id == layer_id,
            ZipAssignmentModel.zip_code == zip_code.zfill(5),
        )
    ).scalar_one_or_none()
    if not za:
        raise HTTPException(404)
    return ZipAssignment(
        zip_code=za.zip_code,
        layer_id=za.layer_id,
        parent_node_id=za.parent_node_id,
        color=za.color,
    )


@graph_router.get(
    "/zip-assignments/{layer_id}/{zip_code}/geography",
    response_model=ZipAssignment,
)
def get_zip_with_geography_default(
    layer_id: int,
    zip_code: str,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
):
    """Get a zip's assignment state, falling back to geography defaults if no row exists.

    Unlike GET /zip-assignments/{layer_id}/{zip_code}, this never returns 404 for
    known zip codes — it returns the implicit white/unassigned state.
    """
    _check_layer_access(db, layer_id, current_user.id, permission_service)
    padded = zip_code.zfill(5)

    za = db.execute(
        select(ZipAssignmentModel)
        .options(undefer(ZipAssignmentModel.data))
        .where(
            ZipAssignmentModel.layer_id == layer_id,
            ZipAssignmentModel.zip_code == padded,
        )
    ).scalar_one_or_none()

    if za:
        return ZipAssignment(
            zip_code=za.zip_code, layer_id=za.layer_id, parent_node_id=za.parent_node_id, color=za.color, data=za.data
        )

    # Implicit state — verify zip exists in geography
    geo = db.get(ZipCodeGeography, padded)
    if not geo:
        raise HTTPException(404, f"Zip code {padded} not found.")
    return ZipAssignment(zip_code=padded, layer_id=layer_id, parent_node_id=None, color="#FFFFFF")


@graph_router.get("/search", response_model=SearchResults)
def search_map(
    map_id: str,
    q: str,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
    layer_id: int | None = None,
    limit: int = 20,
):
    """Search nodes and zip codes within a map by name / zip code prefix.

    Results are ordered alphabetically and capped at `limit`. Pass `layer_id`
    to restrict the search to a single layer; omit to search all layers.
    Zip codes are matched by prefix (e.g. "902" → "90210"). Node names are
    matched as a substring (case-insensitive).
    """
    if not permission_service.check_for_map_access(
        user_id=current_user.id,
        map_id=map_id,
        map_roles=["OWNER"],
    ):
        raise HTTPException(403)

    layers = db.execute(select(LayerModel).where(LayerModel.map_id == map_id)).scalars().all()
    if layer_id is not None:
        layers = [la for la in layers if la.id == layer_id]

    layer_map = {la.id: la for la in layers}
    results: list[SearchResultItem] = []

    # ── Node search (order >= 1) ──────────────────────────────────────────────
    node_layer_ids = [la.id for la in layers if la.order >= 1]
    if node_layer_ids and q:
        rows = db.execute(  # type: ignore[arg-type]
            select(
                NodeModel.id,
                NodeModel.layer_id,
                NodeModel.name,
                NodeModel.color,
                ST_X(ST_Centroid(NodeModel.geom)).label("lng"),  # type: ignore[arg-type]
                ST_Y(ST_Centroid(NodeModel.geom)).label("lat"),  # type: ignore[arg-type]
            )
            .where(NodeModel.layer_id.in_(node_layer_ids))
            .where(NodeModel.name.ilike(f"%{q}%"))
            .order_by(NodeModel.name)
            .limit(limit)
        ).all()
        for row in rows:
            layer = layer_map[row.layer_id]
            centroid = [row.lng, row.lat] if row.lng is not None and row.lat is not None else None
            results.append(
                SearchResultItem(
                    type="node",
                    id=row.id,
                    name=row.name,
                    layer_id=row.layer_id,
                    layer_name=layer.name,
                    color=row.color,
                    centroid=centroid,
                )
            )

    # ── Zip code search (order = 0) ───────────────────────────────────────────
    zip_layer = next((la for la in layers if la.order == 0), None)
    if zip_layer and q:
        zip_rows = db.execute(  # type: ignore[arg-type]
            select(
                ZipCodeGeography.zip_code,
                ST_X(ST_Centroid(ZipCodeGeography.geom)).label("lng"),  # type: ignore[arg-type]
                ST_Y(ST_Centroid(ZipCodeGeography.geom)).label("lat"),  # type: ignore[arg-type]
            )
            .where(ZipCodeGeography.zip_code.like(f"{q}%"))
            .order_by(ZipCodeGeography.zip_code)
            .limit(limit // 2 or 10)
        ).all()
        for row in zip_rows:
            centroid = [row.lng, row.lat] if row.lng is not None and row.lat is not None else None
            results.append(
                SearchResultItem(
                    type="zip",
                    id=row.zip_code,
                    name=row.zip_code,
                    layer_id=zip_layer.id,
                    layer_name=zip_layer.name,
                    color="#FFFFFF",
                    centroid=centroid,
                )
            )

    return SearchResults(results=results, total=len(results))
