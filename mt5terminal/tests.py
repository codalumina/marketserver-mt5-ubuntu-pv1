from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch


class LiveEndpointTests(APITestCase):
    # We patch the exact location where the client is IMPORTED and USED in our views
    @patch("mt5terminal.views.MT5DataClient")
    def test_live_single_symbol_success(self, MockMT5Client):
        # 1. Setup the Mock
        # 'mock_instance' represents the object created when views.py calls client = MT5DataClient()
        mock_instance = MockMT5Client.return_value

        # Tell the mock exactly what to return when get_symbol is called
        mock_instance.get_symbol.return_value = {
            "description": "Euro vs US Dollar",
            "bid": 1.1000,
            "bidhigh": 1.1050,
            "bidlow": 1.0950,
            "ask": 1.1002,
            "askhigh": 1.1052,
            "asklow": 1.0952,
            "session_open": 1.0980,
            "session_close": 1.0990,
            "swap_long": -1.5,
            "swap_short": 0.5,
            "path": "Forex\\Majors\\EURUSD",
        }

        # 2. Make the Request (simulate a user hitting the API)
        response = self.client.get("/api/live/?symbol=EURUSD")

        # 3. Assertions (Did the API behave correctly?)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["symbol"], "EURUSD")
        self.assertEqual(response.data["bid"], 1.1000)

        # 4. Memory Leak Check: Did the view call client.shutdown()?
        mock_instance.shutdown.assert_called_once()

    @patch("mt5terminal.views.MT5DataClient")
    def test_live_invalid_symbol_returns_400(self, MockMT5Client):
        # 1. Setup the Mock to simulate a crash/bad input
        mock_instance = MockMT5Client.return_value
        # Using 'side_effect' makes the mock actually raise an Exception instead of returning data
        mock_instance.get_symbol.side_effect = ValueError(
            "Failed to get symbol info for FAKE"
        )

        # 2. Make the Request
        response = self.client.get("/api/live/?symbol=FAKE")

        # 3. Assertions
        # It should catch the ValueError and return a clean 400 Error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

        # 4. Memory Leak Check: Ensure shutdown STILL runs even after the exception!
        mock_instance.shutdown.assert_called_once()

    @patch("mt5terminal.views.MT5DataClient")
    def test_live_all_symbols_success(self, MockMT5Client):
        mock_instance = MockMT5Client.return_value
        # Mock get_targeted_symbols to return a list/iterable of symbol objects
        mock_instance.get_targeted_symbols.return_value = [
            {
                "name": "EURUSD",
                "description": "Euro vs US Dollar",
                "bid": 1.1000,
                "bidhigh": 1.1050,
                "bidlow": 1.0950,
                "ask": 1.1002,
                "askhigh": 1.1052,
                "asklow": 1.0952,
                "session_open": 1.0980,
                "session_close": 1.0990,
            },
            {
                "name": "GBPUSD",
                "description": "Great British Pound vs US Dollar",
                "bid": 1.2500,
                "bidhigh": 1.2550,
                "bidlow": 1.2450,
                "ask": 1.2502,
                "askhigh": 1.2552,
                "asklow": 1.2452,
                "session_open": 1.2480,
                "session_close": 1.2490,
            },
        ]

        response = self.client.get("/api/live/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("live_board", response.data)
        self.assertIn("timestamp", response.data)
        mock_instance.shutdown.assert_called_once()

    @patch("mt5terminal.views.MT5DataClient")
    def test_live_mt5_connection_error_returns_503(self, MockMT5Client):
        mock_instance = MockMT5Client.return_value
        # Simulate an MT5 connection error
        mock_instance.get_symbol.side_effect = RuntimeError("MT5 connection lost")

        response = self.client.get("/api/live/?symbol=EURUSD")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("error", response.data)
        mock_instance.shutdown.assert_called_once()

    @patch("mt5terminal.views.MT5DataClient")
    def test_live_unexpected_data_structure_returns_500(self, MockMT5Client):
        mock_instance = MockMT5Client.return_value
        # Simulate a missing key in MT5 response
        mock_instance.get_symbol.side_effect = KeyError("bid")

        response = self.client.get("/api/live/?symbol=EURUSD")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.data)
        self.assertIn("missing field", response.data["error"])
        mock_instance.shutdown.assert_called_once()

    @patch("mt5terminal.views.MT5DataClient")
    def test_live_catch_all_exception_returns_500(self, MockMT5Client):
        mock_instance = MockMT5Client.return_value
        # Simulate an unexpected generic error
        mock_instance.get_symbol.side_effect = Exception("Out of memory")

        response = self.client.get("/api/live/?symbol=EURUSD")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.data)
        mock_instance.shutdown.assert_called_once()
