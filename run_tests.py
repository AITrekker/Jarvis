import unittest
import os
import sys
from unittest import TextTestRunner, TextTestResult

# Add current directory to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Custom test result formatter for cleaner output
class CleanTestResult(TextTestResult):
    def getDescription(self, test):
        return test.shortDescription() or str(test)

if __name__ == "__main__":
    # Print header
    print("\n" + "="*70)
    print("🧪 JARVIS TEST SUITE")
    print("="*70)
    
    # Discover and run all tests
    test_loader = unittest.TestLoader()
    test_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'tests')
    test_suite = test_loader.discover(test_dir)
    
    # Use custom formatter with higher verbosity
    runner = TextTestRunner(verbosity=2, resultclass=CleanTestResult)
    result = runner.run(test_suite)
    
    # Print summary
    print("\n" + "="*70)
    print(f"SUMMARY: {result.testsRun} tests run")
    if not result.wasSuccessful():
        print(f"❌ FAILURES: {len(result.failures)}")
        print(f"❌ ERRORS:   {len(result.errors)}")
    else:
        print("✅ All tests passed!")
    print("="*70 + "\n")
    
    # Return non-zero exit code if there were failures
    sys.exit(not result.wasSuccessful())