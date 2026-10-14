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

WINDOW = 10
LIMIT = 10

requests_by_client = defaultdict(deque)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response


@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    origin = request.headers.get("origin")

    if request.method == "OPTIONS":
        response = Response(status_code=204)
    else:
        response = await call_next(request)

    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = (
            "X-Request-ID, X-Client-Id, Content-Type"
        )
        response.headers["Vary"] = "Origin"

    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path != "/ping":
        return await call_next(request)

    client_id = request.headers.get("X-Client-Id", "default")
    now = time.monotonic()
    bucket = requests_by_client[client_id]

    while bucket and now - bucket[0] >= WINDOW:
        bucket.popleft()

    if len(bucket) >= LIMIT:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
        )

    bucket.append(now)
    return await call_next(request)


@app.get("/ping")
async def ping(request: Request):
    return {
        "email": EMAIL,
        "request_id": request.state.request_id,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))