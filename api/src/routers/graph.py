"""Layers router."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from src.app.database import DatabaseSession
from src.models.graph import LayerModel, NodeModel
from src.schemas.dtos.graph import CreateLayer, CreateNode
from src.schemas.graph import Layer, Node

graph_router = APIRouter(prefix="", tags=["Graph"])


@graph_router.post("/layers")
def create_layer(
    layer_data: CreateLayer,
    db: DatabaseSession,
):
    """Create layer."""
    # Get the highest order layer (the current top layer)
    child_layer = db.execute(select(LayerModel).order_by(LayerModel.order.desc())).scalars().first()

    # Create new layer one level above
    new_layer = LayerModel(name=layer_data.name, order=child_layer.order + 1 if child_layer else 0)
    db.add(new_layer)
    db.flush()

    # Create default node for new layer
    default_node = NodeModel(
        layer_id=new_layer.id,
        name="__default__",
        color="#fff",
        data=None,
        geom=None,
        parent_node_id=None,
    )
    db.add(default_node)
    db.flush()

    # Update all nodes in the child layer to point to this new default node as parent
    child_nodes = (
        db.execute(select(NodeModel).filter(NodeModel.layer_id == child_layer.id)).scalars().all()
        if child_layer
        else list[NodeModel]([])
    )
    for child_node in child_nodes:
        child_node.parent_node_id = default_node.id

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
def get_layer(layer_id: int, db: DatabaseSession):
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
def create_node(node_data: CreateNode, db: DatabaseSession):
    """Create node."""
    layer = db.get(LayerModel, node_data.layer_id)
    if not layer or layer.order == 0:
        raise HTTPException(400, "Cannot create nodes in layer 0")

    new_node = NodeModel(
        name=node_data.name,
        layer_id=node_data.layer_id,
        color=node_data.color,
        parent_node_id=node_data.parent_node_id,
        geom=None,
        data=None,
    )
    db.add(new_node)
    db.commit()

    return Node(
        id=new_node.id,
        layer_id=new_node.layer_id,
        color=new_node.color,
        name=new_node.name,
        parent_node_id=new_node.parent_node_id,
        child_count=0,
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
    from src.schemas.graph import Node, PaginatedNodes

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

    # Get child counts efficiently with a single query
    node_ids = [node.id for node in nodes]
    child_counts: dict[int, int] = {}
    if node_ids:
        child_count_results = db.execute(
            select(NodeModel.parent_node_id, func.count(NodeModel.id))
            .filter(NodeModel.parent_node_id.in_(node_ids))
            .group_by(NodeModel.parent_node_id)
        ).all()
        for parent_id, count in child_count_results:
            if parent_id is not None:
                child_counts[parent_id] = count

    return PaginatedNodes(
        nodes=[
            Node(
                id=node.id,
                layer_id=node.layer_id,
                color=node.color,
                name=node.name,
                parent_node_id=node.parent_node_id,
                child_count=child_counts.get(node.id, 0),
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
    node_id: int,
    node_data: CreateNode,
):
    """Update node."""
    node = db.get(NodeModel, node_id)
    if node:
        node.color = node_data.color
        node.layer_id = node_data.layer_id
        node.parent_node_id = node_data.parent_node_id
        node.name = node_data.name
        child_count = db.execute(
            select(func.count(NodeModel.id)).filter(NodeModel.parent_node_id == node.id)
        ).scalar_one()
        db.commit()
        return Node(
            id=node.id,
            layer_id=node.layer_id,
            color=node.color,
            name=node.name,
            child_count=child_count,
        )
    raise HTTPException(404)


@graph_router.delete("/nodes/{node_id}")
def delete_node(node_id: int):
    """Delete node."""
    pass
