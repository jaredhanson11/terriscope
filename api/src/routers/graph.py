"""Graph router."""

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, HTTPException
from geoalchemy2.functions import ST_Centroid, ST_X, ST_Y
from sqlalchemy import delete, func, select

from src.app.database import DatabaseSession
from src.exceptions import TerriscopeException
from src.models.geography import ZipCodeGeography
from src.models.graph import LayerModel, NodeModel, ZipAssignmentModel
from src.models.jobs import MapJobModel
from src.schemas.dtos.graph import (
    AssignZip,
    BulkAssignZips,
    BulkDeleteNodes,
    BulkUpdateNode,
    CreateLayer,
    CreateNode,
    MergeNodes,
    ReparentNodes,
    UpdateNode,
)
from src.schemas.graph import Layer, Node, PaginatedNodes, PaginatedZipAssignments, SearchResultItem, SearchResults, ZipAssignment
from src.services.auth import CurrentUserDependency
from src.services.graph import GraphServiceDependency
from src.services.permissions import PermissionsServiceDependency

graph_router = APIRouter(prefix="", tags=["Graph"])


def _enqueue_recompute(db: DatabaseSession, map_id: int) -> str:
    """Stage a recompute job record in the current session and return its ID.

    The caller MUST commit before dispatching the Celery task so the worker
    always sees both the structural changes and the job row.

    Usage pattern::

        <service call that mutates nodes/zips>
        job_id = _enqueue_recompute(db, map_id)
        db.commit()                                           # persists everything
        from src.workers.tasks.maps import recompute_map_task
        recompute_map_task.delay(job_id, map_id)
    """
    job_id = str(uuid.uuid4())
    job = MapJobModel(
        id=job_id,
        map_id=map_id,
        job_type="recompute",
        status="pending",
        step=None,
        error=None,
    )
    db.add(job)
    return job_id


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
    map_id: int,
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
    except TerriscopeException as e:
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


@graph_router.get("/nodes", response_model=PaginatedNodes)
def list_nodes(
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
    layer_id: int | None = None,
    parent_node_id: int | None = None,
    page: int = 1,
    page_size: int = 100,
):
    """List nodes filtered by layer_id OR parent_node_id (not both) with pagination.

    Only applies to order>=1 layers. For order=0 (zip layer) use GET /zip-assignments.
    """
    if layer_id is not None and parent_node_id is not None:
        raise HTTPException(400, "Provide either layer_id or parent_node_id, not both")
    elif layer_id is not None:
        layer = db.get(LayerModel, layer_id)
        if not layer or not permission_service.check_for_map_access(
            user_id=current_user.id,
            map_id=layer.map_id,
            map_roles=["OWNER"],
        ):
            raise HTTPException(403)
        if layer.order == 0:
            raise HTTPException(400, "Layer order=0 is the zip layer. Use GET /zip-assignments instead.")
        filter_condition = NodeModel.layer_id == layer_id
    elif parent_node_id is not None:
        parent_node = db.get(NodeModel, parent_node_id)
        layer = db.get(LayerModel, parent_node.layer_id) if parent_node else None
        if not layer or not permission_service.check_for_map_access(
            user_id=current_user.id,
            map_id=layer.map_id,
            map_roles=["OWNER"],
        ):
            raise HTTPException(403)
        filter_condition = NodeModel.parent_node_id == parent_node_id
    else:
        raise HTTPException(400, "Must provide either layer_id or parent_node_id")

    total = db.execute(select(func.count(NodeModel.id)).filter(filter_condition)).scalar() or 0
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    offset = (page - 1) * page_size

    nodes = db.execute(select(NodeModel).filter(filter_condition).offset(offset).limit(page_size)).scalars().all()

    return PaginatedNodes(
        nodes=[
            Node(
                id=node.id,
                layer_id=node.layer_id,
                color=node.color,
                name=node.name,
                parent_node_id=node.parent_node_id,
                child_count=node.child_count,
            )
            for node in nodes
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
    """Get node by id."""
    result = (
        db
        .execute(
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
    return Node(
        id=node.id,
        layer_id=node.layer_id,
        color=node.color,
        name=node.name,
        parent_node_id=node.parent_node_id,
        child_count=node.child_count,
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
        db
        .execute(
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
    except TerriscopeException as e:
        raise HTTPException(400, e.msg) from e
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
        db
        .execute(
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
        db
        .execute(
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
    for (node, layer), node_data in zip(nodes_and_layers, node_datas, strict=True):
        graph_service.update_node(node=node, node_data=node_data, layer=layer)
        updated.append(
            Node(
                id=node.id,
                layer_id=node.layer_id,
                color=node.color,
                name=node.name,
                child_count=node.child_count,
            )
        )
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
        db
        .execute(
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
    except TerriscopeException as e:
        raise HTTPException(e.code if e.code in (400, 404) else 400, e.msg) from e
    job_id = _enqueue_recompute(db, map_id)
    db.commit()
    from src.workers.tasks.maps import recompute_map_task  # noqa: PLC0415

    recompute_map_task.delay(job_id, map_id)
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
        db
        .execute(
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
    except TerriscopeException as e:
        raise HTTPException(e.code if e.code in (400, 404) else 400, e.msg) from e
    job_id = _enqueue_recompute(db, map_id)
    db.commit()
    from src.workers.tasks.maps import recompute_map_task  # noqa: PLC0415

    recompute_map_task.delay(job_id, map_id)
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
        db
        .execute(
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
    except TerriscopeException as e:
        raise HTTPException(e.code if e.code in (400, 404) else 400, e.msg) from e
    job_id = _enqueue_recompute(db, map_id)
    db.commit()
    from src.workers.tasks.maps import recompute_map_task  # noqa: PLC0415

    recompute_map_task.delay(job_id, map_id)


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
    except TerriscopeException as e:
        raise HTTPException(e.code if e.code in (400, 404) else 400, e.msg) from e
    job_id = _enqueue_recompute(db, layer.map_id)
    db.commit()
    from src.workers.tasks.maps import recompute_map_task  # noqa: PLC0415

    recompute_map_task.delay(job_id, layer.map_id)
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
    _check_layer_access(db, layer_id, current_user.id, permission_service)
    try:
        za = graph_service.assign_zip(layer_id=layer_id, zip_code=zip_code.zfill(5), data=data)
    except TerriscopeException as e:
        raise HTTPException(e.code if e.code in (400, 404) else 400, e.msg) from e
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
    _check_layer_access(db, layer_id, current_user.id, permission_service)
    graph_service.reset_zip(layer_id=layer_id, zip_code=zip_code.zfill(5))
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


@graph_router.get("/search", response_model=SearchResults)
def search_map(
    map_id: int,
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
        select(ZipAssignmentModel).where(
            ZipAssignmentModel.layer_id == layer_id,
            ZipAssignmentModel.zip_code == padded,
        )
    ).scalar_one_or_none()

    if za:
        return ZipAssignment(
            zip_code=za.zip_code, layer_id=za.layer_id, parent_node_id=za.parent_node_id, color=za.color
        )

    # Implicit state — verify zip exists in geography
    geo = db.get(ZipCodeGeography, padded)
    if not geo:
        raise HTTPException(404, f"Zip code {padded} not found.")
    return ZipAssignment(zip_code=padded, layer_id=layer_id, parent_node_id=None, color="#FFFFFF")
