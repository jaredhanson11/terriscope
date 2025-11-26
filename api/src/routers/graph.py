"""Layers router."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import lazyload

from src.app.database import DatabaseSession
from src.models.graph import LayerModel, NodeModel
from src.schemas.dtos.graph import CreateLayer, CreateNode
from src.schemas.graph import Layer, Node, NodeWithChildren

graph_router = APIRouter(prefix="", tags=["Graph"])


@graph_router.post("/layers")
def create_layer(
    layer_data: CreateLayer,
    db: DatabaseSession,
):
    """Create layer."""
    # Get the highest order layer (the current top layer)
    child_layer = db.execute(select(LayerModel).order_by(LayerModel.order.desc())).scalar_one()

    # Create new layer one level above
    new_layer = LayerModel(name=layer_data.name, order=child_layer.order + 1)
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
    child_nodes = db.execute(select(NodeModel).filter(NodeModel.layer_id == child_layer.id)).scalars().all()
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

    return NodeWithChildren(
        id=new_node.id,
        layer_id=new_node.layer_id,
        color=new_node.color,
        name=new_node.name,
        children=[
            Node(
                id=child.id,
                layer_id=child.layer_id,
                name=child.name,
                color=child.color,
            )
            for child in new_node.children
        ],
    )


@graph_router.get("/nodes")
def list_nodes(layer_id: int, db: DatabaseSession):
    """List nodes for a layer."""
    nodes_query = select(NodeModel).filter(NodeModel.layer_id == layer_id)
    if layer_id == 1:
        nodes_query = nodes_query.options(lazyload(NodeModel.children))
    nodes = db.execute(nodes_query).scalars().all()
    return [
        NodeWithChildren(
            id=node.id,
            layer_id=node.layer_id,
            color=node.color,
            name=node.name,
            children=[
                Node(
                    id=child.id,
                    layer_id=child.layer_id,
                    name=child.name,
                    color=child.color,
                )
                for child in list[NodeModel]([])
            ],
        )
        for node in nodes
    ]


@graph_router.get("/nodes/{node_id}")
def get_node(node_id: int, db: DatabaseSession):
    """Get node by id."""
    node = db.get(NodeModel, node_id)
    if node:
        return NodeWithChildren(
            id=node.id,
            layer_id=node.layer_id,
            color=node.color,
            name=node.name,
            children=[
                Node(
                    id=child.id,
                    layer_id=child.layer_id,
                    name=child.name,
                    color=child.color,
                )
                for child in node.children
            ],
        )
    raise HTTPException(404)


@graph_router.put("/nodes/{node_id}")
def update_node(node_id: int):
    """Update node."""
    pass


@graph_router.delete("/nodes/{node_id}")
def delete_node(node_id: int):
    """Delete node."""
    pass
