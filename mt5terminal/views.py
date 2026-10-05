import os
import shutil
import platform

# --- OS-Agnostic MT5 Import ---
try:
    import MetaTrader5 as mt5
except ImportError:
    from unittest.mock import MagicMock

    mt5 = MagicMock()
# ------------------------------

from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from datetime import datetime, timezone
from .connector import MT5DataClient
from .monitored_symbols import TARGET_SYMBOLS


@api_view(["GET"])
def live(request):
    """
    Retrieve live market data for MetaTrader 5 symbols.

    This endpoint provides real-time bid/ask prices, session data, and swap rates
    for either a single symbol or all monitored symbols.

    Args:
        request: Django REST Framework request object.
            Query Parameters:
                - symbol (str, optional): Specific symbol to query (e.g., 'EURUSD').
                                         If omitted, returns data for all monitored symbols.

    Returns:
        Response: JSON response with status 200 containing:
            - Single symbol mode: Symbol details including bid, ask, session data, and timestamp.
            - All symbols mode: List of monitored symbols with their market data.

        Response structure (single symbol):
            {
                "symbol": str,
                "description": str,
                "bid": float,
                "bidhigh": float,
                "bidlow": float,
                "ask": float,
                "askhigh": float,
                "asklow": float,
                "session_open": float,
                "session_close": float,
                "swap_long": float,
                "swap_short": float,
                "path": str,
                "timestamp": str (ISO format)
            }

        Response structure (all symbols):
            {
                "live_board": [list of symbol data],
                "timestamp": str (ISO format)
            }

    Raises:
        HTTP 400 (Bad Request): Invalid symbol or failed to retrieve symbol data.
                               Returns {"error": str}
        HTTP 500 (Internal Server Error): Unexpected data structure or missing fields from MT5.
                                          Returns {"error": str}
        HTTP 503 (Service Unavailable): MT5 terminal connection or initialization error.
                                       Returns {"error": str}
    """
    client = None
    try:
        # 1. Open the bridge
        client = MT5DataClient()

        symbol = request.query_params.get("symbol", None)

        # Scenario A: Single Symbol
        if symbol:
            data = client.get_symbol(symbol)
            return Response(
                {
                    "symbol": symbol,
                    "description": data["description"],
                    "bid": data["bid"],
                    "bidhigh": data["bidhigh"],
                    "bidlow": data["bidlow"],
                    "ask": data["ask"],
                    "askhigh": data["askhigh"],
                    "asklow": data["asklow"],
                    "session_open": data["session_open"],
                    "session_close": data["session_close"],
                    "swap_long": data["swap_long"],
                    "swap_short": data["swap_short"],
                    "path": data["path"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                status=status.HTTP_200_OK,
            )

        # Scenario B: All Symbols
        data = client.get_targeted_symbols(TARGET_SYMBOLS)
        live_board = []
        for sym in data:
            live_board.append(
                {
                    "symbol": sym["name"],
                    "description": sym["description"],
                    "bid": sym["bid"],
                    "bidhigh": sym["bidhigh"],
                    "bidlow": sym["bidlow"],
                    "ask": sym["ask"],
                    "askhigh": sym["askhigh"],
                    "asklow": sym["asklow"],
                    "session_open": sym["session_open"],
                    "session_close": sym["session_close"],
                }
            )

        return Response(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "live_board": live_board,
            },
            status=status.HTTP_200_OK,
        )

    except ValueError as e:
        # Invalid symbol or failed to retrieve symbol data
        return Response(
            {"error": f"Invalid symbol or data retrieval failed: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    except RuntimeError as e:
        # MT5 terminal connection or initialization errors
        return Response(
            {"error": f"MT5 connection error: {str(e)}"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    except KeyError as e:
        # Missing expected data fields in MT5 response
        return Response(
            {"error": f"Unexpected data structure from MT5: missing field {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    except Exception as e:
        # Catch-all for unexpected errors
        return Response(
            {"error": f"Unexpected error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    finally:
        # This block executes NO MATTER WHAT.
        # It guarantees the IPC bridge is destroyed.
        if client is not None:
            client.shutdown()


@api_view(["GET"])
def server_stat(request):
    """
    Retrieve comprehensive MetaTrader 5 and physical server statistics.

    This endpoint provides detailed information about the MT5 terminal connection,
    account status, trading permissions, and physical Linux server resources.
    Uses Wine Z:\ drive mapping to access native Linux /proc filesystem.

    Args:
        request: Django REST Framework request object. No query parameters required.

    Returns:
        Response: JSON response with status 200 containing:
            {
                "status": "healthy",
                "timestamp": str (ISO format),
                "mt5": {
                    "connected": bool,
                    "broker": str,
                    "server": str,
                    "account_name": str,
                    "leverage": int,
                    "ping": int,
                    "build": int,
                    "account_currency": str,
                    "balance": float,
                    "equity": float,
                    "floating_profit": float,
                    "margin_free": float,
                    "margin_level_pct": float,
                    "trade_allowed_by_broker": bool,
                    "algo_trading_allowed": bool,
                    "open_positions_count": int,
                    "pending_orders_count": int
                },
                "server": {
                    "python_architecture": str,
                    "wine_version": str,
                    "ram_total_mb": float,
                    "ram_available_mb": float,
                    "ram_used_mb": float,
                    "cpu_load_avg": list[str],
                    "uptime_days": float,
                    "uptime_hours": float,
                    "cpu_cores": int,
                    "cpu_model": str,
                    "disk_total_gb": float,
                    "disk_free_gb": float
                }
            }

    Raises:
        HTTP 500 (Internal Server Error): Environment configuration errors, failed to parse
                                          system data, or filesystem access errors.
                                          Returns {"status": str, "error_message": str, "timestamp": str}
        HTTP 503 (Service Unavailable): MT5 terminal initialization or connection failed.
                                       Returns {"status": str, "error_message": str, "timestamp": str}
    """
    client = None
    try:
        # 1. Open the MT5 Bridge
        client = MT5DataClient()

        # 2. Gather MT5 Terminal & Account Stats
        terminal_info = client.terminal_info
        account_info = client.get_account_info()

        # Grab active trade counts (safely handling None returns)
        total_positions = (
            mt5.positions_total() if mt5.positions_total() is not None else 0
        )
        total_orders = mt5.orders_total() if mt5.orders_total() is not None else 0

        account_name = (account_info.get("name", "Unknown"),)
        name_initials = (
            "".join([part[0] for part in account_name[0].split()])
            if account_name
            else "Unknown"
        )

        mt5_stats = {
            "connected": terminal_info.get("connected", False),
            "broker": account_info.get("company", "Unknown"),
            "server": account_info.get("server", "Unknown"),
            "account_name_initials": name_initials,
            "leverage": account_info.get("leverage", 0),
            "ping": terminal_info.get("ping_last", 0),
            "build": terminal_info.get("build", 0),
            "account_currency": account_info.get("currency", ""),
            "balance": account_info.get("balance", 0.0),
            "equity": account_info.get("equity", 0.0),
            "floating_profit": account_info.get("profit", 0.0),
            "margin_free": account_info.get("margin_free", 0.0),
            "margin_level_pct": account_info.get("margin_level", 0.0),
            "trade_allowed_by_broker": account_info.get("trade_allowed", False),
            "algo_trading_allowed": terminal_info.get("trade_allowed", False),
            "open_positions_count": total_positions,
            "pending_orders_count": total_orders,
        }

        # 3. Gather Physical OS Server Stats (The Wine Z:\ Drive Hack)
        os_stats = {
            "python_architecture": platform.architecture()[0],
            "wine_version": "Active",
        }

        try:
            # Memory
            with open("Z:/proc/meminfo", "r") as f:
                meminfo = f.readlines()
                total_mb = int(meminfo[0].split()[1]) / 1024
                available_mb = int(meminfo[2].split()[1]) / 1024

                os_stats["ram_total_mb"] = round(total_mb, 2)
                os_stats["ram_available_mb"] = round(available_mb, 2)
                os_stats["ram_used_mb"] = round(total_mb - available_mb, 2)

            # CPU Load (1min, 5min, 15min average)
            with open("Z:/proc/loadavg", "r") as f:
                load = f.read().split()[:3]
                os_stats["cpu_load_avg"] = load

            # Server Uptime
            with open("Z:/proc/uptime", "r") as f:
                uptime_seconds = float(f.readline().split()[0])
                os_stats["uptime_days"] = round(uptime_seconds / 86400, 2)
                os_stats["uptime_hours"] = round(uptime_seconds / 3600, 2)

            # CPU Info
            with open("Z:/proc/cpuinfo", "r") as f:
                cpuinfo = f.read()
                cores = cpuinfo.count("processor\t:")
                # Extract the first CPU model name
                model_lines = [
                    line for line in cpuinfo.split("\n") if "model name" in line
                ]
                model = (
                    model_lines[0].split(":")[1].strip()
                    if model_lines
                    else "Unknown CPU"
                )
                os_stats["cpu_cores"] = cores
                os_stats["cpu_model"] = model

            # Disk Space
            disk = shutil.disk_usage("Z:/")
            os_stats["disk_total_gb"] = round(disk.total / (1024**3), 2)
            os_stats["disk_free_gb"] = round(disk.free / (1024**3), 2)

        except Exception as e:
            os_stats["linux_read_error"] = (
                f"Could not read native Linux stats: {str(e)}"
            )

        # 4. Construct Final Response
        return Response(
            {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mt5": mt5_stats,
                "server": os_stats,
            },
            status=status.HTTP_200_OK,
        )

    except ValueError as e:
        # Environment configuration errors or invalid MT5 credentials
        return Response(
            {
                "status": "configuration_error",
                "error_message": f"Configuration error: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    except RuntimeError as e:
        # MT5 terminal initialization or connection failures
        return Response(
            {
                "status": "mt5_connection_error",
                "error_message": f"MT5 connection failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    except (IOError, OSError) as e:
        # File system access errors (reading /proc files via Wine)
        return Response(
            {
                "status": "filesystem_error",
                "error_message": f"Failed to read system stats: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    except (IndexError, KeyError) as e:
        # Unexpected data structure when parsing system files or MT5 data
        return Response(
            {
                "status": "parse_error",
                "error_message": f"Failed to parse system or MT5 data: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    except Exception as e:
        # Catch-all for unexpected errors
        return Response(
            {
                "status": "error",
                "error_message": f"Unexpected error: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    finally:
        # Guarantee the connection closes cleanly
        if client is not None:
            client.shutdown()


@api_view(["GET"])
def history(request):
    """
    Retrieve historical OHLC (Open, High, Low, Close) data for a specific symbol within a date range.

    This endpoint fetches candlestick data for a given symbol between specified start and end dates
    at a particular timeframe granularity.

    Args:
        request: Django REST Framework request object.
            Query Parameters (all required):
                - symbol (str): Trading symbol (e.g., 'EURUSD', 'BTCUSD').
                - from (str): Start date in ISO format (e.g., '2023-01-01T00:00:00').
                - to (str): End date in ISO format (e.g., '2023-12-31T23:59:59').
                - timeframe (str): Candlestick timeframe. Valid options include:
                                  'M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1', 'MN1'

    Returns:
        Response: JSON response with status 200 containing:
            {
                "symbol": str,
                "timeframe": str,
                "count": int,
                "history": [
                    {
                        "time": int (Unix timestamp),
                        "iso_time": str (ISO format),
                        "open": float,
                        "high": float,
                        "low": float,
                        "close": float,
                        "tick_volume": int,
                        "spread": int,
                        "real_volume": int
                    },
                    ...
                ],
                "timestamp": str (ISO format)
            }

    Raises:
        HTTP 400 (Bad Request): Missing required parameters, invalid date format, invalid timeframe,
                               invalid symbol, no data available, or timestamp conversion errors.
                               Returns {"error": str}
        HTTP 500 (Internal Server Error): Unexpected errors during data processing.
                                          Returns {"error": str}
        HTTP 503 (Service Unavailable): MT5 terminal not connected.
                                       Returns {"error": str}
    """
    client = None
    try:
        symbol = request.query_params.get("symbol")
        from_date_str = request.query_params.get("from")
        to_date_str = request.query_params.get("to")
        timeframe_str = request.query_params.get("timeframe")

        if not all([symbol, from_date_str, to_date_str, timeframe_str]):
            return Response(
                {"error": "Missing required parameters: symbol, from, to, timeframe"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Safely parse the dates
        try:
            from_date = datetime.fromisoformat(from_date_str)
            to_date = datetime.fromisoformat(to_date_str)
        except ValueError:
            return Response(
                {
                    "error": "Invalid date format. Use ISO format (e.g., 2023-01-01T00:00:00)"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = MT5DataClient()

        # Safely map the string timeframe to the MT5 constant
        tf_map = client.timeframes
        tf_constant = tf_map.get(timeframe_str.upper())
        if tf_constant is None:
            return Response(
                {"error": f"Invalid timeframe. Valid options: {list(tf_map.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ohlc_history = client.get_ohlc_range(
            symbol_name=symbol,
            from_date=from_date,
            to_date=to_date,
            timeframe=tf_constant,
        )

        # Inject timezone-aware ISO timestamps
        for ohlc in ohlc_history:
            ohlc["iso_time"] = datetime.fromtimestamp(
                ohlc["time"], tz=client.timezone
            ).isoformat()

        return Response(
            {
                "symbol": symbol,
                "timeframe": timeframe_str.upper(),
                "count": len(ohlc_history),
                "history": ohlc_history,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            status=status.HTTP_200_OK,
        )

    except ValueError as e:
        # Invalid symbol, date format, or no data available for the range
        return Response(
            {"error": f"Invalid input or no data available: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    except RuntimeError as e:
        # MT5 terminal not connected
        return Response(
            {"error": f"MT5 connection error: {str(e)}"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    except (OSError, OverflowError) as e:
        # Timestamp conversion errors
        return Response(
            {"error": f"Date/time processing error: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:
        # Catch-all for unexpected errors
        return Response(
            {"error": f"Unexpected error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    finally:
        if client is not None:
            client.shutdown()


@api_view(["GET"])
def recent_price_action(request):
    """
    Retrieve the most recent OHLC price action data for a specific symbol.

    This endpoint fetches the latest N candlesticks for a given symbol and timeframe,
    starting from the most recent bar and working backwards.

    Args:
        request: Django REST Framework request object.
            Query Parameters:
                - symbol (str, required): Trading symbol (e.g., 'EURUSD', 'BTCUSD').
                - timeframe (str, required): Candlestick timeframe. Valid options include:
                                            'M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1', 'MN1'
                - count (int, optional): Number of bars to retrieve. Defaults to 100.

    Returns:
        Response: JSON response with status 200 containing:
            {
                "symbol": str,
                "timeframe": str,
                "count": int,
                "price_action": [
                    {
                        "time": int (Unix timestamp),
                        "iso_time": str (ISO format),
                        "open": float,
                        "high": float,
                        "low": float,
                        "close": float,
                        "tick_volume": int,
                        "spread": int,
                        "real_volume": int
                    },
                    ...
                ],
                "timestamp": str (ISO format)
            }

    Raises:
        HTTP 400 (Bad Request): Missing required parameters, invalid count parameter,
                               invalid timeframe, invalid symbol, no data available,
                               or timestamp conversion errors.
                               Returns {"error": str}
        HTTP 500 (Internal Server Error): Unexpected errors during data processing.
                                          Returns {"error": str}
        HTTP 503 (Service Unavailable): MT5 terminal not connected.
                                       Returns {"error": str}
    """
    client = None
    try:
        symbol = request.query_params.get("symbol")
        timeframe_str = request.query_params.get("timeframe")

        # Safely parse count
        try:
            count = int(request.query_params.get("count", 100))
        except ValueError:
            return Response(
                {"error": "'count' parameter must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not symbol or not timeframe_str:
            return Response(
                {"error": "Missing required parameters: symbol, timeframe"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = MT5DataClient()

        tf_map = client.timeframes
        tf_constant = tf_map.get(timeframe_str.upper())
        if tf_constant is None:
            return Response(
                {"error": f"Invalid timeframe. Valid options: {list(tf_map.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        price_action = client.get_ohlc_from_pos(
            symbol_name=symbol, start_pos=0, count=count, timeframe=tf_constant
        )

        for ohlc in price_action:
            ohlc["iso_time"] = datetime.fromtimestamp(
                ohlc["time"], tz=client.timezone
            ).isoformat()

        return Response(
            {
                "symbol": symbol,
                "timeframe": timeframe_str.upper(),
                "count": len(price_action),
                "price_action": price_action,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            status=status.HTTP_200_OK,
        )

    except ValueError as e:
        # Invalid symbol, invalid count parameter, or no data available
        return Response(
            {"error": f"Invalid input or no data available: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    except RuntimeError as e:
        # MT5 terminal not connected
        return Response(
            {"error": f"MT5 connection error: {str(e)}"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    except (OSError, OverflowError) as e:
        # Timestamp conversion errors
        return Response(
            {"error": f"Date/time processing error: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:
        # Catch-all for unexpected errors
        return Response(
            {"error": f"Unexpected error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    finally:
        if client is not None:
            client.shutdown()


@api_view(["GET"])
def all_symbols(request):
    """
    Retrieve detailed metadata for all available trading symbols from MetaTrader 5.

    This endpoint provides comprehensive information about every symbol available on the broker,
    including classification, exchange details, precision settings, and market hierarchy.

    Args:
        request: Django REST Framework request object. No query parameters required.

    Returns:
        Response: JSON response with status 200 containing:
            {
                "count": int,
                "symbols": [
                    {
                        "name": str,
                        "description": str,
                        "exchange": str,
                        "isin": str,
                        "digits": int,
                        "point": float,
                        "class": str (parsed from path, e.g., 'Majors'),
                        "group": str (parsed from path, e.g., 'EURUSD')
                    },
                    ...
                ],
                "timestamp": str (ISO format)
            }

    Raises:
        HTTP 500 (Internal Server Error): Failed to retrieve symbols or parse symbol data,
                                          or unexpected errors during processing.
                                          Returns {"error": str}
        HTTP 503 (Service Unavailable): MT5 terminal not connected.
                                       Returns {"error": str}
    """
    client = None
    try:
        client = MT5DataClient()
        symbols = client.get_all_symbols()

        fields = ["name", "description", "exchange", "isin", "digits", "point"]
        data = []

        for sym in symbols:
            sym_data = {}

            # Safely parse the path (e.g., Forex\Majors\EURUSD)
            sym_meta = sym.get("path", "").split("\\")
            sym_data["class"] = sym_meta[1] if len(sym_meta) > 1 else "Unknown"
            sym_data["group"] = sym_meta[2] if len(sym_meta) > 2 else "Unknown"

            # Extract requested fields securely
            for field in fields:
                sym_data[field] = sym.get(field, None)

            data.append(sym_data)

        return Response(
            {
                "count": len(data),
                "symbols": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            status=status.HTTP_200_OK,
        )

    except ValueError as e:
        # Failed to retrieve symbols from MT5
        return Response(
            {"error": f"Failed to retrieve symbols: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    except RuntimeError as e:
        # MT5 terminal not connected
        return Response(
            {"error": f"MT5 connection error: {str(e)}"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    except (IndexError, KeyError) as e:
        # Error parsing symbol path or missing expected fields
        return Response(
            {"error": f"Failed to parse symbol data: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    except Exception as e:
        # Catch-all for unexpected errors
        return Response(
            {"error": f"Unexpected error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    finally:
        if client is not None:
            client.shutdown()


@api_view(["GET"])
def symbols(request):
    """
    Retrieve a lightweight list of all available trading symbol names.

    This endpoint provides a simple flat list of symbol names without metadata,
    optimized for frontend dropdowns and symbol selection interfaces.

    Args:
        request: Django REST Framework request object. No query parameters required.

    Returns:
        Response: JSON response with status 200 containing:
            {
                "count": int,
                "symbols": [str, str, ...],  # List of symbol names
                "timestamp": str (ISO format)
            }

    Raises:
        HTTP 500 (Internal Server Error): Failed to retrieve symbols or unexpected errors.
                                          Returns {"error": str}
        HTTP 503 (Service Unavailable): MT5 terminal not connected.
                                       Returns {"error": str}
    """
    client = None
    try:
        client = MT5DataClient()
        all_syms = client.get_all_symbols()

        # Extract just the 'name' field into a flat list
        supported_symbols = [sym["name"] for sym in all_syms]

        return Response(
            {
                "count": len(supported_symbols),
                "symbols": supported_symbols,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            status=status.HTTP_200_OK,
        )

    except ValueError as e:
        # Failed to retrieve symbols from MT5
        return Response(
            {"error": f"Failed to retrieve symbols: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    except RuntimeError as e:
        # MT5 terminal not connected
        return Response(
            {"error": f"MT5 connection error: {str(e)}"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    except Exception as e:
        # Catch-all for unexpected errors
        return Response(
            {"error": f"Unexpected error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    finally:
        if client is not None:
            client.shutdown()
