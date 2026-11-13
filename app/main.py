"""Microservice « payment-api » : catalogue, checkout lent, endpoint flaky."""
import asyncio
import os
import random
import time

from fastapi import FastAPI, HTTPException, Request, Response
from opentelemetry import trace
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

from .telemetry import setup_logging, setup_telemetry

log = setup_logging()
tracer = trace.get_tracer("payment-api")
app = FastAPI(title="payment-api", version="1.0.0")
setup_telemetry(app)

# --- Métriques RED (buckets alignés sur le SLO : 0.2 s) -----------------------
REQUESTS = Counter(
    "http_requests_total", "Requêtes HTTP", ["method", "path", "status"]
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "Latence HTTP",
    ["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1, 2, 5),
)

PRODUCTS = {
    1: {"id": 1, "name": "Clavier", "price": 49.9},
    2: {"id": 2, "name": "Souris", "price": 19.9},
    3: {"id": 3, "name": "Écran 27\"", "price": 249.0},
}
CURRENCIES = {"EUR", "USD", "TND"}


def _cfg_float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


class CheckoutRequest(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=100)
    currency: str = "EUR"


@app.middleware("http")
async def observe(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        path = route.path if route else "unmatched"
        elapsed = time.perf_counter() - start
        REQUESTS.labels(request.method, path, str(status)).inc()
        LATENCY.labels(request.method, path).observe(elapsed)
        log.info(
            "request",
            extra={"fields": {"method": request.method, "path": path,
                              "status": status, "duration_ms": round(elapsed * 1000, 2)}},
        )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/products")
def list_products():
    return list(PRODUCTS.values())


@app.get("/products/{product_id}")
def get_product(product_id: int):
    product = PRODUCTS.get(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="produit introuvable")
    return product


@app.post("/checkout")
async def checkout(req: CheckoutRequest):
    """Traitement lent simulé (50–150 ms par défaut)."""
    if req.currency not in CURRENCIES:
        raise HTTPException(status_code=422, detail="devise non supportée")
    product = PRODUCTS.get(req.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="produit introuvable")
    with tracer.start_as_current_span("process_payment") as span:
        delay = random.uniform(
            _cfg_float("CHECKOUT_MIN_DELAY", 0.05), _cfg_float("CHECKOUT_MAX_DELAY", 0.15)
        )
        await asyncio.sleep(delay)
        total = round(product["price"] * req.quantity, 2)
        span.set_attribute("order.total", total)
        log.info("checkout ok", extra={"fields": {"total": total}})
    return {"status": "paid", "total": total, "currency": req.currency}


@app.get("/flaky")
def flaky():
    """Erreurs intermittentes (taux configurable via FLAKY_ERROR_RATE)."""
    if random.random() < _cfg_float("FLAKY_ERROR_RATE", 0.3):
        log.error("flaky failure")
        raise HTTPException(status_code=503, detail="service temporairement indisponible")
    return {"status": "ok"}
