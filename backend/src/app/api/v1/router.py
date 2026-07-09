from fastapi import APIRouter
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.videos import router as videos_router
from app.api.v1.endpoints.shorts import router as shorts_router
from app.api.v1.endpoints.images import router as images_router
from app.api.v1.endpoints.settings import router as settings_router
from app.api.v1.endpoints.notifications import router as notifications_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(videos_router)
api_router.include_router(shorts_router)
api_router.include_router(images_router)
api_router.include_router(settings_router)
api_router.include_router(notifications_router)
