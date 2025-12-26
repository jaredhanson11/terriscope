"""Layers router."""

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from src.app.database import DatabaseSession
from src.exceptions import TerriscopeException
from src.models.graph import LayerModel, NodeModel
from src.schemas.dtos.graph import BulkUpdateNode, CreateLayer, CreateNode, UpdateNode
from src.schemas.graph import Layer, Node, PaginatedNodes
from src.services import GraphServiceDependency

graph_router = APIRouter(prefix="", tags=["Graph"])


@graph_router.post("/layers")
def create_layer(
    layer_data: CreateLayer,
    graph_service: GraphServiceDependency,
    db: DatabaseSession,
):
    """Create layer."""
    # Get the highest order layer (the current top layer)
    new_layer = graph_service.create_layer(layer_data)
    db.commit()
    return Layer(id=new_layer.id, name=new_layer.name, order=new_layer.order)


@graph_router.get("/layers")
def list_layers(db: DatabaseSession):
    """List layers."""
    return [
        Layer(
            id=layer.id,
            name=layer.name,
            order=layer.order,
        )
        for layer in db.query(LayerModel).all()
    ]


@graph_router.get("/layers/{layer_id}")
def get_layer(
    layer_id: int,
    db: DatabaseSession,
):
    """Get a layer by id."""
    layer = db.get(LayerModel, layer_id)
    if layer:
        return Layer(
            id=layer.id,
            name=layer.name,
            order=layer.order,
        )
    raise HTTPException(404)


@graph_router.post("/nodes")
def create_node(
    node_data: CreateNode,
    db: DatabaseSession,
    graph_service: GraphServiceDependency,
):
    """Create node."""
    try:
        new_node = graph_service.create_node(node_data=node_data)
    except TerriscopeException as e:
        if e.code == 400 or e.code == 402:
            raise HTTPException(404, e.msg) from e
        else:
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


@graph_router.get("/nodes")
def list_nodes(
    db: DatabaseSession,
    layer_id: int | None = None,
    parent_node_id: int | None = None,
    page: int = 1,
    page_size: int = 100,
):
    """List nodes filtered by layer_id OR parent_node_id (not both) with pagination."""
    # Build filter condition - use either layer_id or parent_node_id, not both
    if layer_id is not None and parent_node_id is not None:
        raise HTTPException(400, "Provide either layer_id or parent_node_id, not both")
    elif layer_id is not None:
        filter_condition = NodeModel.layer_id == layer_id
    elif parent_node_id is not None:
        filter_condition = NodeModel.parent_node_id == parent_node_id
    else:
        raise HTTPException(400, "Must provide either layer_id or parent_node_id")

    # Count total nodes
    total = db.execute(select(func.count(NodeModel.id)).filter(filter_condition)).scalar() or 0

    # Calculate pagination
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    offset = (page - 1) * page_size

    # Query nodes with pagination
    nodes_query = select(NodeModel).filter(filter_condition).offset(offset).limit(page_size)
    nodes = db.execute(nodes_query).scalars().all()

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


@graph_router.get("/nodes/{node_id}")
def get_node(node_id: int, db: DatabaseSession):
    """Get node by id."""
    node = db.get(NodeModel, node_id)
    if node:
        return Node(
            id=node.id,
            layer_id=node.layer_id,
            color=node.color,
            name=node.name,
        )
    raise HTTPException(404)


@graph_router.put("/nodes/{node_id}")
def update_node(
    db: DatabaseSession,
    graph_service: GraphServiceDependency,
    node_id: int,
    node_data: UpdateNode,
):
    """Update node."""
    node = db.get(NodeModel, node_id)
    if node:
        graph_service.update_node(node=node, node_data=node_data)
        db.commit()
        return Node(
            id=node.id,
            layer_id=node.layer_id,
            color=node.color,
            name=node.name,
            child_count=node.child_count,
        )
    raise HTTPException(404)


@graph_router.put("/nodes/bulk")
def bulk_update_node(
    node_datas: Sequence[BulkUpdateNode],
    db: DatabaseSession,
    graph_service: GraphServiceDependency,
):
    """Update node."""
    nodes_and_layers = (
        db.execute(
            select(NodeModel, LayerModel)
            .join(target=LayerModel, onclause=NodeModel.layer_id == LayerModel.id)
            .filter(NodeModel.id.in_([_node.id for _node in node_datas]))
        )
        .tuples()
        .all()
    )
    if len(nodes_and_layers) != len(node_datas):
        found_ids = {_node.id for _node, _ in nodes_and_layers}
        wanted_ids = [_node.id for _node in node_datas]
        if len(wanted_ids) != len(set(wanted_ids)):
            raise HTTPException(400, f"Invalid request. Can't update the same node twice: {wanted_ids}")
        raise HTTPException(404, f"Can't find nodes: {found_ids - set(wanted_ids)}")

    updated_nodes: Sequence[Node] = []
    for (node, layer), node_data in zip(nodes_and_layers, node_datas, strict=True):
        graph_service.update_node(node=node, node_data=node_data, layer=layer)
        updated_nodes.append(
            Node(
                id=node.id,
                layer_id=node.layer_id,
                color=node.color,
                name=node.name,
                child_count=node.child_count,
            )
        )
    db.commit()
    return updated_nodes


@graph_router.delete("/nodes/{node_id}")
def delete_node(node_id: int):
    """Delete node."""
    pass
