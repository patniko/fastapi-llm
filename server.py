import os
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from scheduler import ServiceScheduler
from services.users import router as user_router
from services.webhooks import router as webhooks_router
from services.items import router as items_router
from services.notifications import router as notifications_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    run_scheduler_thread()
    yield
    # Shutdown (if needed)
    pass


app = FastAPI(
    title="FastAPI Template",
    description="A generic FastAPI template with authentication, database, and Kafka integration",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Mounts
app.mount("/static", StaticFiles(directory="static"), name="static")


# Scheduler function
def run_scheduler_thread():
    scheduler = ServiceScheduler()
    scheduler_thread = threading.Thread(target=scheduler.start, daemon=True)
    scheduler_thread.start()


# Include routers
app.include_router(user_router, prefix="/users", tags=["users"])
app.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
app.include_router(items_router, prefix="/items", tags=["items"])
app.include_router(notifications_router, prefix="/notifications", tags=["notifications"])


@app.api_route(
    "/", response_class=HTMLResponse, status_code=200, methods=["GET", "HEAD"]
)
async def load_root():
    return "FastAPI Template - Awake and ready to serve!"


if __name__ == "__main__":
    port = os.getenv("PORT") or 8080
    uvicorn.run(app, host="127.0.0.1", port=int(port))
