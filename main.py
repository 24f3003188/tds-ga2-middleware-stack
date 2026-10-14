import os
import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
import uvicorn

app = FastAPI()

EMAIL = os.getenv("EMAIL", "YOUR_LOGGED_IN_EMAIL")

ALLOWED_ORIGINS = {
    "https://app-jjp99d.example.com",
    "https://exam.sanand.workers.dev",
}

LIMIT = 10
WINDOW = 10
buckets = defaultdict(deque)


@app.middleware("http")
async def combined_middleware(request: Request, call_next):
    # 1. Request context
    request_id = request.headers.get("X-Request-ID")
    if request_id is None:
        request_id = str(uuid.uuid4())

    request.state.request_id = request_id

    # 2. CORS preflight
    origin = request.headers.get("Origin")

    if request.method == "OPTIONS" and origin in ALLOWED_ORIGINS:
        response = Response(status_code=204)

    # 3. Rate limiting
    elif request.url.path == "/ping":
        client_id = request.headers.get("X-Client-Id", "default")
        now = time.monotonic()
        bucket = buckets[client_id]

        while bucket and now - bucket[0] >= WINDOW:
            bucket.popleft()

        if len(bucket) >= LIMIT:
            response = JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
            )
        else:
            bucket.append(now)
            response = await call_next(request)
    else:
        response = await call_next(request)

    # Always echo the request ID, including error/preflight responses
    response.headers["X-Request-ID"] = request_id

    # Only approved origins receive CORS headers
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = (
            "X-Request-ID, X-Client-Id, Content-Type"
        )
        response.headers["Vary"] = "Origin"

    return response


@app.get("/ping")
async def ping(request: Request):
    return {
        "email": EMAIL,
        "request_id": request.state.request_id,
    }


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )