"""Docs routes."""

from copy import deepcopy

from fastapi import APIRouter
from scalar_fastapi import get_scalar_api_reference  # pyright: ignore[reportUnknownVariableType]

from src import app
from src.app.openapi import openapi_generator

docs_router = APIRouter(prefix="", include_in_schema=False)


@docs_router.get(path="/try")
def docs():
    """This route is used to get the Scalar API docs."""
    return get_scalar_api_reference(
        openapi_url="/openapi.json",
        title="Terriscope API",
    )


@docs_router.get(path="/public-openapi.json")
def public_openapi():
    """This route is used to get public openapi.json schema."""
    openapi = openapi_generator(app)
    public_openapi = deepcopy(openapi)
    paths = openapi["paths"]
    for path in paths:
        operations = paths[path]
        for operation in operations:
            openapi_operation_spec = operations[operation]
            if not openapi_operation_spec.get("public", None):
                del public_openapi["paths"][path][operation]
        if not operations:
            del public_openapi["paths"][path]

    return public_openapi


@docs_router.get(path="/developers")
def public_docs():
    """This route is used to get the public facing Scalar API docs."""
    return get_scalar_api_reference(
        openapi_url="/public-openapi.json",
        title="Terriscope - API Docs",
        default_open_all_tags=False,
        hide_download_button=True,
        hide_models=True,
    )
