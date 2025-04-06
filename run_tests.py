import os
import sys
import unittest
import time

def run_tests():
    """Run all test cases from the tests directory."""
    print("=" * 70)
    print("🧪 JARVIS TEST SUITE")
    print("=" * 70)
    
    # Find the tests directory
    tests_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests")
    
    # Create a test loader
    loader = unittest.TestLoader()
    
    # Discover all tests in the tests directory
    test_suite = loader.discover(tests_dir, pattern="test_*.py")
    
    # Run the tests
    start_time = time.time()
    result = unittest.TextTestRunner().run(test_suite)
    end_time = time.time()
    
    # Print a summary
    print("=" * 70)
    print(f"SUMMARY: {result.testsRun} tests run in {end_time - start_time:.2f}s")
    
    # Print failures and errors
    if result.failures:
        print(f"❌ FAILURES: {len(result.failures)}")
    else:
        print("❌ FAILURES: 0")
        
    if result.errors:
        print(f"❌ ERRORS:   {len(result.errors)}")
    else:
        print("❌ ERRORS:   0")
    
    if not result.failures and not result.errors:
        print("✅ All tests passed!")
        
    print("=" * 70)
    
    # Return appropriate exit code
    return len(result.failures) + len(result.errors)

if __name__ == "__main__":
    sys.exit(run_tests())