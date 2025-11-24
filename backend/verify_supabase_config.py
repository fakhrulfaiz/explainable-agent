#!/usr/bin/env python3
"""
Script to verify Supabase configuration.
Run this inside the Docker container or locally to check if Supabase is properly configured.
"""

import os
import sys
from src.models.config import settings

def check_configuration():
    """Check if Supabase is properly configured"""
    print("=" * 60)
    print("Supabase Configuration Verification")
    print("=" * 60)
    print()
    
    # Check URL
    url = settings.supabase_url or os.getenv("SUPABASE_URL", "")
    print(f"✅ SUPABASE_URL: {'Set' if url else '❌ NOT SET'}")
    if url:
        print(f"   Value: {url}")
    else:
        print("   ⚠️  Required: Set SUPABASE_URL in .env file")
    print()
    
    # Check Service Role Key
    service_key = settings.supabase_service_role_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    print(f"✅ SUPABASE_SERVICE_ROLE_KEY: {'Set' if service_key else '❌ NOT SET'}")
    if service_key:
        masked_key = service_key[:20] + "..." + service_key[-10:] if len(service_key) > 30 else "***"
        print(f"   Value: {masked_key}")
    else:
        print("   ⚠️  Required: Set SUPABASE_SERVICE_ROLE_KEY in .env file")
    print()
    
    # Check JWT Secret (optional)
    jwt_secret = settings.supabase_jwt_secret or os.getenv("SUPABASE_JWT_SECRET", "")
    print(f"ℹ️  SUPABASE_JWT_SECRET: {'Set' if jwt_secret else 'Not Set (Optional)'}")
    if jwt_secret:
        masked_secret = jwt_secret[:10] + "..." + jwt_secret[-5:] if len(jwt_secret) > 15 else "***"
        print(f"   Value: {masked_secret}")
    print()
    
    # Test Storage Service
    print("Testing Storage Service...")
    try:
        from src.services.supabase_storage_service import get_supabase_storage_service
        storage_service = get_supabase_storage_service()
        print("✅ Storage Service: Initialized successfully")
        print(f"   Bucket: {storage_service.bucket_name}")
    except ValueError as e:
        print(f"❌ Storage Service: {e}")
    except Exception as e:
        print(f"⚠️  Storage Service: {str(e)}")
    print()
    
    # Test User Memory Service
    print("Testing User Memory Service...")
    try:
        from src.services.user_memory_service import UserMemoryService
        user_service = UserMemoryService()
        if user_service.is_configured:
            print("✅ User Memory Service: Configured")
        else:
            print("❌ User Memory Service: Not configured (missing credentials)")
    except Exception as e:
        print(f"⚠️  User Memory Service: {str(e)}")
    print()
    
    # Summary
    print("=" * 60)
    if url and service_key:
        print("✅ Configuration Status: READY")
        print("   Your Supabase configuration appears to be correct!")
    else:
        print("❌ Configuration Status: INCOMPLETE")
        print("   Please set the required environment variables in backend/.env")
        print()
        print("   Required variables:")
        print("   - SUPABASE_URL=https://burgvcsigiyboezdfogu.supabase.co")
        print("   - SUPABASE_SERVICE_ROLE_KEY=your-service-role-key")
    print("=" * 60)
    
    return url and service_key

if __name__ == "__main__":
    success = check_configuration()
    sys.exit(0 if success else 1)

