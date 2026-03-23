#!/usr/bin/env python3
"""
Startup script for the Agentic Demo backend server.
"""

import uvicorn
import os
import sys
import socket
from pathlib import Path
import httpx

# Disable ChromaDB telemetry globally
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.main import app
from backend.litellm_bootstrap import maybe_bootstrap_litellm


def is_port_open(host: str, port: int, timeout: float = 0.8) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def is_backend_healthy() -> bool:
    try:
        with httpx.Client(timeout=1.5) as client:
            r = client.get("http://localhost:8000/health")
        return r.status_code == 200
    except Exception:
        return False

if __name__ == "__main__":
    print("🚀 Starting Agentic Demo Backend Server...")
    print("📍 Server will be available at: http://localhost:8000")
    print("📚 API documentation at: http://localhost:8000/docs")
    print("🔧 Admin interface at: http://localhost:3000/admin")
    print("🌐 Demo page at: http://localhost:3000")
    print("\n" + "="*50)

    if is_port_open("localhost", 8000):
        if is_backend_healthy():
            print("ℹ️ Backend already running on http://localhost:8000; exiting without starting a duplicate server.")
            sys.exit(0)
        print("❌ Port 8000 is in use by a non-demo process. Free the port and retry.")
        sys.exit(1)

    maybe_bootstrap_litellm(Path(__file__).resolve().parent)
    
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

