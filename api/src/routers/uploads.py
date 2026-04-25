"""Uploads router.

Handles the first phase of map creation: file upload + background parsing.

Routes:
    POST /maps/uploads        — upload a spreadsheet, kick off parse task
    GET  /maps/uploads/{id}   — poll parse status (parsing → ready | failed)
"""

import logging
import os
import uuid

from fastapi import APIRouter, Form, HTTPException, UploadFile

from src.app.database import DatabaseSession
from src.models.uploads import MapUploadModel
from src.schemas.uploads import MapUploadFailed, MapUploadParsing, MapUploadReady, MapUploadStatus
from src.services.auth import CurrentUserDependency
from src.services.permissions import PermissionsServiceDependency
from src.services.s3 import S3ServiceDependency
from src.workers.tasks.uploads import process_upload_task

logger = logging.getLogger(__name__)

uploads_router = APIRouter(prefix="/maps/uploads", tags=["Uploads"])

_ALLOWED_EXTENSIONS = {".xlsx", ".ztt"}


@uploads_router.post("", response_model=MapUploadStatus, status_code=201)
def upload_spreadsheet(
    file: UploadFile,
    current_user: CurrentUserDependency,
    db: DatabaseSession,
    s3: S3ServiceDependency,
    permission_service: PermissionsServiceDependency,
    tab_index: int = Form(default=0),
) -> MapUploadParsing | MapUploadReady | MapUploadFailed:
    """Accept an Excel/.ztt file, stream it to S3, and enqueue background parsing.

    Returns immediately with document_id. The client should poll
    GET /maps/uploads/{document_id} until status is 'ready' or 'failed'.
    """
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Allowed: {sorted(_ALLOWED_EXTENSIONS)}")

    upload_id = str(uuid.uuid4())
    s3_key = f"map-uploads/{upload_id}{ext}"

    s3.upload_private_file(file=file.file, content_type=file.content_type, key=s3_key)

    upload = MapUploadModel(
        s3_key=s3_key,
        original_filename=filename,
        tab_index=tab_index,
        status="parsing",
    )
    db.add(upload)
    db.flush()

    permission_service.add_upload_role(user_id=current_user.id, upload_id=upload.id)
    db.commit()

    process_upload_task.delay(upload.id)

    return MapUploadParsing.create(upload)


@uploads_router.get("/{document_id}", response_model=MapUploadStatus)
def get_upload_status(
    document_id: str,
    current_user: CurrentUserDependency,
    db: DatabaseSession,
    permission_service: PermissionsServiceDependency,
) -> MapUploadParsing | MapUploadReady | MapUploadFailed:
    """Poll the parse status of an uploaded file."""
    upload = db.get(MapUploadModel, document_id)
    if not upload or not permission_service.check_for_upload_access(user_id=current_user.id, upload_id=document_id):
        raise HTTPException(status_code=404, detail="Upload not found")

    match upload.status:
        case "parsing":
            return MapUploadParsing.create(upload)
        case "ready":
            return MapUploadReady.create(upload)
        case "failed":
            return MapUploadFailed.create(upload)
        case "importing" | "complete":
            raise HTTPException(status_code=409, detail="Upload has already been claimed by a map")
