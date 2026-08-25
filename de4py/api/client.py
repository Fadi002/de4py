# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import logging
import requests
from requests.exceptions import RequestException, ConnectionError, Timeout
from typing import Dict, Any

from de4py.config.config import settings
from de4py.api.constants import ERROR_CODES

logger = logging.getLogger(__name__)


class ApiError(Exception):

    def __init__(self, status_code: int, message: str, action: str = None):
        self.status_code = status_code
        self.message = message
        self.action = action or "Check the error and retry"
        super().__init__(f"API Error {status_code}: {message}")


class De4pyApiClient:

    def __init__(self, base_url: str = None, timeout: int = None):
        self.base_url = (base_url or settings.api_base_url).rstrip("/")
        self.timeout = timeout or settings.api_timeout

        version = settings.version.lstrip("Vv")
        self.headers = {
            "User-Agent": f"de4py/{version}",
        }

        self._session = requests.Session()
        self._session.headers.update(self.headers)

    def _build_url(self, endpoint: str) -> str:
        return f"{self.base_url}{endpoint}"

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError:
            logger.debug("Response text: %s", response.text)
            status_code = response.status_code

            if status_code in ERROR_CODES:
                error_info = ERROR_CODES[status_code]
                raise ApiError(
                    status_code=status_code,
                    message=error_info["meaning"],
                    action=error_info["action"],
                )

            try:
                error_data = response.json()
                message = error_data.get("detail", error_data.get("message", str(response.text)))
            except Exception:
                message = response.text or f"HTTP {status_code} error"
            
            raise ApiError(status_code=status_code, message=message)

    def get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
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
        self._session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
