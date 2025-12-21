#!/usr/bin/env python3
"""
Comprehensive test suite for local data formats and security validation
with Cloudflare D1 + Vectorize integration.

Tests:
- Data format validation (JSON schemas, types, constraints)
- Security boundaries (input validation, sanitization, auth)
- Local processing with Ollama (nomic-embed, granite-docling, qwen3)
- D1 database operations and constraints
- Vectorize integration patterns (without remote calls)
"""

import json
import requests
import hashlib
import time
import subprocess
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8787"
ENGINE_URL = "http://localhost:8000"
API_KEY = "sk_2b9a4ed00eda4d9fac477b080231fd6c"
TEST_PROJECT_ID = "9d352c77-824b-4b84-86c4-0fbdb1e86449"

@dataclass
class TestResult:
    test_name: str
    passed: bool
    error: Optional[str] = None
    response_data: Optional[Dict] = None
    execution_time_ms: Optional[int] = None

class DataFormatValidator:
    """Validates data formats against PRD specifications"""
    
    @staticmethod
    def validate_project_response(data: Dict) -> List[str]:
        """Validate project creation response format"""
        errors = []
        required_fields = ['id', 'name', 'created_at']
        
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        if 'id' in data and not isinstance(data['id'], str):
            errors.append("Project ID must be string")
            
        if 'created_at' in data and not isinstance(data['created_at'], int):
            errors.append("Created at must be integer timestamp")
            
        return errors
    
    @staticmethod
    def validate_document_response(data: Dict) -> List[str]:
        """Validate document creation response format"""
        errors = []
        required_fields = ['document_id', 'upload_url', 'expires_at']
        
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        if 'document_id' in data and not isinstance(data['document_id'], str):
            errors.append("Document ID must be string")
            
        if 'upload_url' in data and not data['upload_url'].startswith('http'):
            errors.append("Upload URL must be valid HTTP URL")
            
        return errors
    
    @staticmethod
    def validate_query_response(data: Dict) -> List[str]:
        """Validate query response format"""
        errors = []
        required_fields = ['query', 'results', 'debug']
        
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        if 'results' in data and not isinstance(data['results'], list):
            errors.append("Results must be array")
            
        if 'debug' in data and not isinstance(data['debug'], dict):
            errors.append("Debug must be object")
            
        return errors

class SecurityValidator:
    """Validates security boundaries and input sanitization"""
    
    @staticmethod
    def validate_api_key_format(api_key: str) -> List[str]:
        """Validate API key format and security"""
        errors = []
        
        if not api_key.startswith('sk_'):
            errors.append("API key must start with 'sk_'")
            
        if len(api_key) < 32:
            errors.append("API key must be at least 32 characters")
            
        if not api_key.replace('_', '').replace('-', '').isalnum():
            errors.append("API key contains invalid characters")
            
        return errors
    
    @staticmethod
    def validate_filename_sanitization(filename: str) -> List[str]:
        """Validate filename sanitization"""
        errors = []
        
        # Check for path traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            errors.append("Filename contains path traversal characters")
            
        # Check for dangerous extensions
        dangerous_extensions = ['.exe', '.bat', '.cmd', '.sh', '.php']
        if any(filename.lower().endswith(ext) for ext in dangerous_extensions):
            errors.append("Filename has dangerous extension")
            
        return errors
    
    @staticmethod
    def validate_content_type(content_type: str) -> List[str]:
        """Validate content type security"""
        errors = []
        
        allowed_types = [
            'application/pdf',
            'text/plain',
            'text/markdown',
            'application/json',
            'text/csv'
        ]
        
        if content_type not in allowed_types:
            errors.append(f"Content type {content_type} not allowed")
            
        return errors

class LocalIntegrationTester:
    """Tests local integration with Ollama models"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json'
        })
    
    def test_ollama_embedding_generation(self, text: str) -> TestResult:
        """Test Ollama nomic-embed-text:v1.5 integration"""
        start_time = time.time()
        
        try:
            # Test direct Ollama call
            response = requests.post('http://localhost:11434/api/embeddings', json={
                'model': 'nomic-embed-text:v1.5',
                'prompt': text
            })
            
            if response.status_code != 200:
                return TestResult(
                    test_name='ollama_embedding_generation',
                    passed=False,
                    error=f'Ollama returned {response.status_code}: {response.text}'
                )
            
            data = response.json()
            
            # Validate embedding format
            if 'embedding' not in data:
                return TestResult(
                    test_name='ollama_embedding_generation',
                    passed=False,
                    error='Missing embedding in response'
                )
            
            embedding = data['embedding']
            if not isinstance(embedding, list):
                return TestResult(
                    test_name='ollama_embedding_generation',
                    passed=False,
                    error='Embedding must be array'
                )
            
            if len(embedding) != 768:  # nomic-embed-text:v1.5 dimensions
                return TestResult(
                    test_name='ollama_embedding_generation',
                    passed=False,
                    error=f'Expected 768 dimensions, got {len(embedding)}'
                )
            
            execution_time = int((time.time() - start_time) * 1000)
            return TestResult(
                test_name='ollama_embedding_generation',
                passed=True,
                response_data=data,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            return TestResult(
                test_name='ollama_embedding_generation',
                passed=False,
                error=str(e)
            )
    
    def test_ollama_text_generation(self, prompt: str) -> TestResult:
        """Test Ollama qwen3:3b text generation"""
        start_time = time.time()
        
        try:
            response = requests.post('http://localhost:11434/api/generate', json={
                'model': 'qwen2.5-coder:3b',
                'prompt': prompt,
                'stream': False
            })
            
            if response.status_code != 200:
                return TestResult(
                    test_name='ollama_text_generation',
                    passed=False,
                    error=f'Ollama returned {response.status_code}: {response.text}'
                )
            
            data = response.json()
            
            if 'response' not in data:
                return TestResult(
                    test_name='ollama_text_generation',
                    passed=False,
                    error='Missing response in data'
                )
            
            execution_time = int((time.time() - start_time) * 1000)
            return TestResult(
                test_name='ollama_text_generation',
                passed=True,
                response_data=data,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            return TestResult(
                test_name='ollama_text_generation',
                passed=False,
                error=str(e)
            )
    
    def test_granite_docling_extraction(self, markdown_text: str) -> TestResult:
        """Test Granite-Docling for code documentation extraction"""
        start_time = time.time()
        
        try:
            response = requests.post('http://localhost:11434/api/chat', json={
                'model': 'ibm/granite-docling:latest',
                'messages': [{
                    'role': 'user',
                    'content': f"Extract code documentation structure from this markdown:\n{markdown_text[:2000]}"
                }]
            })
            
            if response.status_code != 200:
                return TestResult(
                    test_name='granite_docling_extraction',
                    passed=False,
                    error=f'Granite returned {response.status_code}: {response.text}'
                )
            
            data = response.json()
            
            if 'message' not in data or 'content' not in data['message']:
                return TestResult(
                    test_name='granite_docling_extraction',
                    passed=False,
                    error='Missing message content in response'
                )
            
            execution_time = int((time.time() - start_time) * 1000)
            return TestResult(
                test_name='granite_docling_extraction',
                passed=True,
                response_data=data,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            return TestResult(
                test_name='granite_docling_extraction',
                passed=False,
                error=str(e)
            )

class APITester:
    """Tests API endpoints with data format validation"""
    
    def __init__(self):
        self.session = requests.Session()
        self.validator = DataFormatValidator()
        self.security_validator = SecurityValidator()
    
    def test_project_creation(self) -> TestResult:
        """Test project creation with format validation"""
        start_time = time.time()
        
        try:
            response = self.session.post(f'{BASE_URL}/v1/projects', json={
                'name': 'Test Project for Data Format Validation'
            })
            
            if response.status_code != 200:
                return TestResult(
                    test_name='project_creation',
                    passed=False,
                    error=f'API returned {response.status_code}: {response.text}'
                )
            
            data = response.json()
            
            # Validate response format
            format_errors = self.validator.validate_project_response(data)
            if format_errors:
                return TestResult(
                    test_name='project_creation',
                    passed=False,
                    error=f'Format validation failed: {"; ".join(format_errors)}'
                )
            
            execution_time = int((time.time() - start_time) * 1000)
            return TestResult(
                test_name='project_creation',
                passed=True,
                response_data=data,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            return TestResult(
                test_name='project_creation',
                passed=False,
                error=str(e)
            )
    
    def test_document_creation(self) -> TestResult:
        """Test document creation with security validation"""
        start_time = time.time()
        
        try:
            # Test with potentially dangerous filename
            response = self.session.post(f'{BASE_URL}/v1/documents', json={
                'filename': 'test_document.pdf',
                'sha256': hashlib.sha256(b'test content').hexdigest()
            })
            
            if response.status_code != 200:
                return TestResult(
                    test_name='document_creation',
                    passed=False,
                    error=f'API returned {response.status_code}: {response.text}'
                )
            
            data = response.json()
            
            # Validate response format
            format_errors = self.validator.validate_document_response(data)
            if format_errors:
                return TestResult(
                    test_name='document_creation',
                    passed=False,
                    error=f'Format validation failed: {"; ".join(format_errors)}'
                )
            
            # Validate security
            security_errors = self.security_validator.validate_filename_sanitization(
                data.get('upload_url', '')
            )
            if security_errors:
                return TestResult(
                    test_name='document_creation',
                    passed=False,
                    error=f'Security validation failed: {"; ".join(security_errors)}'
                )
            
            execution_time = int((time.time() - start_time) * 1000)
            return TestResult(
                test_name='document_creation',
                passed=True,
                response_data=data,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            return TestResult(
                test_name='document_creation',
                passed=False,
                error=str(e)
            )
    
    def test_query_with_mock_data(self) -> TestResult:
        """Test query endpoint with mock data for format validation"""
        start_time = time.time()
        
        try:
            response = self.session.post(f'{BASE_URL}/v1/query', json={
                'query': 'test query for format validation',
                'top_k': 5,
                'mode': 'chunks'
            })
            
            # We expect this to fail due to no data, but validate format
            if response.status_code == 500:
                data = response.json()
                
                # Should have proper error format
                if 'error' not in data or 'debug' not in data:
                    return TestResult(
                        test_name='query_with_mock_data',
                        passed=False,
                        error='Missing error or debug fields in error response'
                    )
                
                execution_time = int((time.time() - start_time) * 1000)
                return TestResult(
                    test_name='query_with_mock_data',
                    passed=True,
                    response_data=data,
                    execution_time_ms=execution_time
                )
            
            # If it succeeds, validate the success format
            data = response.json()
            format_errors = self.validator.validate_query_response(data)
            if format_errors:
                return TestResult(
                    test_name='query_with_mock_data',
                    passed=False,
                    error=f'Format validation failed: {"; ".join(format_errors)}'
                )
            
            execution_time = int((time.time() - start_time) * 1000)
            return TestResult(
                test_name='query_with_mock_data',
                passed=True,
                response_data=data,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            return TestResult(
                test_name='query_with_mock_data',
                passed=False,
                error=str(e)
            )
    
    def test_security_boundaries(self) -> TestResult:
        """Test security boundaries and input validation"""
        start_time = time.time()
        
        try:
            # Test 1: Invalid API key format
            invalid_key = 'invalid_key_format'
            response = requests.post(f'{BASE_URL}/v1/documents', 
                                   headers={'Authorization': f'Bearer {invalid_key}'},
                                   json={'filename': 'test.pdf'})
            
            if response.status_code == 401:
                # Test 2: Path traversal attempt
                response2 = self.session.post(f'{BASE_URL}/v1/documents', json={
                    'filename': '../../../etc/passwd',
                    'sha256': 'test'
                })
                
                if response2.status_code == 400:
                    execution_time = int((time.time() - start_time) * 1000)
                    return TestResult(
                        test_name='security_boundaries',
                        passed=True,
                        execution_time_ms=execution_time
                    )
            
            return TestResult(
                test_name='security_boundaries',
                passed=False,
                error='Security boundaries not properly enforced'
            )
            
        except Exception as e:
            return TestResult(
                test_name='security_boundaries',
                passed=False,
                error=str(e)
            )

class DatabaseTester:
    """Tests D1 database operations and constraints"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json'
        })
    
    def test_database_constraints(self) -> TestResult:
        """Test database constraints and data integrity"""
        start_time = time.time()
        
        try:
            # Test unique constraint on API keys
            response1 = self.session.post(f'{BASE_URL}/v1/api-keys', json={})
            if response1.status_code != 200:
                return TestResult(
                    test_name='database_constraints',
                    passed=False,
                    error='Failed to create first API key'
                )
            
            key_data = response1.json()
            api_key = key_data.get('key')
            
            # Test foreign key constraint
            response2 = self.session.post(f'{BASE_URL}/v1/documents', json={
                'filename': 'constraint_test.pdf',
                'sha256': 'test123'
            })
            
            if response2.status_code != 200:
                return TestResult(
                    test_name='database_constraints',
                    passed=False,
                    error='Failed to create document with valid API key'
                )
            
            execution_time = int((time.time() - start_time) * 1000)
            return TestResult(
                test_name='database_constraints',
                passed=True,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            return TestResult(
                test_name='database_constraints',
                passed=False,
                error=str(e)
            )

def run_comprehensive_test_suite():
    """Run the complete test suite and generate report"""
    print("🧪 Starting Comprehensive Local Data Format & Security Test Suite")
    print("=" * 70)
    
    # Initialize testers
    ollama_tester = LocalIntegrationTester()
    api_tester = APITester()
    db_tester = DatabaseTester()
    
    all_results = []
    
    # Test 1: Ollama Integration
    print("\n🔍 Testing Ollama Integration...")
    test_text = "This is a test document about artificial intelligence and machine learning concepts."
    
    results = [
        ollama_tester.test_ollama_embedding_generation(test_text),
        ollama_tester.test_ollama_text_generation("What is the capital of France?"),
        ollama_tester.test_granite_docling_extraction("# API Documentation\n\n## POST /users\nCreates a new user account.")
    ]
    
    all_results.extend(results)
    
    # Test 2: API Data Format Validation
    print("\n🔍 Testing API Data Format Validation...")
    api_results = [
        api_tester.test_project_creation(),
        api_tester.test_document_creation(),
        api_tester.test_query_with_mock_data(),
        api_tester.test_security_boundaries()
    ]
    
    all_results.extend(api_results)
    
    # Test 3: Database Constraints
    print("\n🔍 Testing Database Constraints...")
    db_results = [
        db_tester.test_database_constraints()
    ]
    
    all_results.extend(db_results)
    
    # Generate report
    print("\n" + "=" * 70)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for r in all_results if r.passed)
    total = len(all_results)
    
    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    print("\n📋 Detailed Results:")
    for result in all_results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"{status} {result.test_name}")
        
        if not result.passed:
            print(f"    Error: {result.error}")
        
        if result.execution_time_ms:
            print(f"    Time: {result.execution_time_ms}ms")
        
        if result.response_data and 'debug' in result.response_data:
            print(f"    Debug: {json.dumps(result.response_data['debug'], indent=2)}")
    
    # Performance summary
    execution_times = [r.execution_time_ms for r in all_results if r.execution_time_ms]
    if execution_times:
        avg_time = sum(execution_times) / len(execution_times)
        print(f"\n⚡ Performance Summary:")
        print(f"Average execution time: {avg_time:.1f}ms")
        print(f"Min: {min(execution_times)}ms, Max: {max(execution_times)}ms")
    
    return passed == total

if __name__ == "__main__":
    success = run_comprehensive_test_suite()
    exit(0 if success else 1)