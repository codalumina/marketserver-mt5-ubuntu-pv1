import MetaTrader5 as mt5
import os
import sys
from dotenv import load_dotenv

# This script checks if a connection to the MetaTrader 5 terminal can be established.
# It exits with code 0 on success and 1 on failure.

def check_connection():
    """Tries to initialize the MT5 terminal connection."""
    try:
        load_dotenv()
        mt5_path = os.getenv('MT5_PATH')

        # Attempt to initialize connection with a 5-second timeout
        if not mt5.initialize(path=mt5_path, timeout=5000):
            print(f"Health check failed: Could not initialize. Reason: {mt5.last_error()}", file=sys.stderr)
            return False
        
        # A successful initialization means the terminal is responsive.
        print("Health check successful: MT5 terminal is responsive.")
        mt5.shutdown()
        return True

    except Exception as e:
        print(f"Health check failed with an exception: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    if check_connection():
        sys.exit(0)
    else:
        sys.exit(1)