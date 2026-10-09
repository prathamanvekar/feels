import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routes.auth_routes import router as auth_router
from app.routes.api_routes import router as api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("feels")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure SQLite database tables are ready
    logger.info("Initializing Feels application...")
    init_db()
    logger.info("Local AI model configured: %s (Ollama: %s)", settings.OLLAMA_MODEL, settings.OLLAMA_BASE_URL)
    logger.info("Timezone configured: %s", settings.APP_TIMEZONE)
    yield
    logger.info("Feels application shutdown completed.")

app = FastAPI(
    title="Feels - Outdoor Soundtrack Matcher",
    description="Local open-weight AI that turns your recent Spotify listening history into outdoor destinations in Pune.",
    version="1.0.0",
    lifespan=lifespan
)


# CORS configuration for local safety
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API and Auth routers
app.include_router(auth_router)
app.include_router(api_router)

# Mount static directory for frontend assets
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def serve_index(request: Request):
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Feels API is running. Static frontend not yet compiled."}

@app.get("/app")
async def serve_app(request: Request):
    app_file = os.path.join(static_dir, "app.html")
    if os.path.exists(app_file):
        return FileResponse(app_file)
    return FileResponse(os.path.join(static_dir, "index.html"))

