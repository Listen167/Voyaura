from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.errors import install_error_handlers
from app.routers import check_ins, city_memories, health, map_overview, media_uploads, users

app = FastAPI(
    title="Voyaura API",
    version="0.1.0",
    description="Map-first travel memories and Xiaoxi companion API.",
)

install_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(users.router, prefix="/api/v1")
app.include_router(map_overview.router, prefix="/api/v1")
app.include_router(check_ins.router, prefix="/api/v1")
app.include_router(city_memories.router, prefix="/api/v1")
app.include_router(media_uploads.router, prefix="/api/v1")

