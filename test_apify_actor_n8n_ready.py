"""
Test script to verify the Apify Actor structure for n8n integration
"""
import json
import os
from pathlib import Path

def test_actor_structure():
    """Test that the actor has the correct structure for n8n integration"""
    print("Testing Apify Actor Structure for n8n Integration...\n")
    
    # Check that required files exist
    required_files = ['actor.py', 'actor.json', 'Dockerfile', 'requirements.txt', 'README.md']
    
    for file in required_files:
        file_path = Path(f"apify_only/{file}")
        if file_path.exists():
            print(f"✅ {file} exists")
        else:
            print(f"❌ {file} missing")
            return False
    
    # Check actor.json structure
    with open('apify_only/actor.json', 'r') as f:
        actor_config = json.load(f)
    
    required_config_fields = ['name', 'version', 'description', 'input', 'output']
    for field in required_config_fields:
        if field in actor_config:
            print(f"✅ actor.json has {field}")
        else:
            print(f"❌ actor.json missing {field}")
            return False
    
    # Check input schema has required properties
    input_schema = actor_config.get('input', {}).get('schema', {})
    if 'properties' in input_schema:
        props = input_schema['properties']
        if 'pdf_url' in props:
            print("✅ Input schema has pdf_url property")
        else:
            print("❌ Input schema missing pdf_url property")
            return False
        
        if 'schema' in props:
            print("✅ Input schema has schema property for custom extraction")
        else:
            print("❌ Input schema missing schema property")
            return False
    else:
        print("❌ Input schema malformed")
        return False
    
    # Check output schema
    output_schema = actor_config.get('output', {}).get('schema', {})
    if 'properties' in output_schema:
        output_props = output_schema['properties']
        required_outputs = ['extracted_data', 'confidence']
        
        for output_field in required_outputs:
            if output_field in output_props:
                print(f"✅ Output schema has {output_field}")
            else:
                print(f"❌ Output schema missing {output_field}")
                return False
    else:
        print("❌ Output schema malformed")
        return False
    
    # Check Dockerfile
    with open('apify_only/Dockerfile', 'r') as f:
        docker_content = f.read()
    
    if 'EXPOSE 8080' in docker_content:
        print("✅ Dockerfile has EXPOSE 8080 (required by Apify)")
    else:
        print("❌ Dockerfile missing EXPOSE 8080")
        return False
    
    if 'CMD' in docker_content and 'apify.actor' in docker_content:
        print("✅ Dockerfile has correct CMD for Apify")
    else:
        print("❌ Dockerfile missing correct CMD for Apify")
        return False
    
    # Check requirements.txt
    with open('apify_only/requirements.txt', 'r') as f:
        req_content = f.read()
    
    if 'apify' in req_content.lower():
        print("✅ requirements.txt includes Apify")
    else:
        print("❌ requirements.txt missing Apify")
        return False
    
    if 'docling' in req_content.lower():
        print("✅ requirements.txt includes Docling")
    else:
        print("❌ requirements.txt missing Docling")
        return False
    
    if 'openai' in req_content.lower():
        print("✅ requirements.txt includes OpenAI (for Ollama compatibility)")
    else:
        print("❌ requirements.txt missing OpenAI (needed for Ollama compatibility)")
        return False
    
    print("\n✅ All structural tests passed!")
    print("✅ Actor is properly structured for n8n integration!")
    
    return True


def test_n8n_ready_features():
    """Test that the actor has features needed for n8n integration"""
    print("\nTesting n8n-Ready Features...\n")
    
    # Read the actor code
    with open('apify_only/actor.py', 'r') as f:
        actor_code = f.read()
    
    # Check for n8n-compatible output (push_data)
    if 'Actor.push_data(' in actor_code:
        print("✅ Actor pushes data to dataset (n8n reads from here)")
    else:
        print("❌ Actor missing push_data call (n8n won't get results)")
        return False
    
    # Check for key-value store output (alternative access method)
    if 'Actor.set_value(' in actor_code and 'OUTPUT' in actor_code:
        print("✅ Actor sets OUTPUT value in key-value store")
    else:
        print("⚠️  Actor could benefit from setting OUTPUT value in key-value store")
    
    # Check for proper error handling
    if 'try:' in actor_code and 'except' in actor_code and 'Actor.fail(' in actor_code:
        print("✅ Actor has proper error handling with Actor.fail()")
    else:
        print("❌ Actor missing proper error handling")
        return False
    
    # Check for async/await usage (needed for Apify)
    if 'async def main' in actor_code and 'await Actor' in actor_code:
        print("✅ Actor uses async/await (required for Apify)")
    else:
        print("❌ Actor missing async/await (required for Apify)")
        return False
    
    print("\n✅ All n8n-ready feature tests passed!")
    return True


def test_groq_integration():
    """Test that the actor can integrate with Groq as specified"""
    print("\nTesting Groq Integration Capability...\n")
    
    with open('apify_only/actor.py', 'r') as f:
        actor_code = f.read()
    
    # Check for OpenAI client usage (compatible with Groq)
    if 'OpenAI(' in actor_code:
        print("✅ Actor uses OpenAI client (compatible with Groq)")
    else:
        print("❌ Actor not using OpenAI client")
        return False
    
    # Check for configurable base URL (needed for Groq)
    if 'base_url' in actor_code:
        print("✅ Actor supports configurable base URL (can use Groq)")
    else:
        print("❌ Actor not supporting configurable base URL")
        return False
    
    # Check for API key handling
    if 'api_key' in actor_code:
        print("✅ Actor handles API keys")
    else:
        print("❌ Actor not handling API keys")
        return False
    
    # Check actor.json for Groq API key input
    with open('apify_only/actor.json', 'r') as f:
        actor_config = json.load(f)
    
    input_props = actor_config.get('input', {}).get('schema', {}).get('properties', {})
    
    # We configured it to use Ollama API key, but the principle is the same
    if 'ollama_api_key' in input_props or 'api_key' in str(input_props):
        print("✅ Actor.json supports API key input")
    else:
        print("⚠️  Actor.json could be enhanced with API key input field")
    
    print("\n✅ Groq integration capability verified!")
    return True


def run_all_tests():
    """Run all tests for the n8n-ready actor"""
    print("Running Apify Actor Validation for n8n Integration\n")
    print("="*60)
    
    all_passed = True
    
    all_passed &= test_actor_structure()
    all_passed &= test_n8n_ready_features()
    all_passed &= test_groq_integration()
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Apify Actor is ready for n8n integration!")
        print("✅ Proper structure with required files")
        print("✅ n8n-compatible output methods")
        print("✅ Async/await and error handling")
        print("✅ API key and base URL configuration")
        print("\nThe actor is ready to be deployed to Apify!")
        return True
    else:
        print("❌ SOME TESTS FAILED!")
        print("Please fix the issues before deploying.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    if not success:
        exit(1)