import logging
import requests
from requests.exceptions import RequestException, ConnectionError, Timeout
from typing import Optional, Dict, Any, Tuple

from de4py.config.config import settings
from de4py.api.constants import ERROR_CODES

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Custom exception for API errors with structured information."""
    
    def __init__(self, status_code: int, message: str, action: str = None):
        self.status_code = status_code
        self.message = message
        self.action = action or "Check the error and retry"
        super().__init__(f"API Error {status_code}: {message}")


class De4pyApiClient:
    """
    Base HTTP client for de4py backend API.
    
    Features:
        - Automatic User-Agent header with version
        - Configurable timeout
        - Structured error handling for known error codes
        - JSON response parsing
    
    Usage:
        client = De4pyApiClient()
        response = client.get("/api/some/endpoint")
        data = client.post("/api/other/endpoint", json={"key": "value"})
    """
    
    def __init__(self, base_url: str = None, timeout: int = None):
        """
        Initialize the API client.
        
        Args:
            base_url: API base URL (defaults to config value)
            timeout: Request timeout in seconds (defaults to config value)
        """
        self.base_url = (base_url or settings.api_base_url).rstrip("/")
        self.timeout = timeout or settings.api_timeout
        
        # Extract version number (e.g., "V2.0.0" -> "2.0.0")
        version = settings.version.lstrip("Vv")
        self.headers = {
            "User-Agent": f"de4py/{version}",
        }
        
        # Session for connection pooling
        self._session = requests.Session()
        self._session.headers.update(self.headers)
    
    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint path."""
        return f"{self.base_url}{endpoint}"
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        Handle API response, raising structured errors for known error codes.
        
        Args:
            response: requests.Response object
            
        Returns:
            Parsed JSON response as dictionary
            
        Raises:
            ApiError: For known HTTP error codes
            requests.exceptions.HTTPError: For unknown HTTP errors
        """
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError:
            status_code = response.status_code
            
            # Check for known error codes
            if status_code in ERROR_CODES:
                error_info = ERROR_CODES[status_code]
                raise ApiError(
                    status_code=status_code,
                    message=error_info["meaning"],
                    action=error_info["action"],
                )
            
            # Try to extract error message from response
            try:
                error_data = response.json()
                message = error_data.get("detail", error_data.get("message", str(response.text)))
            except Exception:
                message = response.text or f"HTTP {status_code} error"
            
            raise ApiError(status_code=status_code, message=message)

    def get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Perform GET request.
        
        Args:
            endpoint: API endpoint path (e.g., "/api/integrations/pylingual/progress/123")
            params: Optional query parameters
            
        Returns:
            Parsed JSON response
        """
        url = self._build_url(endpoint)
        logger.debug(f"GET {url} params={params}")
        
        try:
            response = self._session.get(url, params=params, timeout=self.timeout)
            return self._handle_response(response)
        except ConnectionError:
            raise ApiError(
                status_code=0, 
                message="No internet connection available.", 
                action="Check your network settings and try again."
            )
        except Timeout:
            raise ApiError(
                status_code=408, 
                message="The server took too long to respond.", 
                action="Please try again later."
            )
        except RequestException as e:
            raise ApiError(
                status_code=999,
                message=f"Network Error: {str(e)}",
                action="Check your connection."
            )
    
    def post(
        self,
        endpoint: str,
        json: Dict[str, Any] = None,
        data: Dict[str, Any] = None,
        files: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Perform POST request.
        
        Args:
            endpoint: API endpoint path
            json: JSON body data
            data: Form data
            files: Files to upload (for multipart/form-data)
            
        Returns:
            Parsed JSON response
        """
        url = self._build_url(endpoint)
        logger.debug(f"POST {url}")
        
        try:
            response = self._session.post(
                url,
                json=json,
                data=data,
                files=files,
                timeout=self.timeout,
            )
            return self._handle_response(response)
        except ConnectionError:
            raise ApiError(
                status_code=0, 
                message="No internet connection available.", 
                action="Check your network settings and try again."
            )
        except Timeout:
            raise ApiError(
                status_code=408, 
                message="The server took too long to respond.", 
                action="Please try again later."
            )
        except RequestException as e:
            raise ApiError(
                status_code=999,
                message=f"Network Error: {str(e)}",
                action="Check your connection."
            )
    
    def close(self):
        """Close the session and release resources."""
        self._session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
