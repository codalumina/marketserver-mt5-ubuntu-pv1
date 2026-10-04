import os
from dotenv import load_dotenv
from datetime import datetime
import pytz
import pandas as pd

# --- OS-Agnostic MT5 Import ---
try:
    import MetaTrader5 as mt5
except ImportError:
    from unittest.mock import MagicMock
    print("WARNING: MetaTrader5 module not found. Using Mock object (Safe for local testing).")
    mt5 = MagicMock()
# ------------------------------


class MT5DataClient:
    def __init__(self):
        try:
            load_dotenv()
            self.login = int(os.getenv('MT5_LOGIN'))
            self.password = os.getenv('MT5_PASSWORD')
            self.server = os.getenv('MT5_SERVER')
            self.timezone_str = os.getenv('MT5_TIMEZONE', 'Etc/UTC')
            self.path = os.getenv('MT5_PATH')
        except (TypeError, ValueError) as e:
            raise ValueError("Failed to load environment variables. Check your .env file and ensure MT5_LOGIN, MT5_PASSWORD, and MT5_SERVER are set correctly.") from e

        if not mt5.initialize(path=self.path):
            raise RuntimeError(f"Initialisation error: {mt5.last_error()}")
        self.connected = True
        self.terminal_info = mt5.terminal_info()._asdict()

        try:
            self.authorised = mt5.login(
                self.login, password=self.password, server=self.server)
        except Exception as e:
            raise ValueError("Authorisation error")

        self.timezone = pytz.timezone(self.timezone_str)
        self._initialisedAt = datetime.now()

    @property
    def total_symbols(self):
        if not self.connected:
            total_symbols = 0
        else:
            total_symbols = mt5.symbols_total()
        return total_symbols

    @property
    def timeframes(self):
        timeframe_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
            "W1": mt5.TIMEFRAME_W1,
            "MN1": mt5.TIMEFRAME_MN1
        }
        return timeframe_map

    def get_targeted_symbols(self, symbol_list):
        if not self.connected:
            raise RuntimeError("MT5 terminal not connected")
        
        results =[]
        for sym in symbol_list:
            # Force the symbol into Market Watch for live tick data
            mt5.symbol_select(sym, True)
            
            # Fetch the data
            info = mt5.symbol_info(sym)
            if info is not None:
                results.append(info._asdict())
                
        if len(results) == 0:
            raise ValueError("Failed to retrieve data for the provided symbols.")
            
        return results

    def get_symbol(self, symbol_name):
        if not self.connected:
            raise RuntimeError("MT5 terminal not connected")
        # CRITICAL FIX: Force MT5 to add the symbol to Market Watch
        mt5.symbol_select(symbol_name, True)
        symbol = mt5.symbol_info(symbol_name)
        if symbol is None:
            raise ValueError(f"Failed to get symbol info for {symbol}")
        return symbol._asdict()

    def get_last_tick(self, symbol_name):
        if not self.connected:
            raise RuntimeError("MT5 terminal not connected")
        tick = mt5.symbol_info_tick(symbol_name)
        if tick is None:
            raise ValueError(f"Failed to get tick info for {symbol_name}")
        return tick._asdict()

    def get_ohlc_from(self, symbol_name, timeframe, from_date: datetime, count=1000):
        if not self.connected:
            raise RuntimeError("MT5 terminal not connected")
        utc_from = datetime(from_date.year, from_date.month, from_date.day,
                            from_date.hour, from_date.minute, from_date.second,  tzinfo=self.timezone)
        rates = mt5.copy_rates_from(symbol_name, timeframe, utc_from, count)
        if rates is None or len(rates) == 0:
            raise ValueError(f"Failed to get OHLC data for {symbol_name}")
        rates_df = pd.DataFrame(rates)
        return rates_df.to_dict(orient='records')

    def get_ohlc_from_pos(self, symbol_name, timeframe, start_pos=0, count=100):
        if not self.connected:
            raise RuntimeError("MT5 terminal not connected")
        rates = mt5.copy_rates_from_pos(
            symbol_name, timeframe, start_pos, count)
        if rates is None or len(rates) == 0:
            raise ValueError(f"Failed to get OHLC data for {symbol_name}")
        rates_df = pd.DataFrame(rates)
        return rates_df.to_dict(orient='records')

    def get_ohlc_range(self, symbol_name, timeframe, from_date: datetime, to_date: datetime):
        if not self.connected:
            raise RuntimeError("MT5 terminal not connected")
        utc_from = datetime(from_date.year, from_date.month, from_date.day,
                            from_date.hour, from_date.minute, from_date.second,  tzinfo=self.timezone)
        utc_to = datetime(to_date.year, to_date.month, to_date.day, to_date.hour,
                          to_date.minute, to_date.second,  tzinfo=self.timezone)
        rates = mt5.copy_rates_range(symbol_name, timeframe, utc_from, utc_to)
        if rates is None or len(rates) == 0:
            raise ValueError(f"Failed to get OHLC data for {symbol_name}")
        rates_df = pd.DataFrame(rates)
        return rates_df.to_dict(orient='records')

    def get_ticks_from(self, symbol_name, from_date: datetime, count=10000, flags=mt5.COPY_TICKS_ALL):
        if not self.connected:
            raise RuntimeError("MT5 terminal not connected")
        utc_from = datetime(from_date.year, from_date.month, from_date.day,
                            from_date.hour, from_date.minute, from_date.second,  tzinfo=self.timezone)
        ticks = mt5.copy_ticks_from(symbol_name, utc_from, count, flags)
        if ticks is None or len(ticks) == 0:
            raise ValueError(f"Failed to get ticks data for {symbol_name}")
        ticks_df = pd.DataFrame(ticks)
        return ticks_df.to_dict(orient='records')

    def get_ticks_range(self, symbol_name, from_date: datetime, to_date: datetime, flags=mt5.COPY_TICKS_ALL):
        if not self.connected:
            raise RuntimeError("MT5 terminal not connected")
        utc_from = datetime(from_date.year, from_date.month, from_date.day,
                            from_date.hour, from_date.minute, from_date.second,  tzinfo=self.timezone)
        utc_to = datetime(to_date.year, to_date.month, to_date.day, to_date.hour,
                          to_date.minute, to_date.second,  tzinfo=self.timezone)
        ticks = mt5.copy_ticks_range(symbol_name, utc_from, utc_to, flags)
        if ticks is None or len(ticks) == 0:
            raise ValueError(f"Failed to get ticks data for {symbol_name}")
        ticks_df = pd.DataFrame(ticks)
        return ticks_df.to_dict(orient='records')

    def get_account_info(self):
        if not self.connected:
            raise RuntimeError("MT5 terminal not connected")
        account_info = mt5.account_info()._asdict()
        if account_info is None:
            raise ValueError(f"Failed to get account info")
        return account_info

    def get_all_symbols(self, group="*"):
        if not self.connected:
            raise RuntimeError("MT5 terminal not connected")
        symbols = mt5.symbols_get(group=group)
        if symbols is None or len(symbols) == 0:
            raise ValueError(f"Failed to get symbols")
        s = [symbol._asdict() for symbol in symbols]
        # symbols_df = pd.DataFrame(s)
        # return symbols_df.to_dict(orient='records')
        return s


    def get_last_error(self):
        return mt5.last_error()

    def is_connected(self):
        try:
            return mt5.terminal_info().connected
        except Exception as e:
            return False

    def shutdown(self):
        if self.connected:
            mt5.shutdown()
            self.connected = False

    def __repr__(self):
        return f"MT5DataClient(login={self.login}, server={self.server}, connected={self.connected}, authorised={self.authorised}, terminal_info={self.terminal_info}, timezone={self.timezone}, initialisedAt={self._initialisedAt})"

    def __str__(self):
        return f"MT5DataClient(login={self.login}, server={self.server}, connected={self.connected}, authorised={self.authorised}, terminal_info={self.terminal_info}, timezone={self.timezone}, initialisedAt={self._initialisedAt})"


# if __name__ == "__main__":
#     mt5_client = MT5DataClient()
#     print(mt5_client.terminal_info)
#     mt5_client.shutdown()