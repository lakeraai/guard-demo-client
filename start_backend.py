#!/usr/bin/env python3
"""
Startup script for the Agentic Demo backend server.
"""

import uvicorn
import os
import sys

# Disable ChromaDB telemetry globally
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.main import app

if __name__ == "__main__":
    print("🚀 Starting Agentic Demo Backend Server...")
    print("📍 Server will be available at: http://localhost:8000")
    print("📚 API documentation at: http://localhost:8000/docs")
    print("🔧 Admin interface at: http://localhost:3000/admin")
    print("🌐 Demo page at: http://localhost:3000")
    print("\n" + "="*50)
    
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

