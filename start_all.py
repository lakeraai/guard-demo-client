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
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n🛑 Backend server stopped")
    except Exception as e:
        print(f"❌ Backend server failed: {e}")

def start_frontend():
    """Start the frontend development server."""
    print("🚀 Starting frontend server...")
    try:
        subprocess.run(["npm", "run", "dev"], check=True)
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
    
    print("\n🎯 Starting services...")
    print("Press Ctrl+C to stop all services\n")
    
    # Start backend in a separate thread
    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()
    
    # Wait a moment for backend to start
    time.sleep(3)
    
    # Start frontend
    try:
        start_frontend()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        sys.exit(0)

if __name__ == "__main__":
    main()

