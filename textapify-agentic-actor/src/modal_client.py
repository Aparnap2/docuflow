import httpx
import asyncio
from typing import Dict, Any, Optional

class ModalClient:
    """
    Client for interacting with the Modal OCR service
    """
    
    def __init__(self, modal_url: Optional[str] = None, timeout: int = 120):
        self.modal_url = modal_url
        self.timeout = timeout
        self.http_client = httpx.AsyncClient(timeout=timeout)
    
    async def process_document(self, pdf_url: str) -> Dict[str, Any]:
        """
        Process a document using the Modal OCR service
        """
        if not self.modal_url:
            return {
                "error": "No Modal URL provided",
                "markdown": None
            }
        
        payload = {
            "pdf_url": pdf_url
        }
        
        try:
            response = await self.http_client.post(
                self.modal_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "markdown": result.get("markdown"),
                    "status": result.get("status")
                }
            else:
                return {
                    "success": False,
                    "error": f"Modal request failed with status {response.status_code}: {response.text}",
                    "markdown": None
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Modal request exception: {str(e)}",
                "markdown": None
            }
    
    async def close(self):
        """
        Close the HTTP client
        """
        await self.http_client.aclose()
    
    def __del__(self):
        """
        Cleanup on deletion
        """
        try:
            # Attempt to close the client if it's still open
            if hasattr(self, 'http_client') and not self.http_client.is_closed:
                # In a real implementation, we'd handle this more gracefully
                pass
        except Exception:
            pass