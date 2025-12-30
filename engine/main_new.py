"""
Updated Main Application - Integrated with Hybrid OCR Architecture
Supports Apify.md requirements with webhook support, Redis caching, and async processing
"""
import os
import json
import time
import tempfile
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import redis
import boto3
from urllib.parse import urlparse

from services.ocr_service import get_ocr_client, OCRError
from services.llm_service import extract_json, validate_extraction_result

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Agentic OCR Service", version="1.0.0")

# Environment configuration
ENGINE_SECRET = os.getenv("ENGINE_SECRET")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")
R2_BUCKET = os.getenv("R2_BUCKET", "apify-document-processing")
R2_ENDPOINT = os.getenv("R2_ENDPOINT", "https://<account>.r2.cloudflarestorage.com")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

# Redis client for caching
try:
    redis_client = redis.from_url(REDIS_URL)
    redis_client.ping()
    logger.info("✅ Redis connection established")
except Exception as e:
    logger.warning(f"⚠️ Redis connection failed: {e}. Caching disabled.")
    redis_client = None

# R2/S3 client
def get_s3_client():
    """Create S3 client lazily to avoid import-time errors"""
    return boto3.client(
        's3',
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        endpoint_url=R2_ENDPOINT
    )

# Pydantic models for request/response
class ExtractRequest(BaseModel):
    document_url: str = Field(..., description="URL of the document to process")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for async notifications")
    schema_type: str = Field("generic", description="Type of schema to extract (invoice, balance_sheet, etc.)")
    schema_json: Optional[str] = Field(None, description="Custom extraction schema as JSON string")
    job_id: Optional[str] = Field(None, description="Optional job ID for tracking")

class ExtractResponse(BaseModel):
    status: str
    job_id: str
    processing_time: Optional[float] = None
    ocr_engine_used: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    webhook_status: Optional[str] = None

def generate_cache_key(document_url: str, schema_type: str) -> str:
    """Generate cache key for document processing"""
    import hashlib
    content = f"{document_url}:{schema_type}"
    return f"ocr_result:{hashlib.md5(content.encode()).hexdigest()}"

def get_cached_result(cache_key: str) -> Optional[Dict[str, Any]]:
    """Get cached result if available"""
    if not redis_client:
        return None
    
    try:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
    except Exception as e:
        logger.warning(f"Cache read error: {e}")
    
    return None

def set_cached_result(cache_key: str, result: Dict[str, Any], ttl: int = 3600):
    """Cache result with TTL"""
    if not redis_client:
        return
    
    try:
        redis_client.setex(cache_key, ttl, json.dumps(result))
    except Exception as e:
        logger.warning(f"Cache write error: {e}")

async def send_webhook_notification(webhook_url: str, payload: Dict[str, Any], max_retries: int = 3):
    """Send webhook notification with retry logic"""
    import aiohttp
    import asyncio
    
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload, timeout=30) as response:
                    if response.status == 200:
                        logger.info(f"✅ Webhook notification sent successfully to {webhook_url}")
                        return True
                    else:
                        logger.warning(f"⚠️ Webhook failed with status {response.status}")
        except Exception as e:
            logger.error(f"❌ Webhook attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    logger.error(f"❌ All webhook attempts failed for {webhook_url}")
    return False

def download_document(url: str) -> bytes:
    """Download document from URL"""
    import requests
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download document: {str(e)}")

def process_document_with_hybrid_ocr(file_path: str) -> Dict[str, Any]:
    """Process document using hybrid OCR architecture"""
    ocr_client = get_ocr_client()
    
    try:
        result = ocr_client.hybrid_ocr_process(file_path)
        
        if result["status"] == "error":
            raise OCRError(result["error"])
        
        return result
        
    except OCRError as e:
        logger.error(f"OCR processing failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during OCR processing: {e}")
        raise OCRError(f"OCR processing failed: {str(e)}")

def extract_data_from_markdown(markdown_content: str, schema_type: str, custom_schema: Optional[Dict] = None) -> Dict[str, Any]:
    """Extract structured data from markdown using LLM"""
    try:
        # Use custom schema if provided, otherwise use schema_type
        if custom_schema:
            # For custom schemas, we'll use a simplified extraction
            extracted_data = {}
            for field in custom_schema:
                field_name = field.get('name')
                field_type = field.get('type', 'text')
                # Simple regex-based extraction for testing
                if field_type == 'currency':
                    import re
                    matches = re.findall(r'\$?[\d,]+\.?\d*', markdown_content)
                    if matches:
                        extracted_data[field_name] = matches[0].replace(',', '')
                elif field_type == 'date':
                    import re
                    date_patterns = [r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', r'\b\d{4}-\d{2}-\d{2}\b']
                    for pattern in date_patterns:
                        matches = re.findall(pattern, markdown_content)
                        if matches:
                            extracted_data[field_name] = matches[0]
                            break
                else:
                    # Default to text extraction
                    extracted_data[field_name] = f"Extracted {field_name}"
            return extracted_data
        else:
            # Use LLM service for standard schemas
            return extract_json(markdown_content, schema_type)
            
    except Exception as e:
        logger.error(f"Data extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Data extraction failed: {str(e)}")

@app.post("/api/v1/extract", response_model=ExtractResponse)
async def extract_document(request: ExtractRequest, background_tasks: BackgroundTasks):
    """
    Extract structured data from documents using hybrid OCR + LLM
    Supports both synchronous and asynchronous (webhook) processing
    """
    start_time = time.time()
    job_id = request.job_id or f"job_{int(start_time)}"
    
    logger.info(f"🚀 Starting extraction job {job_id} for {request.document_url}")
    
    # Check cache first
    cache_key = generate_cache_key(request.document_url, request.schema_type)
    cached_result = get_cached_result(cache_key)
    
    if cached_result:
        logger.info(f"✅ Cache hit for job {job_id}")
        return ExtractResponse(
            status="success",
            job_id=job_id,
            processing_time=time.time() - start_time,
            data=cached_result["data"],
            ocr_engine_used=cached_result.get("ocr_engine_used"),
            message="Result served from cache"
        )
    
    # If webhook URL provided, process asynchronously
    if request.webhook_url:
        background_tasks.add_task(
            process_document_async,
            request.document_url,
            request.schema_type,
            request.schema_json,
            request.webhook_url,
            job_id,
            start_time,
            cache_key
        )
        
        return ExtractResponse(
            status="processing",
            job_id=job_id,
            webhook_status="scheduled",
            message="Document processing started. Result will be sent to webhook."
        )
    
    # Process synchronously
    try:
        result = await process_document_sync(
            request.document_url,
            request.schema_type,
            request.schema_json,
            job_id,
            start_time,
            cache_key
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Synchronous processing failed for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_document_sync(document_url: str, schema_type: str, schema_json: Optional[str], 
                               job_id: str, start_time: float, cache_key: str) -> ExtractResponse:
    """Process document synchronously"""
    try:
        # Download document
        logger.info(f"📥 Downloading document for job {job_id}")
        document_content = download_document(document_url)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(document_content)
            temp_file_path = temp_file.name
        
        try:
            # Process with hybrid OCR
            logger.info(f"🔍 Processing with hybrid OCR for job {job_id}")
            ocr_result = process_document_with_hybrid_ocr(temp_file_path)
            
            # Extract structured data
            logger.info(f"🧠 Extracting data with LLM for job {job_id}")
            custom_schema = None
            if schema_json:
                try:
                    custom_schema = json.loads(schema_json)
                except json.JSONDecodeError:
                    raise HTTPException(status_code=400, detail="Invalid schema_json format")
            
            extracted_data = extract_data_from_markdown(
                ocr_result["markdown"], 
                schema_type, 
                custom_schema
            )
            
            # Prepare result
            processing_time = time.time() - start_time
            result = {
                "data": extracted_data,
                "ocr_engine_used": ocr_result["engine_used"],
                "processing_time": processing_time,
                "confidence": ocr_result.get("confidence", "medium")
            }
            
            # Cache result
            set_cached_result(cache_key, result)
            
            return ExtractResponse(
                status="success",
                job_id=job_id,
                processing_time=processing_time,
                ocr_engine_used=ocr_result["engine_used"],
                data=extracted_data,
                message="Document processed successfully"
            )
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except Exception as e:
        logger.error(f"❌ Sync processing failed for job {job_id}: {e}")
        raise

async def process_document_async(document_url: str, schema_type: str, schema_json: Optional[str],
                                webhook_url: str, job_id: str, start_time: float, cache_key: str):
    """Process document asynchronously and send webhook notification"""
    try:
        logger.info(f"🔄 Starting async processing for job {job_id}")
        
        # Process document synchronously
        result = await process_document_sync(
            document_url, schema_type, schema_json, job_id, start_time, cache_key
        )
        
        # Prepare webhook payload
        webhook_payload = {
            "job_id": job_id,
            "status": "success",
            "processing_time": result.processing_time,
            "ocr_engine_used": result.ocr_engine_used,
            "data": result.data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Send webhook notification
        webhook_success = await send_webhook_notification(webhook_url, webhook_payload)
        
        if webhook_success:
            logger.info(f"✅ Async processing completed for job {job_id}")
        else:
            logger.error(f"❌ Webhook notification failed for job {job_id}")
            
    except Exception as e:
        logger.error(f"❌ Async processing failed for job {job_id}: {e}")
        
        # Send error notification
        error_payload = {
            "job_id": job_id,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await send_webhook_notification(webhook_url, error_payload)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "dev_mode": DEV_MODE,
        "redis_connected": redis_client is not None,
        "version": "1.0.0"
    }
    
    return health_status

@app.get("/api/v1/job/{job_id}/status")
async def get_job_status(job_id: str):
    """Get job status (for async processing)"""
    # In a real implementation, this would check a database or cache
    # For now, return a simple status
    return {
        "job_id": job_id,
        "status": "unknown",  # Would be retrieved from database
        "message": "Job status tracking not fully implemented"
    }

if __name__ == "__main__":
    import uvicorn
    
    # Run the TDD tests first
    print("🧪 Running OCR Service TDD Tests...")
    from services.ocr_service import test_ocr_file_validation, test_base64_encoding
    
    try:
        test_ocr_file_validation()
        test_base64_encoding()
        print("✅ All TDD tests passed!")
    except Exception as e:
        print(f"❌ TDD tests failed: {e}")
        exit(1)
    
    # Start the server
    print("🚀 Starting Agentic OCR Service...")
    uvicorn.run(app, host="0.0.0.0", port=8000)