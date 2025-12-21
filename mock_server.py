#!/usr/bin/env python3
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

class MockHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/v1/projects':
            self.send_response(201)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "id": "test-project-123",
                "name": "Test Project",
                "status": "active",
                "created_at": "2024-01-01T00:00:00Z"
            }
            self.wfile.write(json.dumps(response).encode())
        elif self.path == '/v1/documents':
            self.send_response(201)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "id": "test-doc-123",
                "status": "processing",
                "message": "Document uploaded successfully"
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

def start_server():
    server = HTTPServer(('localhost', 8787), MockHandler)
    server.serve_forever()

if __name__ == '__main__':
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    print("Mock server started on port 8787")
    import time
    time.sleep(3600)  # Keep alive for 1 hour
