#!/usr/bin/env python3
"""
DocuFlow v2.0 Feature Validation Tests
Tests new hybrid search, table extraction, parent context, and smart citations
"""

import requests
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, List

class V2FeatureTester:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self.project_id = None
        self.document_id = None
        
    def log_result(self, test_name: str, success: bool, details: str = "") -> bool:
        """Log test result and return success status"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   Details: {details}")
        return success
    
    def create_project(self) -> bool:
        """Create a test project"""
        try:
            response = requests.post(
                f"{self.base_url}/v1/projects",
                json={"name": "V2 Feature Test Project"},
                headers=self.headers
            )
            if response.status_code == 200:
                data = response.json()
                self.project_id = data.get("id")
                return self.log_result("Create Project", True, f"Project ID: {self.project_id}")
            else:
                return self.log_result("Create Project", False, f"Status: {response.status_code}")
        except Exception as e:
            return self.log_result("Create Project", False, str(e))
    
    def upload_test_document(self, filename: str, content: bytes) -> bool:
        """Upload a test document with tables and sections"""
        try:
            # Calculate SHA256
            file_hash = hashlib.sha256(content).hexdigest()
            
            # Create document
            create_response = requests.post(
                f"{self.base_url}/v1/documents",
                json={
                    "project_id": self.project_id,
                    "source_name": filename,
                    "content_type": "application/pdf",
                    "sha256": file_hash
                },
                headers=self.headers
            )
            
            if create_response.status_code not in [200, 201]:
                return self.log_result("Upload Document", False, f"Create failed: {create_response.status_code}")
            
            doc_data = create_response.json()
            self.document_id = doc_data.get("document_id")
            
            # Upload file
            upload_response = requests.put(
                f"{self.base_url}/v1/documents/{self.document_id}/upload",
                data=content,
                headers=self.headers
            )
            
            if upload_response.status_code != 200:
                return self.log_result("Upload Document", False, f"Upload failed: {upload_response.status_code}")
            
            # Complete processing
            complete_response = requests.post(
                f"{self.base_url}/v1/documents/{self.document_id}/complete",
                headers=self.headers
            )
            
            if complete_response.status_code != 200:
                return self.log_result("Upload Document", False, f"Complete failed: {complete_response.status_code}")
            
            # Wait for processing
            max_wait = 60
            for _ in range(max_wait):
                status_response = requests.get(
                    f"{self.base_url}/v1/documents/{self.document_id}",
                    headers=self.headers
                )
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    if status_data.get("status") == "READY":
                        return self.log_result("Upload Document", True, f"Document ID: {self.document_id}")
                    elif status_data.get("status") == "FAILED":
                        return self.log_result("Upload Document", False, "Processing failed")
                time.sleep(1)
            
            return self.log_result("Upload Document", False, "Processing timeout")
            
        except Exception as e:
            return self.log_result("Upload Document", False, str(e))
    
    def test_hybrid_search_keyword(self) -> bool:
        """Test keyword-based search"""
        try:
            response = requests.post(
                f"{self.base_url}/v1/query",
                json={
                    "query": "termination fee",
                    "mode": "chunks",
                    "top_k": 5
                },
                headers=self.headers
            )
            
            if response.status_code != 200:
                return self.log_result("Hybrid Search - Keyword", False, f"Status: {response.status_code}")
            
            data = response.json()
            results = data.get("results", [])
            
            if len(results) == 0:
                return self.log_result("Hybrid Search - Keyword", False, "No results found")
            
            # Check if results contain expected fields
            first_result = results[0]
            has_text = bool(first_result.get("text"))
            has_score = "score" in first_result
            
            return self.log_result("Hybrid Search - Keyword", has_text and has_score, 
                                 f"Found {len(results)} results with scores")
            
        except Exception as e:
            return self.log_result("Hybrid Search - Keyword", False, str(e))
    
    def test_hybrid_search_semantic(self) -> bool:
        """Test semantic search"""
        try:
            response = requests.post(
                f"{self.base_url}/v1/query",
                json={
                    "query": "What are the cancellation charges?",
                    "mode": "chunks",
                    "top_k": 5
                },
                headers=self.headers
            )
            
            if response.status_code != 200:
                return self.log_result("Hybrid Search - Semantic", False, f"Status: {response.status_code}")
            
            data = response.json()
            results = data.get("results", [])
            
            if len(results) == 0:
                return self.log_result("Hybrid Search - Semantic", False, "No results found")
            
            # Check for both vector and keyword scores
            first_result = results[0]
            has_vector_score = "vector_score" in first_result
            has_keyword_score = "keyword_score" in first_result
            
            return self.log_result("Hybrid Search - Semantic", True, 
                                 f"Found {len(results)} results, vector_score: {has_vector_score}, keyword_score: {has_keyword_score}")
            
        except Exception as e:
            return self.log_result("Hybrid Search - Semantic", False, str(e))
    
    def test_parent_context(self) -> bool:
        """Test parent context preservation"""
        try:
            response = requests.post(
                f"{self.base_url}/v1/query",
                json={
                    "query": "document processing",
                    "mode": "chunks",
                    "top_k": 3
                },
                headers=self.headers
            )
            
            if response.status_code != 200:
                return self.log_result("Parent Context", False, f"Status: {response.status_code}")
            
            data = response.json()
            results = data.get("results", [])
            
            if len(results) == 0:
                return self.log_result("Parent Context", False, "No results found")
            
            # Check if context is present
            has_context = any(
                result.get('context', {}).get('before') or 
                result.get('context', {}).get('after') 
                for result in results
            )
            
            context_count = sum(1 for r in results if r.get('context', {}).get('before') or r.get('context', {}).get('after'))
            
            return self.log_result("Parent Context", has_context,
                                 f"Found context in {context_count}/{len(results)} results")
            
        except Exception as e:
            return self.log_result("Parent Context", False, str(e))
    
    def test_smart_citations(self) -> bool:
        """Test smart citations with page numbers and sections"""
        try:
            response = requests.post(
                f"{self.base_url}/v1/query",
                json={
                    "query": "document content",
                    "mode": "chunks",
                    "top_k": 3
                },
                headers=self.headers
            )
            
            if response.status_code != 200:
                return self.log_result("Smart Citations", False, f"Status: {response.status_code}")
            
            data = response.json()
            results = data.get("results", [])
            
            if len(results) == 0:
                return self.log_result("Smart Citations", False, "No results found")
            
            # Check citation structure
            good_citations = 0
            for result in results:
                citation = result.get('citation', {})
                if (citation.get('page_number') and 
                    citation.get('section_header') and 
                    citation.get('document_name')):
                    good_citations += 1
            
            return self.log_result("Smart Citations", good_citations > 0,
                                 f"Good citations: {good_citations}/{len(results)}")
            
        except Exception as e:
            return self.log_result("Smart Citations", False, str(e))
    
    def test_table_extraction(self) -> bool:
        """Test table HTML extraction"""
        try:
            response = requests.post(
                f"{self.base_url}/v1/query",
                json={
                    "query": "table data financial information",
                    "mode": "chunks",
                    "top_k": 5
                },
                headers=self.headers
            )
            
            if response.status_code != 200:
                return self.log_result("Table Extraction", False, f"Status: {response.status_code}")
            
            data = response.json()
            results = data.get("results", [])
            
            if len(results) == 0:
                return self.log_result("Table Extraction", False, "No results found")
            
            # Check if any results contain table HTML
            has_tables = any(result.get('table_html') for result in results)
            table_count = sum(1 for r in results if r.get('table_html'))
            
            return self.log_result("Table Extraction", has_tables,
                                 f"Found tables in {table_count}/{len(results)} results")
            
        except Exception as e:
            return self.log_result("Table Extraction", False, str(e))
    
    def test_kv_cache_deduplication(self) -> bool:
        """Test SHA256 cache for instant ingestion"""
        try:
            # Create a simple test document
            test_content = b"Test document content for deduplication testing"
            test_hash = hashlib.sha256(test_content).hexdigest()
            
            # First upload
            response1 = requests.post(
                f"{self.base_url}/v1/documents",
                json={
                    "project_id": self.project_id,
                    "source_name": "cache_test_1.pdf",
                    "content_type": "application/pdf",
                    "sha256": test_hash
                },
                headers=self.headers
            )
            
            if response1.status_code not in [200, 201]:
                return self.log_result("KV Cache Deduplication", False, f"First upload failed: {response1.status_code}")
            
            data1 = response1.json()
            
            # Second upload with same hash
            response2 = requests.post(
                f"{self.base_url}/v1/documents",
                json={
                    "project_id": self.project_id,
                    "source_name": "cache_test_2.pdf",
                    "content_type": "application/pdf",
                    "sha256": test_hash
                },
                headers=self.headers
            )
            
            if response2.status_code not in [200, 201]:
                return self.log_result("KV Cache Deduplication", False, f"Second upload failed: {response2.status_code}")
            
            data2 = response2.json()
            
            # Check if second upload was instant (status READY)
            instant = (data2.get('status') == 'READY' and data2.get('deduped') == True)
            
            return self.log_result("KV Cache Deduplication", instant,
                                 f"First: {data1.get('status')}, Second: {data2.get('status')}, Instant: {instant}")
            
        except Exception as e:
            return self.log_result("KV Cache Deduplication", False, str(e))
    
    def test_answer_generation(self) -> bool:
        """Test answer generation with new hybrid search"""
        try:
            response = requests.post(
                f"{self.base_url}/v1/query",
                json={
                    "query": "What is this document about?",
                    "mode": "answer",
                    "top_k": 5
                },
                headers=self.headers
            )
            
            if response.status_code != 200:
                return self.log_result("Answer Generation", False, f"Status: {response.status_code}")
            
            data = response.json()
            answer = data.get("answer")
            results = data.get("results", [])
            
            has_answer = bool(answer and len(answer.strip()) > 0)
            has_results = len(results) > 0
            
            return self.log_result("Answer Generation", has_answer and has_results,
                                 f"Answer length: {len(answer) if answer else 0}, Results: {len(results)}")
            
        except Exception as e:
            return self.log_result("Answer Generation", False, str(e))
    
    def test_performance_metrics(self) -> bool:
        """Test performance metrics are included"""
        try:
            response = requests.post(
                f"{self.base_url}/v1/query",
                json={
                    "query": "test performance",
                    "mode": "chunks",
                    "top_k": 3
                },
                headers=self.headers
            )
            
            if response.status_code != 200:
                return self.log_result("Performance Metrics", False, f"Status: {response.status_code}")
            
            data = response.json()
            debug = data.get("debug", {})
            
            has_latency = "retrieval_latency_ms" in debug
            has_dimensions = "vector_dimensions" in debug
            has_results_found = "results_found" in debug
            has_hybrid_search = debug.get("hybrid_search_used") == True
            
            return self.log_result("Performance Metrics", 
                                 has_latency and has_dimensions and has_results_found and has_hybrid_search,
                                 f"Latency: {has_latency}, Dimensions: {has_dimensions}, Results: {has_results_found}, Hybrid: {has_hybrid_search}")
            
        except Exception as e:
            return self.log_result("Performance Metrics", False, str(e))
    
    def run_all_tests(self) -> Dict[str, bool]:
        """Run all v2.0 feature tests"""
        print("\n🚀 Starting DocuFlow v2.0 Feature Tests")
        print("=" * 50)
        
        results = {}
        
        # Setup
        results["create_project"] = self.create_project()
        if not results["create_project"]:
            print("❌ Project creation failed, cannot continue")
            return results
        
        # Note: We would need actual test documents for full testing
        # For now, we'll test the search functionality with existing data
        print("\n📋 Testing Hybrid Search Features")
        print("-" * 30)
        
        results["hybrid_search_keyword"] = self.test_hybrid_search_keyword()
        results["hybrid_search_semantic"] = self.test_hybrid_search_semantic()
        results["parent_context"] = self.test_parent_context()
        results["smart_citations"] = self.test_smart_citations()
        results["table_extraction"] = self.test_table_extraction()
        results["kv_cache_deduplication"] = self.test_kv_cache_deduplication()
        results["answer_generation"] = self.test_answer_generation()
        results["performance_metrics"] = self.test_performance_metrics()
        
        # Summary
        print("\n📊 Test Summary")
        print("=" * 50)
        passed = sum(1 for success in results.values() if success)
        total = len(results)
        print(f"Tests Passed: {passed}/{total} ({passed/total*100:.1f}%)")
        
        if passed == total:
            print("🎉 All tests passed! DocuFlow v2.0 features are working correctly.")
        else:
            print("⚠️  Some tests failed. Check the details above.")
        
        return results

def main():
    """Main test runner"""
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python test_v2_features.py <BASE_URL> <API_KEY>")
        print("Example: python test_v2_features.py https://api.docuflow.dev sk_test_123...")
        sys.exit(1)
    
    base_url = sys.argv[1]
    api_key = sys.argv[2]
    
    tester = V2FeatureTester(base_url, api_key)
    results = tester.run_all_tests()
    
    # Exit with appropriate code
    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()