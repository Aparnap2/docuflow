"""
LLM Service - Handles interactions with both Ollama (local) and Groq (production) APIs
Implements robust error handling, JSON repair, and timeout management
"""
import os
import json
import re
import requests
import time
from typing import Dict, Any, Optional
from requests.exceptions import RequestException, Timeout, ConnectionError


class OllamaClient:
    """Client for interacting with Ollama API"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model_name = os.getenv("LLM_MODEL_NAME", "ministral-3:3b")
        
    def chat_completions_create(self, messages: list, response_format: dict = None, timeout: int = 45):
        """
        Generate chat completions using Ollama API
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            response_format: Optional response format specification
            timeout: Request timeout in seconds (default: 45s to handle model loading)
            
        Returns:
            Response object with choices
            
        Raises:
            ConnectionError: If cannot connect to Ollama
            Timeout: If request times out
            ValueError: If model is not found or other API errors
        """
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": messages,
        }
        
        if response_format:
            payload["format"] = response_format.get("type", "json")
        
        headers = {"Content-Type": "application/json"}
        
        try:
            # First attempt with normal timeout
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=timeout
            )
            
            # Check for model not found (404)
            if response.status_code == 404:
                raise ValueError(
                    f"❌ Model '{self.model_name}' not found. "
                    f"Run `ollama pull {self.model_name}` first."
                )
            
            # Check for other errors
            response.raise_for_status()
            
            return response.json()
            
        except Timeout:
            # On timeout, retry once with longer timeout for model loading
            try:
                print("⚠️ First attempt timed out. Retrying with longer timeout...")
                response = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=60  # Longer timeout for model loading
                )
                response.raise_for_status()
                return response.json()
            except Timeout:
                raise Timeout(
                    f"Request to Ollama timed out after {timeout} seconds. "
                    "Is Ollama running at {self.base_url}?"
                )
        
        except ConnectionError as e:
            raise ConnectionError(
                f"Could not connect to Ollama. Is it running at {self.base_url}?"
            ) from e
        
        except RequestException as e:
            raise ValueError(f"Ollama API request failed: {str(e)}") from e


class GroqClient:
    """Client for interacting with Groq API"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("Groq API key is required")
        self.model_name = os.getenv("LLM_MODEL_NAME", "llama3-70b-8192")
        
    def chat_completions_create(self, messages: list, response_format: dict = None, timeout: int = 20):
        """
        Generate chat completions using Groq API
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            response_format: Optional response format specification
            timeout: Request timeout in seconds (default: 20s)
            
        Returns:
            Response object with choices
        """
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model_name,
            "messages": messages,
        }
        
        if response_format:
            payload["response_format"] = response_format
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
            
        except RequestException as e:
            raise ValueError(f"Groq API request failed: {str(e)}") from e


def get_client():
    """
    Get the appropriate LLM client based on DEV_MODE environment variable
    
    Returns:
        OllamaClient or GroqClient instance
    """
    dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"
    
    if dev_mode:
        print("🔧 Running in DEV MODE with Ollama")
        return OllamaClient()
    else:
        print("🚀 Running in PROD MODE with Groq")
        return GroqClient()


def extract_json(markdown_text: str, schema: str, max_retries: int = 1) -> Dict[str, Any]:
    """
    Extract structured JSON from markdown text using LLM
    
    Args:
        markdown_text: The markdown content to extract from
        schema: The schema/type of extraction (e.g., "invoice", "balance_sheet")
        max_retries: Maximum number of retries for JSON repair (default: 1)
        
    Returns:
        Dictionary containing extracted data
        
    Raises:
        ValueError: If extraction fails after all retries
    """
    if not markdown_text or len(markdown_text.strip()) < 20:
        print("⚠️ Warning: Markdown text is too short or empty")
        return {"status": "no_data_found"}
    
    client = get_client()
    
    prompt = f"""
Extract {schema} data from the following markdown document:

{markdown_text}

Return only a valid JSON object with the extracted information.
Do not include any explanations, code blocks, or markdown formatting.
"""
    
    messages = [{"role": "user", "content": prompt}]
    response_format = {"type": "json_object"}
    
    # Try to get a response from the LLM
    try:
        response = client.chat_completions_create(
            messages=messages,
            response_format=response_format
        )
        
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        if not content:
            return {"status": "no_data_found"}
        
        # Try to parse the JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # JSON repair strategy
            return _repair_json(content, max_retries)
            
    except (ConnectionError, Timeout) as e:
        raise ValueError(f"LLM connection failed: {str(e)}")
    except ValueError as e:
        raise ValueError(f"LLM extraction failed: {str(e)}")


def _repair_json(json_string: str, max_retries: int) -> Dict[str, Any]:
    """
    Attempt to repair malformed JSON using regex and retry logic
    
    Args:
        json_string: The potentially malformed JSON string
        max_retries: Maximum number of repair attempts
        
    Returns:
        Parsed JSON dictionary
        
    Raises:
        ValueError: If JSON cannot be repaired after max_retries
    """
    if not json_string:
        raise ValueError("Empty JSON string")
    
    for attempt in range(max_retries + 1):
        try:
            # Try direct parsing first
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            if attempt >= max_retries:
                raise ValueError(f"JSON repair failed after {max_retries} attempts: {str(e)}")
            
            # Try to extract JSON object using regex (more robust pattern)
            # Match from first { to last } (non-greedy first, then greedy to get everything)
            match = re.search(r'\{.*?\}', json_string, re.DOTALL)
            if match:
                json_string = match.group()
                # Try to fix common issues like trailing commas
                json_string = json_string.replace(',}', '}').replace(',]', ']')
                continue
            
            # Try to extract JSON array
            match = re.search(r'\[.*?\]', json_string, re.DOTALL)
            if match:
                json_string = match.group()
                json_string = json_string.replace(',}', '}').replace(',]', ']')
                continue
            
            # If no JSON-like structure found, return empty dict
            print(f"⚠️ Warning: Could not extract JSON structure (attempt {attempt + 1})")
            return {}
    
    return {}


def validate_extraction_result(result: Dict[str, Any], schema: str) -> bool:
    """
    Validate that the extraction result contains expected fields
    
    Args:
        result: The extracted data dictionary
        schema: The schema/type of extraction
        
    Returns:
        True if validation passes, False otherwise
    """
    # Basic validation - check if result is a dictionary
    if not isinstance(result, dict):
        return False
    
    # Check for common fields based on schema
    if schema == "invoice":
        required_fields = ["invoice_number", "total_amount"]
    elif schema == "balance_sheet":
        required_fields = ["total_assets", "total_liabilities"]
    else:
        required_fields = []
    
    found_fields = [field for field in required_fields if field in result]
    
    # Consider valid if at least one required field is found or if no specific schema
    return len(found_fields) > 0 or len(required_fields) == 0
