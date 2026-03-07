#!/usr/bin/env python3
"""
Simple HTTP server to view scraped articles
Run: python server.py
Then open http://localhost:8000/articles/index.html
"""

import http.server
import socketserver
import os
import sys
from pathlib import Path

PORT = 8000
HANDLER = http.server.SimpleHTTPRequestHandler

# Change to script directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

print(f"🚀 Starting server at http://localhost:{PORT}")
print(f"📂 Serving files from: {os.getcwd()}")
print(f"📰 View articles at: http://localhost:{PORT}/articles/index.html")
print(f"\nPress Ctrl+C to stop the server\n")

try:
    with socketserver.TCPServer(("", PORT), HANDLER) as httpd:
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\n✓ Server stopped")
    sys.exit(0)
except OSError as e:
    print(f"❌ Error: {e}")
    if "Address already in use" in str(e):
        print(f"Port {PORT} is already in use. Try a different port or kill the process using it.")
    sys.exit(1)
