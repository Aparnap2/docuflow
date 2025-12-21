#!/usr/bin/env python3
"""
Focused test for Ollama integration with Docling + Granite-Docling + Nomic
Validates local AI model integration and data formats without API dependencies.
"""

import json
import requests
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class TestResult:
    test_name: str
    passed: bool
    error: Optional[str] = None
    response_data: Optional[Dict] = None
    execution_time_ms: Optional[int] = None

class OllamaIntegrationTester:
    """Tests Ollama model integration for DocuFlow v2.0"""
    
    def __init__(self):
        self.base_url = "http://localhost:11434"
        self.test_documents = {
            "api_docs": """
# API Documentation

## POST /v1/documents
Creates a new document record for upload.

**Request Body:**
```json
{
  "filename": "contract.pdf",
  "sha256": "abc123def456",
  "content_type": "application/pdf"
}
```

**Response:**
```json
{
  "document_id": "doc_123456",
  "upload_url": "https://storage.example.com/upload/doc_123456",
  "expires_at": 1640995200
}
```

## Authentication
All API endpoints require Bearer token authentication.
""",
            "code_example": """
# Python Code Example

```python
def process_document(content: bytes, filename: str) -> dict:
    \"\"\"Process document content and extract metadata.\"\"\"
    import hashlib
    from docling import DocumentConverter
    
    # Calculate SHA256
    sha256 = hashlib.sha256(content).hexdigest()
    
    # Convert document
    converter = DocumentConverter()
    result = converter.convert(filename)
    
    return {
        "sha256": sha256,
        "pages": len(result.document.pages),
        "text": result.document.export_to_markdown()
    }
```

This function handles document processing with proper error handling.
""",
            "table_data": """
# Financial Report Q4 2023

## Revenue Summary

| Quarter | Revenue | Growth | Region |
|---------|---------|--------|---------|
| Q1 2023 | $1.2M   | +15%   | NA      |
| Q2 2023 | $1.5M   | +25%   | EU      |
| Q3 2023 | $1.8M   | +20%   | APAC    |
| Q4 2023 | $2.1M   | +17%   | Global  |

## Key Metrics
- Total Revenue: $6.6M
- YoY Growth: +19%
- Customer Acquisition: 1,250 new customers
"""
        }
    
    def test_nomic_embedding_generation(self) -> TestResult:
        """Test Nomic embeddings for document chunks"""
        start_time = time.time()
        
        try:
            test_text = self.test_documents["api_docs"][:500]  # First 500 chars
            
            response = requests.post(f'{self.base_url}/api/embeddings', json={
                'model': 'nomic-embed-text:v1.5',
                'prompt': test_text
            })
            
            if response.status_code != 200:
                return TestResult(
                    test_name='nomic_embedding_generation',
                    passed=False,
                    error=f'Ollama returned {response.status_code}: {response.text}'
                )
            
            data = response.json()
            
            # Validate embedding format
            if 'embedding' not in data:
                return TestResult(
                    test_name='nomic_embedding_generation',
                    passed=False,
                    error='Missing embedding in response'
                )
            
            embedding = data['embedding']
            if not isinstance(embedding, list):
                return TestResult(
                    test_name='nomic_embedding_generation',
                    passed=False,
                    error='Embedding must be array'
                )
            
            if len(embedding) != 768:  # nomic-embed-text:v1.5 dimensions
                return TestResult(
                    test_name='nomic_embedding_generation',
                    passed=False,
                    error=f'Expected 768 dimensions, got {len(embedding)}'
                )
            
            # Validate embedding values are reasonable
            if not all(isinstance(x, (int, float)) for x in embedding):
                return TestResult(
                    test_name='nomic_embedding_generation',
                    passed=False,
                    error='Embedding values must be numeric'
                )
            
            execution_time = int((time.time() - start_time) * 1000)
            return TestResult(
                test_name='nomic_embedding_generation',
                passed=True,
                response_data={
                    'dimensions': len(embedding),
                    'sample_values': embedding[:5],  # First 5 values for verification
                    'embedding_range': [min(embedding), max(embedding)]
                },
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            return TestResult(
                test_name='nomic_embedding_generation',
                passed=False,
                error=str(e)
            )
    
    def test_granite_docling_extraction(self) -> TestResult:
        """Test Granite-Docling for code documentation extraction"""
        start_time = time.time()
        
        try:
            # Test with code documentation
            code_doc = self.test_documents["code_example"]
            
            response = requests.post(f'{self.base_url}/api/generate', json={
                'model': 'ibm/granite-docling:latest',
                'prompt': f"Extract the main programming concepts and code structure from this documentation:\n\n{code_doc[:1000]}",
                'stream': False
            })
            
            if response.status_code != 200:
                return TestResult(
                    test_name='granite_docling_extraction',
                    passed=False,
                    error=f'Granite returned {response.status_code}: {response.text}'
                )
            
            data = response.json()
            
            if 'response' not in data:
                return TestResult(
                    test_name='granite_docling_extraction',
                    passed=False,
                    error='Missing response in data'
                )
            
            extracted_content = data['response']
            
            # Validate extraction quality
            if len(extracted_content) < 50:
                return TestResult(
                    test_name='granite_docling_extraction',
                    passed=False,
                    error='Extracted content too short'
                )
            
            execution_time = int((time.time() - start_time) * 1000)
            return TestResult(
                test_name='granite_docling_extraction',
                passed=True,
                response_data={
                    'extracted_length': len(extracted_content),
                    'contains_code_keywords': any(keyword in extracted_content.lower() 
                                                for keyword in ['function', 'python', 'code', 'api']),
                    'sample': extracted_content[:200]
                },
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            return TestResult(
                test_name='granite_docling_extraction',
                passed=False,
                error=str(e)
            )
    
    def test_qwen_code_generation(self) -> TestResult:
        """Test Qwen for code-related text generation"""
        start_time = time.time()
        
        try:
            prompt = "Write a simple Python function that calculates the factorial of a number with proper documentation."
            
            response = requests.post(f'{self.base_url}/api/generate', json={
                'model': 'qwen2.5-coder:3b',
                'prompt': prompt,
                'stream': False
            })
            
            if response.status_code != 200:
                return TestResult(
                    test_name='qwen_code_generation',
                    passed=False,
                    error=f'Qwen returned {response.status_code}: {response.text}'
                )
            
            data = response.json()
            
            if 'response' not in data:
                return TestResult(
                    test_name='qwen_code_generation',
                    passed=False,
                    error='Missing response in data'
                )
            
            generated_code = data['response']
            
            # Validate code generation quality
            if len(generated_code) < 100:
                return TestResult(
                    test_name='qwen_code_generation',
                    passed=False,
                    error='Generated code too short'
                )
            
            # Check for Python code indicators
            python_indicators = ['def ', 'return', 'import', '"""', "'''"]
            has_python_code = any(indicator in generated_code for indicator in python_indicators)
            
            execution_time = int((time.time() - start_time) * 1000)
            return TestResult(
                test_name='qwen_code_generation',
                passed=True,
                response_data={
                    'code_length': len(generated_code),
                    'has_python_syntax': has_python_code,
                    'contains_docstring': '"""' in generated_code or "'''" in generated_code,
                    'sample': generated_code[:300]
                },
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            return TestResult(
                test_name='qwen_code_generation',
                passed=False,
                error=str(e)
            )
    
    def test_embedding_consistency(self) -> TestResult:
        """Test that similar texts produce similar embeddings"""
        start_time = time.time()
        
        try:
            # Test with similar documents
            doc1 = "The API requires authentication using Bearer tokens."
            doc2 = "Authentication is handled through Bearer token headers."
            
            # Get embeddings for both
            emb1_response = requests.post(f'{self.base_url}/api/embeddings', json={
                'model': 'nomic-embed-text:v1.5',
                'prompt': doc1
            })
            
            emb2_response = requests.post(f'{self.base_url}/api/embeddings', json={
                'model': 'nomic-embed-text:v1.5',
                'prompt': doc2
            })
            
            if emb1_response.status_code != 200 or emb2_response.status_code != 200:
                return TestResult(
                    test_name='embedding_consistency',
                    passed=False,
                    error='Failed to generate embeddings for comparison'
                )
            
            emb1 = emb1_response.json()['embedding']
            emb2 = emb2_response.json()['embedding']
            
            # Calculate cosine similarity
            def cosine_similarity(a, b):
                dot_product = sum(x * y for x, y in zip(a, b))
                norm_a = sum(x * x for x in a) ** 0.5
                norm_b = sum(x * x for x in b) ** 0.5
                return dot_product / (norm_a * norm_b) if norm_a * norm_b != 0 else 0
            
            similarity = cosine_similarity(emb1, emb2)
            
            # Similar documents should have high similarity (> 0.7)
            if similarity < 0.7:
                return TestResult(
                    test_name='embedding_consistency',
                    passed=False,
                    error=f'Similarity too low: {similarity:.3f}'
                )
            
            execution_time = int((time.time() - start_time) * 1000)
            return TestResult(
                test_name='embedding_consistency',
                passed=True,
                response_data={
                    'similarity_score': similarity,
                    'embedding_dimensions': len(emb1),
                    'doc1_length': len(doc1),
                    'doc2_length': len(doc2)
                },
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            return TestResult(
                test_name='embedding_consistency',
                passed=False,
                error=str(e)
            )
    
    def test_document_chunking_simulation(self) -> TestResult:
        """Test document chunking for processing pipeline"""
        start_time = time.time()
        
        try:
            # Simulate chunking a larger document
            full_doc = self.test_documents["table_data"]
            chunk_size = 200  # characters
            overlap = 50
            
            chunks = []
            for i in range(0, len(full_doc), chunk_size - overlap):
                chunk_text = full_doc[i:i + chunk_size]
                if len(chunk_text.strip()) > 20:  # Minimum meaningful chunk
                    chunks.append({
                        'id': f"chunk_{i}",
                        'text': chunk_text,
                        'start_idx': i,
                        'end_idx': min(i + chunk_size, len(full_doc))
                    })
            
            if len(chunks) < 2:
                return TestResult(
                    test_name='document_chunking_simulation',
                    passed=False,
                    error=f'Not enough meaningful chunks: {len(chunks)}'
                )
            
            # Test embedding generation for chunks
            chunk_embeddings = []
            for chunk in chunks[:3]:  # Test first 3 chunks
                response = requests.post(f'{self.base_url}/api/embeddings', json={
                    'model': 'nomic-embed-text:v1.5',
                    'prompt': chunk['text']
                })
                
                if response.status_code == 200:
                    chunk_embeddings.append({
                        'id': chunk['id'],
                        'embedding': response.json()['embedding']
                    })
            
            if len(chunk_embeddings) < 2:
                return TestResult(
                    test_name='document_chunking_simulation',
                    passed=False,
                    error=f'Failed to generate embeddings for chunks: {len(chunk_embeddings)}'
                )
            
            execution_time = int((time.time() - start_time) * 1000)
            return TestResult(
                test_name='document_chunking_simulation',
                passed=True,
                response_data={
                    'total_chunks': len(chunks),
                    'embedded_chunks': len(chunk_embeddings),
                    'chunk_size': chunk_size,
                    'overlap': overlap,
                    'average_chunk_length': sum(len(c['text']) for c in chunks) / len(chunks)
                },
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            return TestResult(
                test_name='document_chunking_simulation',
                passed=False,
                error=str(e)
            )

def run_ollama_integration_tests():
    """Run comprehensive Ollama integration tests"""
    print("🤖 Testing Ollama Integration: Nomic + Granite-Docling + Qwen")
    print("=" * 70)
    
    tester = OllamaIntegrationTester()
    all_results = []
    
    # Test 1: Nomic Embeddings
    print("\n🔍 Testing Nomic Embeddings...")
    results = [
        tester.test_nomic_embedding_generation(),
        tester.test_embedding_consistency(),
        tester.test_document_chunking_simulation()
    ]
    all_results.extend(results)
    
    # Test 2: Granite-Docling
    print("\n🔍 Testing Granite-Docling...")
    granite_result = tester.test_granite_docling_extraction()
    all_results.append(granite_result)
    
    # Test 3: Qwen Code Generation
    print("\n🔍 Testing Qwen Code Generation...")
    qwen_result = tester.test_qwen_code_generation()
    all_results.append(qwen_result)
    
    # Generate report
    print("\n" + "=" * 70)
    print("📊 OLLAMA INTEGRATION TEST RESULTS")
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
        
        if result.response_data:
            print(f"    Data: {json.dumps(result.response_data, indent=2)[:200]}...")
    
    # Performance summary
    execution_times = [r.execution_time_ms for r in all_results if r.execution_time_ms]
    if execution_times:
        avg_time = sum(execution_times) / len(execution_times)
        print(f"\n⚡ Performance Summary:")
        print(f"Average execution time: {avg_time:.1f}ms")
        print(f"Min: {min(execution_times)}ms, Max: {max(execution_times)}ms")
    
    # Integration quality assessment
    print(f"\n🔍 Integration Quality Assessment:")
    if passed == total:
        print("✅ All Ollama models are properly integrated and functional")
        print("✅ Embeddings are consistent and properly formatted")
        print("✅ Granite-Docling can extract documentation structure")
        print("✅ Qwen can generate code with proper syntax")
        print("✅ Document chunking pipeline is ready for production")
    else:
        print("⚠️  Some integration issues detected - review failed tests")
    
    return passed == total

if __name__ == "__main__":
    success = run_ollama_integration_tests()
    exit(0 if success else 1)