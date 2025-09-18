#!/usr/bin/env python3
"""
Test runner script for the explainable agent project
"""
import subprocess
import sys
import os
from pathlib import Path

def run_tests():
    """Run the test suite with coverage reporting"""
    
    # Change to backend directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    # Install test dependencies if needed
    print("📦 Installing test dependencies...")
    subprocess.run([
        sys.executable, "-m", "pip", "install", "-r", "requirements-test.txt"
    ], check=False)
    
    print("\n🧪 Running Repository Pattern Tests...\n")
    
    # Run tests with coverage
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--cov=src",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
        "--cov-fail-under=70"
    ]
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n✅ All tests passed!")
        print("\n📊 Coverage report generated in htmlcov/index.html")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Tests failed with exit code {e.returncode}")
        return False

def run_specific_test(test_pattern):
    """Run specific tests matching the pattern"""
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-k", test_pattern,
        "-v"
    ]
    
    subprocess.run(cmd)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run specific test pattern
        test_pattern = sys.argv[1]
        print(f"🔍 Running tests matching: {test_pattern}")
        run_specific_test(test_pattern)
    else:
        # Run all tests
        success = run_tests()
        sys.exit(0 if success else 1)
