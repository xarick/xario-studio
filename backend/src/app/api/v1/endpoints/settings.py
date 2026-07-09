from fastapi import APIRouter, Depends
from app.api.v1.deps import require_admin
from app.core.config import settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/ai")
def get_ai_settings(_=Depends(require_admin)):
    return {
        "provider": settings.AI_PROVIDER,
        "model": settings.AI_MODEL,
        "base_url": settings.AI_BASE_URL or "",
    }
