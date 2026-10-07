"""Nora's registered agent API (MIP-003 shape) on the Masumi registry.

Nora is registered as a Standard agent so every Masumi payment node can resolve her on-chain metadata (an
`api_base_url`); the registry health-checks `/availability`. Her work is taken as Sokosumi Tasks, so a direct
`start_job` is declined with that pointer.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/agents/nora")

NAME = "Nora · Uplift Lead"


@router.get("/availability")
def availability():
    return {"status": "available", "type": "masumi-agent", "message": f"{NAME} is ready"}


@router.get("/input_schema")
def input_schema():
    return {"input_data": [{"id": "request", "type": "string", "name": "What should Nora do for your product?"}]}


@router.post("/start_job")
def start_job():
    raise HTTPException(400, f"{NAME} takes work as a Sokosumi Task: assign a Task to her on Sokosumi.")


@router.get("/status")
def status():
    raise HTTPException(404, "Nora's work is tracked on its Sokosumi Task.")
