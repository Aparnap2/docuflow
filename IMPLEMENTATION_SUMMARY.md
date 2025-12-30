# Apify Implementation Summary

## Overview
This implementation completes the transformation of the DocuFlow codebase to fully support the Apify architecture as specified in `apify.md`. The system now supports a hybrid OCR/LLM pipeline with robust error handling, fallback mechanisms, and comprehensive testing.

## Key Features Implemented

### 1. Environment Configuration
- **DEV_MODE**: Toggle between local development (Ollama) and production (Groq)
- **OLLAMA_BASE_URL**: Configured to `http://localhost:11434` for local development
- **LLM_MODEL_NAME**: `ministral-3:3b` for development, `llama3-70b-8192` for production
- **OCR_MODEL_NAME**: `deepseek-ocr:3b` for OCR processing

### 2. LLM Service Architecture

#### services/llm_service.py
- **OllamaClient**: Handles local Ollama API calls with:
  - 45-second timeout (with retry for model loading)
  - Automatic retry on timeout (once with 60s timeout)
  - 404 model missing error handling with helpful message
  - Connection error handling with friendly error messages

- **GroqClient**: Handles production Groq API calls with:
  - 20-second timeout
  - API key validation
  - Error handling for API failures

- **get_client()**: Factory function that returns appropriate client based on DEV_MODE

- **extract_json()**: Main extraction function that:
  - Validates input text length (minimum 20 characters)
  - Calls appropriate LLM client
  - Implements JSON repair strategy for malformed responses
  - Returns structured data or error status

- **_repair_json()**: JSON repair function that:
  - Attempts direct JSON parsing first
  - Uses regex to extract JSON objects/arrays from text
  - Handles common issues like trailing commas, missing braces
  - Returns empty dict if repair fails

- **validate_extraction_result()**: Validates extracted data against schema requirements

### 3. Main Application Updates

#### engine/main.py
- Updated to import and use `extract_json` and `validate_extraction_result` from llm_service
- Added schema_type extraction from request data
- Implemented hybrid extraction approach:
  - Primary: LLM-based extraction using new service
  - Fallback: Regex-based extraction if LLM fails or validation fails
- Added `ocr_engine_used` field to response
- Maintains backward compatibility with existing regex extraction

### 4. Error Handling & Resilience

#### Input Validation
- Empty text detection (returns `{"status": "no_data_found"}`)
- Short text detection (returns `{"status": "no_data_found"}`)
- Garbage character detection (returns empty dict)

#### Network & Connection Errors
- ConnectionError: Friendly message indicating Ollama/Groq is not running
- Timeout: Automatic retry once with longer timeout for model loading
- 404 Model Missing: Specific error message with instruction to pull model

#### JSON Parsing Errors
- Regex-based JSON extraction from text
- Automatic repair of common JSON issues
- Graceful degradation when repair fails

### 5. Testing Suite

#### test_json_repair.py (11 tests)
- Valid JSON parsing
- Missing closing brace repair
- Missing opening brace repair
- Trailing comma repair
- Extra text before/after JSON
- Empty string handling
- Completely invalid JSON
- Nested JSON structures
- JSON with newlines
- Multiple JSON objects

#### test_llm_service.py (13 tests)
- DEV_MODE client selection
- PROD_MODE client selection
- Ollama connection error handling
- Ollama timeout retry logic
- Ollama model not found (404)
- Empty text extraction
- Short text extraction
- Invoice validation
- Invalid result validation
- Generic schema validation
- Groq API key requirement
- Mock LLM extraction
- Malformed JSON repair

#### test_integration.py (8 tests)
- Network failure graceful degradation
- Bad JSON recovery
- Empty OCR output handling
- Very short OCR output (hallucination check)
- OCR with garbage characters
- Model loading timeout
- DEV_MODE toggle
- Fallback to regex extraction

**Total: 32 tests, all passing**

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (FastAPI)                     │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    Document Processing                       │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐  │
│  │  Docling OCR   │    │  DeepSeek OCR  │    │  LLM        │  │
│  │ (Granite)      │───▶│ (Fallback)     │───▶│ Extraction  │  │
│  └─────────────────┘    └─────────────────┘    └─────────────┘  │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    LLM Service Layer                        │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  get_client() → OllamaClient or GroqClient              │  │
│  └─────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  extract_json() → JSON with repair fallback            │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    Response                                │
│  {                                                           │
│    "status": "completed",                                    │
│    "ocr_engine_used": "granite-docling",                     │
│    "result": { ... },                                        │
│    "confidence": 0.9,                                        │
│    "metrics": { ... }                                        │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

### Development Mode (.env)
```
DEV_MODE=true
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL_NAME=ministral-3:3b
OCR_MODEL_NAME=deepseek-ocr:3b
```

### Production Mode (.env)
```
DEV_MODE=false
GROQ_API_KEY=your-groq-api-key-here
MODAL_TOKEN=your-modal-token-here
```

## Requirements

Added `json-repair` package to requirements.txt for additional JSON repair capabilities.

## Testing

Run all tests:
```bash
cd engine
python3 tests/test_json_repair.py
python3 tests/test_llm_service.py
python3 tests/test_integration.py
```

## Deployment

### Local Development
1. Install Ollama: https://ollama.com/
2. Pull models:
   ```bash
   ollama pull ministral-3:3b
   ollama pull deepseek-ocr:3b
   ```
3. Set `DEV_MODE=true` in .env
4. Run: `uvicorn main:app --reload`

### Production
1. Set `DEV_MODE=false` in .env
2. Configure `GROQ_API_KEY` and `MODAL_TOKEN`
3. Deploy to Apify platform

## Validation Checklist

- [x] DEV_MODE toggle implemented
- [x] Ollama/Groq client selection
- [x] JSON repair strategy with regex fallback
- [x] Timeout handling (45s Ollama, 20s Groq)
- [x] Model loading timeout retry
- [x] 404 model missing error handling
- [x] Empty text detection
- [x] Short text detection (hallucination check)
- [x] Garbage character handling
- [x] Connection error handling
- [x] Comprehensive test suite (32 tests)
- [x] All tests passing
- [x] Git cleanup completed

## Files Modified/Created

### Modified
- `engine/.env` - Added LLM/OCR configuration
- `engine/main.py` - Integrated LLM service
- `engine/requirements.txt` - Added json-repair
- `apify.md` - Updated documentation

### Created
- `engine/services/llm_service.py` - Complete LLM service implementation
- `engine/services/__init__.py` - Service package initializer
- `engine/tests/test_json_repair.py` - JSON repair tests
- `engine/tests/test_llm_service.py` - LLM service tests
- `engine/tests/test_integration.py` - Integration tests

## Next Steps

1. Deploy to Apify platform
2. Set up Modal for OCR processing (DeepSeek fallback)
3. Configure Redis cache for API responses
4. Set up webhook processing for async operations
5. Implement rate limiting and authentication
6. Add monitoring and logging

## References

- [Apify Documentation](https://docs.apify.com/)
- [Ollama Documentation](https://ollama.com/)
- [Groq API Documentation](https://console.groq.com/docs)
- [DeepSeek OCR](https://huggingface.co/deepseek-ai/DeepSeek-VL)
