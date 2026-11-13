import json
import logging
import sys

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.telemetry import JsonFormatter

client = TestClient(app)


@pytest.fixture(autouse=True)
def fast_checkout(monkeypatch):
    monkeypatch.setenv("CHECKOUT_MIN_DELAY", "0")
    monkeypatch.setenv("CHECKOUT_MAX_DELAY", "0")


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_list_products():
    r = client.get("/products")
    assert r.status_code == 200 and len(r.json()) == 3


def test_get_product_ok_and_404():
    assert client.get("/products/1").json()["name"] == "Clavier"
    assert client.get("/products/999").status_code == 404


def test_checkout_nominal():
    r = client.post("/checkout", json={"product_id": 2, "quantity": 3})
    assert r.status_code == 200
    assert r.json() == {"status": "paid", "total": 59.7, "currency": "EUR"}


@pytest.mark.parametrize("qty", [0, 101, -1])
def test_checkout_quantity_limits(qty):
    assert client.post("/checkout", json={"product_id": 1, "quantity": qty}).status_code == 422


def test_checkout_boundary_quantities():
    for qty in (1, 100):
        assert client.post("/checkout", json={"product_id": 1, "quantity": qty}).status_code == 200


def test_checkout_unknown_product():
    assert client.post("/checkout", json={"product_id": 42, "quantity": 1}).status_code == 404


def test_checkout_bad_currency():
    r = client.post("/checkout", json={"product_id": 1, "quantity": 1, "currency": "XXX"})
    assert r.status_code == 422


def test_flaky_failure_and_success(monkeypatch):
    monkeypatch.setattr(main.random, "random", lambda: 0.0)
    assert client.get("/flaky").status_code == 503
    monkeypatch.setattr(main.random, "random", lambda: 0.99)
    assert client.get("/flaky").status_code == 200


def test_flaky_rate_configurable(monkeypatch):
    monkeypatch.setenv("FLAKY_ERROR_RATE", "0")
    assert all(client.get("/flaky").status_code == 200 for _ in range(20))


def test_metrics_exposed_after_traffic():
    client.get("/products")
    client.get("/inconnu")
    body = client.get("/metrics").text
    assert "http_requests_total" in body
    assert 'path="/products"' in body
    assert 'path="unmatched"' in body
    assert "http_request_duration_seconds_bucket" in body


def test_json_log_format_has_trace_fields():
    record = logging.LogRecord("x", logging.INFO, "f", 1, "hello", None, None)
    record.fields = {"k": "v"}
    data = json.loads(JsonFormatter().format(record))
    assert data["message"] == "hello" and data["k"] == "v"
    assert "trace_id" in data and "span_id" in data


def test_json_log_includes_exception():
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord("x", logging.ERROR, "f", 1, "err", None, sys.exc_info())
    assert "ValueError" in json.loads(JsonFormatter().format(record))["exception"]
