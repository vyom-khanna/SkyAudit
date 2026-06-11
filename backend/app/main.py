import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import init_db
from app.routers import schools, districts, anomalies, pulse, reports, whatsapp, auth
from app.services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)


def seed_demo_officer():
    """Insert demo officer if not already present."""
    from app.database import SessionLocal
    from app.models import Officer
    from app.routers.auth import hash_password

    db = SessionLocal()
    try:
        existing = db.query(Officer).filter(Officer.email == "demo@schooltruth.in").first()
        if not existing:
            demo = Officer(
                email="demo@schooltruth.in",
                name="Demo Officer",
                role="national_admin",
                district_code=None,
                state_code=None,
                hashed_password=hash_password("demo1234"),
            )
            db.add(demo)
            db.commit()
            logger.info("Demo officer seeded: demo@schooltruth.in / demo1234")
        else:
            logger.info("Demo officer already exists, skipping seed.")
    except Exception as e:
        logger.error(f"Failed to seed demo officer: {e}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("SchoolTruth API starting up...")
    init_db()
    seed_demo_officer()
    start_scheduler()
    yield
    logger.info("SchoolTruth API shutting down...")
    stop_scheduler()


app = FastAPI(
    title="SchoolTruth API",
    description="Satellite-powered government school accountability platform for India",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,https://schooltruth.in,https://www.schooltruth.in"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(schools.router)
app.include_router(districts.router)
app.include_router(anomalies.router)
app.include_router(pulse.router)
app.include_router(reports.router)
app.include_router(whatsapp.router)


@app.get("/", tags=["health"])
def root():
    return {
        "service": "SchoolTruth API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": f"Endpoint {request.url.path} not found"},
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception):
    logger.error(f"Internal error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."},
    )
