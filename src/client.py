"""Vestaboard Local API client."""

import requests
from typing import Optional

from .characters import format_message, create_board, ROWS, COLS
from .config import config


class VestaboardClient:
    """Client for Vestaboard Local API."""

    def __init__(
        self,
        local_url: Optional[str] = None,
        local_key: Optional[str] = None
    ):
        """Initialize the Vestaboard client.

        Args:
            local_url: Vestaboard Local API URL (e.g., http://192.168.1.100:7000).
            local_key: Vestaboard Local API key.
        """
        self.local_url = (local_url or config.vestaboard_local_url).rstrip("/")
        self.local_key = local_key or config.vestaboard_local_key

        if not self.local_url:
            raise ValueError("Vestaboard Local URL is required")
        if not self.local_key:
            raise ValueError("Vestaboard Local API key is required")

    def _get_headers(self) -> dict:
        """Get headers for API requests."""
        return {
            "X-Vestaboard-Local-Api-Key": self.local_key,
            "Content-Type": "application/json",
        }

    def send_message(self, text: str, center: bool = True) -> bool:
        """Send a text message to the Vestaboard.

        Args:
            text: Text message to display (will be auto-wrapped).
            center: If True, center the text.

        Returns:
            True if message was sent successfully.
        """
        board = format_message(text, center=center)
        return self.send_board(board)

    def send_board(self, board: list[list[int]]) -> bool:
        """Send a raw board matrix to the Vestaboard.

        Args:
            board: 6x22 matrix of character codes.

        Returns:
            True if message was sent successfully.
        """
        # Validate board dimensions
        if len(board) != ROWS:
            raise ValueError(f"Board must have {ROWS} rows, got {len(board)}")
        for row in board:
            if len(row) != COLS:
                raise ValueError(f"Each row must have {COLS} columns")

        url = f"{self.local_url}/local-api/message"

        try:
            response = requests.post(
                url,
                json=board,
                headers=self._get_headers(),
                timeout=10
            )
            response.raise_for_status()
            print(f"Message sent successfully to Vestaboard")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error sending message to Vestaboard: {e}")
            return False

    def send_lines(self, lines: list[str], center: bool = True) -> bool:
        """Send multiple lines to the Vestaboard.

        Args:
            lines: List of up to 6 lines of text.
            center: If True, center each line.

        Returns:
            True if message was sent successfully.
        """
        board = create_board(lines, center=center)
        return self.send_board(board)

    def clear(self) -> bool:
        """Clear the Vestaboard (display all blank).

        Returns:
            True if cleared successfully.
        """
        board = [[0] * COLS for _ in range(ROWS)]
        return self.send_board(board)

    def test_connection(self) -> bool:
        """Test the connection to the Vestaboard.

        Returns:
            True if connection is working.
        """
        url = f"{self.local_url}/local-api/message"

        try:
            # Just do a GET to check if the API is reachable
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=5
            )
            # Local API returns current board on GET
            return response.status_code in [200, 405]  # 405 if GET not allowed
        except requests.exceptions.RequestException as e:
            print(f"Connection test failed: {e}")
            return False

    def get_current_board(self) -> Optional[list[list[int]]]:
        """Get the current board state.

        Returns:
            Current 6x22 matrix or None if unavailable.
        """
        url = f"{self.local_url}/local-api/message"

        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                # API returns {"message": [[...]]}
                if isinstance(data, dict) and "message" in data:
                    return data["message"]
                return data
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error getting current board: {e}")
            return None
