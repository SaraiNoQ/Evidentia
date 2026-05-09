from fastapi import APIRouter, Request

from app.api.envelope import success

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    return success({"status": "ok"}, request)
