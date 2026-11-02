"""System endpoints (Phase 2): create (modes A-D), retrieve, list, delete."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.api.schemas import SystemResponse
from app.core.errors import InvalidMetadata, UnsupportedMediaType
from app.domain.models import SystemSpec
from app.services.system_service import SystemService

router = APIRouter(tags=["systems"])


def get_system_service(request: Request) -> SystemService:
    service = request.app.state.context.system_service  # type: ignore[attr-defined]
    if service is None:  # pragma: no cover - wired in lifespan
        raise InvalidMetadata("system service unavailable")
    return service


def _response_from_spec(spec: SystemSpec) -> SystemResponse:
    return SystemResponse(
        system_id=spec.system_id,
        name=spec.name,
        description=spec.description,
        objective=spec.objective,
        source_type=spec.source_type,
        source_ref=spec.source_ref,
        num_states=spec.num_states,
        num_inputs=spec.num_inputs,
        target=spec.simulation.target,
        capabilities=spec.capabilities,
        simulation=spec.simulation,
        optimization=spec.optimization,
        created_at=spec.created_at,
    )


@router.get("/catalog")
def catalog(request: Request) -> dict:
    catalog_service = request.app.state.context.catalog  # type: ignore[attr-defined]
    return {
        "items": [
            {
                "catalog_id": entry.catalog_id,
                "name": entry.name,
                "description": entry.description,
                "objective": entry.objective,
                "num_states": entry.num_states,
                "num_inputs": entry.num_inputs,
                "target": entry.target,
                "capabilities": list(entry.capabilities),
                "sources": dict(entry.sources),
            }
            for entry in catalog_service.list_entries()
        ]
    }


@router.post("/systems", status_code=status.HTTP_201_CREATED)
async def create_system(request: Request) -> SystemResponse:
    content_type = request.headers.get("content-type", "")
    service = get_system_service(request)

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise InvalidMetadata("multipart payload must include a 'file' part")
        metadata_raw = form.get("metadata")
        parsed_metadata: dict | None = None
        if metadata_raw is not None:
            try:
                parsed_metadata = json.loads(str(metadata_raw))
            except json.JSONDecodeError as exc:
                raise InvalidMetadata(f"invalid metadata JSON: {exc}") from exc
            if not isinstance(parsed_metadata, dict):
                raise InvalidMetadata("metadata must be a JSON object")
        content = await upload.read()  # type: ignore[union-attr]
        filename = getattr(upload, "filename", "")
        spec = service.create_from_upload(filename or "", content, parsed_metadata)
        return _response_from_spec(spec)

    if "application/json" not in content_type:
        raise UnsupportedMediaType("use application/json or multipart/form-data")

    try:
        payload = json.loads(await request.body())
    except json.JSONDecodeError as exc:
        raise InvalidMetadata(f"body is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise InvalidMetadata("body must be a JSON object")
    source = payload.get("source")
    if not isinstance(source, dict):
        raise InvalidMetadata("body must include a 'source' object")

    source_type = source.get("type")
    if source_type == "catalog":
        spec = service.create_from_catalog(str(source.get("catalog_id", "")))
    elif source_type == "case_study_json":
        case_study = source.get("case_study")
        if not isinstance(case_study, dict):
            raise InvalidMetadata("'case_study' must be a JSON object")
        spec = service.create_from_case_study_json(case_study)
    elif source_type == "python_code":
        metadata_obj = source.get("metadata") or {}
        if not isinstance(metadata_obj, dict):
            raise InvalidMetadata("'metadata' must be a JSON object")
        spec = service.create_from_code(str(source.get("code", "")), metadata_obj)
    else:
        raise InvalidMetadata(
            f"unknown source.type {str(source_type)!r}",
            context={"allowed": ["catalog", "case_study_json", "python_code"]},
        )
    return _response_from_spec(spec)


@router.get("/systems")
def list_systems(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    source_type: str | None = None,
    source_ref: str | None = None,
) -> dict:
    service = get_system_service(request)
    items, total = service.list(
        limit=limit,
        offset=offset,
        source_type=source_type,
        source_ref=source_ref,
    )
    return {
        "items": [_response_from_spec(spec).model_dump(mode="json") for spec in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/systems/{system_id}")
def get_system(system_id: str, request: Request) -> SystemResponse:
    service = get_system_service(request)
    return _response_from_spec(service.get(system_id))


@router.delete("/systems/{system_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_system(system_id: str, request: Request) -> None:
    service = get_system_service(request)
    service.delete(system_id)
