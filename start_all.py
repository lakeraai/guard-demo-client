#!/usr/bin/env python3
"""
Startup script for the complete Agentic Demo application.
Starts both backend and frontend services.
"""

import subprocess
import sys
import os
import time
import signal
import threading
import socket
import urllib.request
from pathlib import Path

def print_banner():
    print("=" * 60)
    print("🚀 AGENTIC DEMO - COMPLETE APPLICATION")
    print("=" * 60)
    print("📍 Demo Page: http://localhost:3000")
    print("🔧 Admin Console: http://localhost:3000/admin")
    print("📚 API Docs: http://localhost:8000/docs")
    print("🌐 Backend API: http://localhost:8000")
    print("=" * 60)
    print()

def check_dependencies():
    """Check if required dependencies are installed."""
    print("🔍 Checking dependencies...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        return False
    
    # Check if requirements.txt exists
    if not Path("requirements.txt").exists():
        print("❌ requirements.txt not found")
        return False
    
    # Check if package.json exists
    if not Path("package.json").exists():
        print("❌ package.json not found")
        return False
    
    print("✅ Dependencies check passed")
    return True

def install_backend_deps():
    """Install backend dependencies if needed."""
    print("📦 Installing backend dependencies...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True, capture_output=True)
        print("✅ Backend dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install backend dependencies: {e}")
        return False

def install_frontend_deps():
    """Install frontend dependencies if needed."""
    print("📦 Installing frontend dependencies...")
    try:
        subprocess.run(["npm", "install"], check=True, capture_output=True)
        print("✅ Frontend dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install frontend dependencies: {e}")
        return False

def start_backend():
    """Start the backend server."""
    print("🚀 Starting backend server...")
    try:
        # Import and run the backend
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from backend.main import app
        import uvicorn
        import logging
        
        # Configure logging to avoid blocking I/O issues
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Disable uvicorn access logging to reduce stdout contention
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=False  # Disable access logging to prevent blocking I/O
        )
    except KeyboardInterrupt:
        print("\n🛑 Backend server stopped")
    except Exception as e:
        print(f"❌ Backend server failed: {e}")


def is_port_open(host: str, port: int, timeout: float = 0.8) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def is_backend_healthy() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:8000/health", timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


def is_frontend_reachable() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:3000", timeout=1.5) as r:
            return r.status < 500
    except Exception:
        return False

def start_frontend():
    """Start the frontend development server."""
    print("🚀 Starting frontend server...")
    try:
        subprocess.run(["npm", "run", "dev","--", "--host", "0.0.0.0"], check=True)
       # subprocess.run(["npm", "run", "dev", ], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Frontend server stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Frontend server failed: {e}")

def main():
    """Main startup function."""
    print_banner()
    
    if not check_dependencies():
        print("❌ Dependency check failed. Please ensure all files are present.")
        sys.exit(1)
    
    # Install dependencies if needed
    if not install_backend_deps():
        print("❌ Backend dependency installation failed.")
        sys.exit(1)
    
    if not install_frontend_deps():
        print("❌ Frontend dependency installation failed.")
        sys.exit(1)

    from backend.litellm_bootstrap import maybe_bootstrap_litellm

    maybe_bootstrap_litellm(Path(__file__).resolve().parent)
    
    print("\n🎯 Starting services...")
    print("Press Ctrl+C to stop all services\n")

    backend_started_by_script = False
    backend_thread = None
    backend_port_in_use = is_port_open("localhost", 8000)
    if backend_port_in_use and is_backend_healthy():
        print("ℹ️ Backend already running on http://localhost:8000; reusing existing server")
    elif backend_port_in_use:
        print("❌ Port 8000 is in use by a non-demo process. Free the port and retry.")
        sys.exit(1)
    else:
        backend_thread = threading.Thread(target=start_backend, daemon=True)
        backend_thread.start()
        backend_started_by_script = True
        time.sleep(3)

    frontend_port_in_use = is_port_open("localhost", 3000)
    if frontend_port_in_use and is_frontend_reachable():
        print("ℹ️ Frontend already running on http://localhost:3000; reusing existing server")
        if backend_started_by_script and backend_thread:
            try:
                backend_thread.join()
            except KeyboardInterrupt:
                print("\n🛑 Shutting down...")
                sys.exit(0)
        return
    if frontend_port_in_use:
        print("❌ Port 3000 is in use by a non-demo process. Free the port and retry.")
        sys.exit(1)

    try:
        start_frontend()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        sys.exit(0)

if __name__ == "__main__":
    main()

