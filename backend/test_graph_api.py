#!/usr/bin/env python3
"""
Test script for the new graph-based API endpoints
"""
import requests
import json
import time

# API base URL
BASE_URL = "http://localhost:8000"

def test_graph_start():
    """Test the /graph/start endpoint"""
    print("🚀 Testing /graph/start endpoint...")
    
    payload = {
        "human_request": "How many paintings are in the database?"
    }
    
    response = requests.post(f"{BASE_URL}/graph/start", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Start request successful!")
        print(f"Thread ID: {result['thread_id']}")
        print(f"Status: {result['run_status']}")
        print(f"Assistant Response: {result.get('assistant_response', 'N/A')}")
        if result.get('plan'):
            print(f"Plan: {result['plan']}")
        return result['thread_id']
    else:
        print(f"❌ Start request failed: {response.status_code}")
        print(f"Error: {response.text}")
        return None

def test_graph_resume(thread_id, action="approved", comment=None):
    """Test the /graph/resume endpoint"""
    print(f"\n🔄 Testing /graph/resume endpoint with action: {action}...")
    
    payload = {
        "thread_id": thread_id,
        "review_action": action
    }
    
    if comment:
        payload["human_comment"] = comment
    
    response = requests.post(f"{BASE_URL}/graph/resume", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Resume request successful!")
        print(f"Status: {result['run_status']}")
        if result.get('assistant_response'):
            print(f"Assistant Response: {result['assistant_response']}")
        if result.get('steps'):
            print(f"Number of steps: {len(result['steps'])}")
        if result.get('final_result'):
            print(f"Final Result Summary: {result['final_result']['Summary']}")
        return result
    else:
        print(f"❌ Resume request failed: {response.status_code}")
        print(f"Error: {response.text}")
        return None

def test_graph_status(thread_id):
    """Test the /graph/status endpoint"""
    print(f"\n📊 Testing /graph/status endpoint...")
    
    response = requests.get(f"{BASE_URL}/graph/status/{thread_id}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Status request successful!")
        print(f"Status: {result['status']}")
        print(f"Step Count: {result['step_count']}")
        if result.get('next_nodes'):
            print(f"Next Nodes: {result['next_nodes']}")
        return result
    else:
        print(f"❌ Status request failed: {response.status_code}")
        print(f"Error: {response.text}")
        return None

def test_complete_workflow():
    """Test the complete workflow: start -> status -> approve -> finish"""
    print("=" * 60)
    print("🧪 TESTING COMPLETE GRAPH WORKFLOW")
    print("=" * 60)
    
    # Step 1: Start the graph
    thread_id = test_graph_start()
    if not thread_id:
        return
    
    # Step 2: Check status
    test_graph_status(thread_id)
    
    # Step 3: Approve and continue
    result = test_graph_resume(thread_id, "approved")
    
    # Step 4: Check final status
    if result and result.get('run_status') == 'finished':
        print("\n🎉 Workflow completed successfully!")
        test_graph_status(thread_id)
    else:
        print("\n⚠️ Workflow may need additional steps")

def test_feedback_workflow():
    """Test workflow with human feedback"""
    print("\n" + "=" * 60)
    print("🧪 TESTING FEEDBACK WORKFLOW")
    print("=" * 60)
    
    # Step 1: Start the graph
    thread_id = test_graph_start()
    if not thread_id:
        return
    
    # Step 2: Provide feedback instead of approval
    result = test_graph_resume(
        thread_id, 
        "feedback", 
        "Please be more specific about which table contains the paintings"
    )
    
    # Step 3: After feedback, approve the revised plan
    if result:
        test_graph_resume(thread_id, "approved")

if __name__ == "__main__":
    print("🔧 Graph API Test Suite")
    print("Make sure the server is running on localhost:8000")
    print("Starting in 3 seconds...")
    time.sleep(3)
    
    try:
        # Test health endpoint first
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            print("❌ Server health check failed!")
            exit(1)
        print("✅ Server is healthy!")
        
        # Run tests
        test_complete_workflow()
        test_feedback_workflow()
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure it's running on localhost:8000")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
