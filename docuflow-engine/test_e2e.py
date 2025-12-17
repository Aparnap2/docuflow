import os
import asyncio
import httpx
import pytest
from main import app, process_file
from fastapi.testclient import TestClient
from loguru import logger

# Setup test client
client = TestClient(app)

# Mock callback URL for testing
MOCK_CALLBACK_URL = "http://testserver/callback"

@pytest.fixture
def mock_callback_server():
    # Start a simple HTTP server to receive callbacks
    from threading import Thread
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class CallbackHandler(BaseHTTPRequestHandler):
        received_data = []

        def do_POST(self):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            self.received_data.append(post_data.decode('utf-8'))
            self.send_response(200)
            self.end_headers()
            return post_data

    server = HTTPServer(('localhost', 8123), CallbackHandler)
    thread = Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    
    yield server
    
    server.shutdown()
    thread.join()

@pytest.mark.asyncio
async def test_complete_flow(tmp_path, mock_callback_server):
    """Test complete document processing flow end-to-end"""
    # 1. Create a sample PDF file
    pdf_path = tmp_path / "sample.pdf"
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4\n1 0 obj\n<< /Title (Test Invoice) >>\nendobj\nxref\ntrailer\n<< /Root 1 0 R >>\nstartxref\n%%EOF")
    
    # 2. Create job request
    job = {
        "file_url": f"file://{pdf_path}",
        "callback_url": MOCK_CALLBACK_URL,
        "document_id": "test-doc-123",
        "secret": "test-secret"
    }
    
    # 3. Process the document asynchronously
    task = asyncio.create_task(process_file(job))
    
    # 4. Wait for processing to complete
    try:
        await asyncio.wait_for(task, timeout=120)
    except asyncio.TimeoutError:
        pytest.fail("Processing timed out")
    
    # 5. Verify callback was received
    handler = mock_callback_server.RequestHandlerClass
    assert len(handler.received_data) > 0
    
    # 6. Validate callback content
    callback_data = handler.received_data[0]
    assert "vendor_name" in callback_data
    assert "invoice_date" in callback_data
    assert "total_amount" in callback_data
    
    logger.success("End-to-end test completed successfully")

if __name__ == "__main__":
    pytest.main(["-s", "-v", "test_e2e.py"])