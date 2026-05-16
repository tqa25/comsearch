import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

TIMEOUTS = {
    "search": 30,
    "scrape": 35,
    "gemini": 60,
    "default": 15,
}


class ConnectionManager:
    """Manage HTTP sessions with persistent connections.

    Reuses sessions to reduce TCP overhead.
    """

    def __init__(self, api_key: str, base_url: str = None):
        """Create session with Authorization header.

        Args:
            api_key: API key for Bearer auth.
            base_url: Optional base URL for all requests.
        """
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })
        self.base_url = base_url

    def post(
        self,
        url: str,
        json: dict = None,
        request_type: str = "search",
        headers: dict = None,
    ) -> requests.Response:
        """Send POST request.

        Args:
            url: Request URL.
            json: JSON body.
            request_type: Type for timeout lookup.
            headers: Additional headers.

        Returns:
            Response object.
        """
        timeout = TIMEOUTS.get(request_type, TIMEOUTS["default"])
        return self.session.post(
            url, json=json, timeout=timeout, headers=headers
        )

    def get(
        self,
        url: str,
        params: dict = None,
        request_type: str = "default",
    ) -> requests.Response:
        """Send GET request.

        Args:
            url: Request URL.
            params: Query parameters.
            request_type: Type for timeout lookup.

        Returns:
            Response object.
        """
        timeout = TIMEOUTS.get(request_type, TIMEOUTS["default"])
        return self.session.get(url, params=params, timeout=timeout)

    def close(self):
        """Close the session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
