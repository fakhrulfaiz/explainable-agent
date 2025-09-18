#!/usr/bin/env python3
"""
Simple test script for the user API
"""
import requests
import json

BASE_URL = "http://localhost:8000"  # Adjust if your API runs on different port

def test_create_user():
    """Test creating a user"""
    print("🧪 Testing user creation...")
    
    user_data = {
        "email": "faiz@gmail.com",
        "username": "faiz",
        "full_name": "Faiz"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/users/",
            json=user_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ User created successfully!")
            print(f"   User ID: {result['data']['user_id']}")
            print(f"   Email: {result['data']['email']}")
            print(f"   Username: {result['data']['username']}")
            return result['data']['user_id']
        else:
            print(f"❌ Failed to create user: {response.status_code}")
            print(f"   Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        return None

def test_get_user_by_email():
    """Test getting user by email"""
    print("\n🧪 Testing get user by email...")
    
    try:
        response = requests.get(f"{BASE_URL}/users/email/faiz@gmail.com")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ User found by email!")
            print(f"   User ID: {result['data']['user_id']}")
            print(f"   Email: {result['data']['email']}")
            return result['data']['user_id']
        else:
            print(f"❌ Failed to get user by email: {response.status_code}")
            print(f"   Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error getting user by email: {e}")
        return None

def test_get_all_users():
    """Test getting all users"""
    print("\n🧪 Testing get all users...")
    
    try:
        response = requests.get(f"{BASE_URL}/users/")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Retrieved {len(result['data'])} users")
            for user in result['data']:
                print(f"   - {user['username']} ({user['email']})")
        else:
            print(f"❌ Failed to get users: {response.status_code}")
            print(f"   Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Error getting users: {e}")

def test_get_user_by_id(user_id):
    """Test getting user by ID"""
    if not user_id:
        print("\n⏭️ Skipping get user by ID test (no user ID)")
        return
        
    print(f"\n🧪 Testing get user by ID ({user_id})...")
    
    try:
        response = requests.get(f"{BASE_URL}/users/{user_id}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ User found by ID!")
            print(f"   User ID: {result['data']['user_id']}")
            print(f"   Email: {result['data']['email']}")
        else:
            print(f"❌ Failed to get user by ID: {response.status_code}")
            print(f"   Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Error getting user by ID: {e}")

def main():
    """Run all tests"""
    print("🚀 Starting User API Tests")
    print("=" * 50)
    
    # Test creating user
    user_id = test_create_user()
    
    # Test getting user by email
    test_get_user_by_email()
    
    # Test getting all users
    test_get_all_users()
    
    # Test getting user by ID
    test_get_user_by_id(user_id)
    
    print("\n" + "=" * 50)
    print("🏁 Tests completed!")

if __name__ == "__main__":
    main()
