"""
ColabBot Bootstrap Registry — FastAPI application
--------------------------------------------------
Start locally:
    uvicorn app.main:app --reload

Swagger UI: http://localhost:8000/docs
"""

import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, SessionLocal, engine
from .models import Agent
from .routers import agents, tasks

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("colabbot.registry")

# Agents are marked offline after this many seconds without a heartbeat
# (3 missed heartbeats at 30s interval = 90s)
OFFLINE_THRESHOLD_SECONDS = int(os.getenv("OFFLINE_THRESHOLD_SECONDS", "90"))
HEARTBEAT_CHECK_INTERVAL = 10  # seconds between checks


def _heartbeat_monitor():
    """Background thread: mark agents as offline when heartbeats stop."""
    while True:
        time.sleep(HEARTBEAT_CHECK_INTERVAL)
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=OFFLINE_THRESHOLD_SECONDS)
            db = SessionLocal()
            stale = (
                db.query(Agent)
                .filter(Agent.status != "offline", Agent.last_heartbeat < cutoff)
                .all()
            )
            for agent in stale:
                log.info("Agent %s (%s) went offline — last heartbeat: %s", agent.agent_id, agent.name, agent.last_heartbeat)
                agent.status = "offline"
            if stale:
                db.commit()
            db.close()
        except Exception as e:
            log.error("Heartbeat monitor error: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables
    Base.metadata.create_all(bind=engine)
    log.info("Database ready.")

    # Start background heartbeat monitor
    monitor = threading.Thread(target=_heartbeat_monitor, daemon=True)
    monitor.start()
    log.info("Heartbeat monitor started (offline threshold: %ss).", OFFLINE_THRESHOLD_SECONDS)

    yield

    log.info("Registry shutting down.")


app = FastAPI(
    title="ColabBot Registry",
    description="Bootstrap registry for the ColabBot peer-to-peer AI agent network.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router, prefix="/v1")
app.include_router(tasks.router, prefix="/v1")


@app.get("/", tags=["meta"])
def root():
    return {
        "name": "ColabBot Registry",
        "version": "0.1.0",
        "docs": "/docs",
        "spec": "https://github.com/colabbot-com/colabbot/blob/main/PROTOCOL.md",
    }


@app.get("/health", tags=["meta"])
def health(db=None):
    from .database import SessionLocal
    from .models import Agent, Task
    db = SessionLocal()
    agents_online = db.query(Agent).filter(Agent.status != "offline").count()
    tasks_total = db.query(Task).count()
    db.close()
    return {"status": "ok", "agents_online": agents_online, "tasks_total": tasks_total}
