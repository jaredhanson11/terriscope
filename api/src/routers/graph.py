"""Layers router."""

from fastapi import APIRouter, HTTPException
from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon
from sqlalchemy import insert, select
from sqlalchemy.orm import defer

from src.app.database import DatabaseSession
from src.models.graph import DependencyModel, LayerModel, NodeModel
from src.schemas.dtos.graph import CreateLayer, CreateNode
from src.schemas.graph import Layer, Node

graph_router = APIRouter(prefix="", tags=["Graph"])


@graph_router.post("/layers")
def create_layer(
    layer_data: CreateLayer,
    db: DatabaseSession,
):
    """Create layer."""
    # create order as -1 to avoid unique constraint
    new_layer = LayerModel(name=layer_data.name, order=-1, parent_layer_id=None)
    db.add(new_layer)
    db.flush()

    parent_layer = db.query(LayerModel).filter(LayerModel.order == layer_data.order - 1).one()
    parent_node_ids = db.execute(select(NodeModel.id).filter(NodeModel.layer_id == parent_layer.id)).scalars().all()

    default_node = NodeModel(
        layer_id=new_layer.id,
        name="__default__",
        is_default=True,
        data={},
        geom=from_shape(MultiPolygon(), srid=4326),
        color="#fff",
    )
    db.add(default_node)
    db.flush()

    existing_layers = (
        db.query(LayerModel).filter(LayerModel.order >= layer_data.order).order_by(LayerModel.order.asc()).all()
    )
    next_layer = None
    for idx, existing_layer in enumerate(existing_layers):
        if idx == 0:
            next_layer = existing_layer
        existing_layer.order += 1

    if next_layer:
        next_layer.parent_layer_id = new_layer.id
        next_layer_node_ids = (
            db.execute(select(NodeModel.id).filter(NodeModel.layer_id == next_layer.id)).scalars().all()
        )
        db.query(DependencyModel).filter(DependencyModel.parent_id.in_(parent_node_ids)).delete()
        db.execute(
            insert(DependencyModel).values([
                {"parent_id": parent_id, "child_id": default_node.id} for parent_id in parent_node_ids
            ])
        )
        # Update all dependencies pointing to nodes in the next layer to point to new default node
        db.execute(
            insert(DependencyModel).values([
                {"parent_id": default_node.id, "child_id": child_id} for child_id in next_layer_node_ids
            ])
        )
    new_layer.parent_layer_id = parent_layer.id
    new_layer.order = layer_data.order
    db.commit()
    return Layer(
        id=new_layer.id,
        name=new_layer.name,
        order=new_layer.order,
        parent_layer_id=new_layer.parent_layer_id,
    )


@graph_router.get("/layers")
def list_layers(db: DatabaseSession):
    """List layers."""
    return [
        Layer(
            id=layer.id,
            name=layer.name,
            order=layer.order,
            parent_layer_id=layer.parent_layer_id,
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
            parent_layer_id=layer.parent_layer_id,
        )
    raise HTTPException(404)


@graph_router.post("/nodes")
def create_node(node_data: CreateNode, db: DatabaseSession):
    """Get node by id."""
    if not db.query(LayerModel.order).filter(LayerModel.id == node_data.layer_id).one().tuple()[0] > 0:
        raise HTTPException(400)
    new_node = NodeModel(
        name=node_data.name,
        layer_id=node_data.layer_id,
        color=node_data.color,
        data={},
        geom=from_shape(MultiPolygon(), srid=4236),
        is_default=False,
    )
    db.add(new_node)
    db.flush()

    new_dependency = DependencyModel(parent_id=node_data.parent_node_id, child_id=new_node.id)
    db.add(new_dependency)
    db.commit()
    return Node(
        id=new_node.id,
        layer_id=new_node.layer_id,
        color=new_node.color,
        parent_node_id=new_dependency.parent_id,
        data=new_node.data,
        name=new_node.name,
    )


@graph_router.get("/nodes")
def list_nodes(layer_id: int, db: DatabaseSession):
    """List nodes for a layer."""
    nodes = (
        db.query(NodeModel, DependencyModel.parent_id)
        .options(defer(NodeModel.geom))
        .outerjoin(target=DependencyModel, onclause=DependencyModel.child_id == NodeModel.id)
        .filter(NodeModel.layer_id == layer_id)
        .tuples()
        .all()
    )
    return [
        Node(
            id=node.id,
            name=node.name,
            layer_id=node.layer_id,
            data=node.data,
            parent_node_id=parent_id,
            color=node.color,
        )
        for node, parent_id in nodes
    ]


@graph_router.get("/nodes/{node_id}")
def get_node(node_id: int, db: DatabaseSession):
    """Get node by id."""
    row = (
        db.query(NodeModel, DependencyModel.parent_id)
        .options(defer(NodeModel.geom))
        .filter(NodeModel.id == node_id)
        .outerjoin(target=DependencyModel, onclause=DependencyModel.child_id == NodeModel.id)
        .tuples()
        .one_or_none()
    )
    if row:
        node = row[0]
        parent_node_id = row[1]
        return Node(
            id=node.id,
            name=node.name,
            layer_id=node.layer_id,
            data=node.data,
            parent_node_id=parent_node_id,
            color=node.color,
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
