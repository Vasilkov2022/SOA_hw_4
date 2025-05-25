from fastapi import FastAPI, Request
import uvicorn
import os
import requests
from fastapi.responses import JSONResponse, Response

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:8001")
POST_URL = os.getenv("POST_API_URL",      "http://api_post_service:8002")

app = FastAPI(
    title="Proxy Service",
    version="1.0.0"
)

ROUTES = {
    "users": os.getenv("USER_SERVICE_URL"),
    "auth":  USER_SERVICE_URL,
    "posts": os.getenv("POST_API_URL"),
}



@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(full_path: str, request: Request):
    prefix = full_path.split("/")[0]
    upstream = ROUTES.get(prefix)
    if not upstream:
        return JSONResponse(status_code=404, content={"detail": "Unknown resource"})

    url = f"{upstream}/{full_path}"
    resp = requests.request(
        request.method,
        url,
        headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
        data=await request.body(),
        timeout=15,
    )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers={"Content-Type": resp.headers.get("Content-Type", "application/json")},
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)