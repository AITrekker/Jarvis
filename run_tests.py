import os
import sys
import unittest
import time
import argparse
from tests.test_helpers import cleanup_test_summaries

# Add parent directory to path to import project modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Handle the debug flag directly in run_tests.py
parser = argparse.ArgumentParser(description="Run Jarvis test suite")
parser.add_argument("-p", "--pattern", default="test_*.py", 
                    help="Pattern for test file names (default: test_*.py)")
parser.add_argument("--debug", "-d", action="store_true", 
                    help="Enable debug mode")
args = parser.parse_args()

# Define DEBUG_MODE here instead of importing from config
DEBUG_MODE = args.debug

def run_tests(test_pattern="test_*.py"):
    """Run all test cases from the tests directory."""
    print("=" * 70)
    print("🧪 JARVIS TEST SUITE")
    if DEBUG_MODE:
        print("🐛 DEBUG MODE ENABLED")
    print("=" * 70)
    
    try:
        # Find the tests directory
        tests_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests")
        
        # Create a test loader
        loader = unittest.TestLoader()
        
        # Discover all tests in the tests directory
        test_suite = loader.discover(tests_dir, pattern=test_pattern)
        
        # Run the tests with verbose output if in debug mode
        start_time = time.time()
        verbosity = 2 if DEBUG_MODE else 1
        result = unittest.TextTestRunner(verbosity=verbosity).run(test_suite)
        end_time = time.time()
        
        # Print a summary
        print("=" * 70)
        print(f"SUMMARY: {result.testsRun} tests run in {end_time - start_time:.2f}s")
        
        # Print failures and errors
        if result.failures:
            print(f"❌ FAILURES: {len(result.failures)}")
            if DEBUG_MODE:
                for i, (test, traceback) in enumerate(result.failures):
                    print(f"\nFAILURE {i+1}: {test}")
                    print("-" * 70)
                    print(traceback)
        else:
            print("✅ FAILURES: 0")
            
        if result.errors:
            print(f"❌ ERRORS:   {len(result.errors)}")
            if DEBUG_MODE:
                for i, (test, traceback) in enumerate(result.errors):
                    print(f"\nERROR {i+1}: {test}")
                    print("-" * 70)
                    print(traceback)
        else:
            print("✅ ERRORS:   0")
        
        if not result.failures and not result.errors:
            print("✅ All tests passed!")
            
        print("=" * 70)
        
        # Perform final cleanup of any test summaries
        print("\nCleaning up any remaining test summaries...")
        cleanup_test_summaries()
        
        # Return appropriate exit code
        return len(result.failures) + len(result.errors)
    finally:
        # Ensure cleanup happens even if tests are interrupted
        cleanup_test_summaries()

if __name__ == "__main__":
    sys.exit(run_tests(args.pattern))