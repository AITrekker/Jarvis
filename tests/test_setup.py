import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from setup.setup import is_ollama_running, check_ollama_api, check_ollama_models

class TestSetup(unittest.TestCase):
    
    @patch('setup.setup.requests.get')
    def test_is_ollama_running_success(self, mock_get):
        # Setup mock for successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"version": "0.1.14"}
        mock_get.return_value = mock_response
        
        # Call function
        result = is_ollama_running()
        
        # Verify
        self.assertTrue(result)
        mock_get.assert_called_once_with('http://localhost:11434/api/version', timeout=5.0)
    
    @patch('setup.setup.requests.get')
    def test_is_ollama_running_failure(self, mock_get):
        # Test cases for different failure modes
        failure_cases = [
            # Bad status code
            (MagicMock(status_code=500), False),
            
            # Connection error
            (ConnectionError(), False),
            
            # Timeout
            (TimeoutError(), False),
            
            # Generic exception
            (Exception("Test error"), False)
        ]
        
        for error, expected in failure_cases:
            # Setup mock
            if isinstance(error, Exception):
                mock_get.side_effect = error
            else:
                mock_get.return_value = error
            
            # Call function
            result = is_ollama_running()
            
            # Verify
            self.assertEqual(result, expected)
    
    @patch('setup.setup.requests.post')
    def test_check_ollama_api(self, mock_post):
        # Test successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = check_ollama_api()
        self.assertTrue(result)
        
        # Test 404 response (model not found but API working)
        mock_response.status_code = 404
        result = check_ollama_api()
        self.assertTrue(result)
        
        # Test other error response
        mock_response.status_code = 500
        result = check_ollama_api()
        self.assertFalse(result)
        
        # Test connection error
        mock_post.side_effect = ConnectionError()
        result = check_ollama_api()
        self.assertFalse(result)
    
    @patch('setup.setup.is_ollama_running')
    @patch('setup.setup.check_ollama_api')
    @patch('setup.setup.requests.get')
    @patch('setup.setup.sys.exit')
    def test_check_ollama_models(self, mock_exit, mock_get, mock_api_check, mock_running):
        # Import config here to avoid circular imports
        import config
        
        # Setup mocks for success case
        mock_running.return_value = True
        mock_api_check.return_value = True
        
        # Mock successful API response with all models available
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": config.OLLAMA_MODEL}, 
                {"name": config.OLLAMA_EMBEDDING_MODEL}
            ]
        }
        mock_get.return_value = mock_response
        
        # Call function - should not exit
        check_ollama_models()
        mock_exit.assert_not_called()
        
        # Test when Ollama is not running
        mock_running.return_value = False
        check_ollama_models()
        mock_exit.assert_called_with(1)
        mock_exit.reset_mock()
        
        # Test when API check fails
        mock_running.return_value = True
        mock_api_check.return_value = False
        check_ollama_models()
        mock_exit.assert_called_with(1)
        mock_exit.reset_mock()
        
        # Test when models are missing
        mock_api_check.return_value = True
        mock_response.json.return_value = {"models": []}
        check_ollama_models()
        mock_exit.assert_called_with(1)

if __name__ == '__main__':
    unittest.main()