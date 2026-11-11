"""ParcelOps minimal web application and monitoring endpoints."""
from contextlib import asynccontextmanager
import logging
import time

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Parcel  # registers the model for create_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("parcelops")

ALLOWED_STATUSES = ("Pending", "Validated", "Disputed")

REQUEST_COUNT = Counter(
    "parcelops_http_requests_total",
    "Number of HTTP requests received",
    ["method", "route", "status"],
)
REQUEST_LATENCY = Histogram(
    "parcelops_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Docker Compose waits for PostgreSQL readiness, but retry startup to be safe.
    for attempt in range(1, 11):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database ready; ParcelOps starting")
            break
        except Exception:
            if attempt == 10:
                logger.exception("Database failed to initialize")
                raise
            logger.warning("Database not ready (attempt %s/10)", attempt)
            time.sleep(2)
    yield


app = FastAPI(title="ParcelOps", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.middleware("http")
async def track_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    route_label = route.path if route else "unmatched"
    REQUEST_COUNT.labels(request.method, route_label, str(response.status_code)).inc()
    REQUEST_LATENCY.labels(request.method, route_label).observe(time.perf_counter() - started)
    logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
    return response


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    parcels = db.scalars(select(Parcel).order_by(Parcel.id.desc())).all()
    counts = {
        status: db.scalar(select(func.count(Parcel.id)).where(Parcel.status == status))
        for status in ALLOWED_STATUSES
    }
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "parcels": parcels,
            "counts": counts,
            "statuses": ALLOWED_STATUSES,
            "duplicate": request.query_params.get("error") == "duplicate",
        },
    )


@app.post("/parcels")
def register_parcel(
    parcel_id: str = Form(min_length=1, max_length=50),
    locality: str = Form(min_length=1, max_length=120),
    db: Session = Depends(get_db),
):
    parcel_id = parcel_id.strip()
    locality = locality.strip()
    if not parcel_id or not locality:
        raise HTTPException(status_code=422, detail="Parcel ID and locality are required")
    parcel = Parcel(parcel_id=parcel_id, locality=locality, status="Pending")
    db.add(parcel)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return RedirectResponse(url="/?error=duplicate", status_code=303)
    logger.info("Registered synthetic parcel %s", parcel_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/parcels/{parcel_pk}/status")
def update_status(
    parcel_pk: int,
    new_status: str = Form(...),
    db: Session = Depends(get_db),
):
    if new_status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid verification status")
    parcel = db.get(Parcel, parcel_pk)
    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcel not found")
    parcel.status = new_status
    db.commit()
    logger.info("Updated parcel %s status to %s", parcel.parcel_id, new_status)
    return RedirectResponse(url="/", status_code=303)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        return Response(content='{"status":"error","database":"unavailable"}',
                        status_code=503, media_type="application/json")


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
