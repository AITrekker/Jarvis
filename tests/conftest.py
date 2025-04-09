"""Test configuration for Jarvis."""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set test mode
os.environ['JARVIS_TEST_MODE'] = 'True'