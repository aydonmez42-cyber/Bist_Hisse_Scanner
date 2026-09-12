# Binance 4H Trend-Cross Trading Bot
# Baseline + ATR risk/exit configuration

SIGNAL_SYMBOL = "ETHUSDT"
LONG_SYMBOL = "ETHUSD_PERP"
SHORT_SYMBOL = "ETHUSDT"
INTERVAL = "1d"

# Indicator parameters
EMA_FAST = 50
EMA_SLOW = 200
ADX_LENGTH = 14
ADX_THRESHOLD = 25

# Supertrend filter
SUPERTREND_PERIOD = 10
SUPERTREND_MULTIPLIER = 6.0
# Bollinger Bands (TEST 11: short-side re-entry filter)
BB_LENGTH = 20
BB_STD_MULTIPLIER = 2.0
USE_BB_SHORT_FILTER = False
CCI_LENGTH = 20
CCI_LONG_THRESHOLD = 100.0
CCI_SHORT_THRESHOLD = -50
RSI_LENGTH = 14
RSI_LONG_THRESHOLD = 55
RSI_SHORT_THRESHOLD = 30

STOCH_RSI_RSI_LENGTH = 14
STOCH_RSI_STOCH_LENGTH = 14
STOCH_RSI_K_SMOOTH = 3
STOCH_RSI_D_SMOOTH = 3
STOCH_LONG_THRESHOLD = 20
STOCH_LONG_D_THRESHOLD = 30.0
STOCH_SHORT_THRESHOLD = 80

# Historical condition validity
CCI_VALID_BARS = 1
STOCH_VALID_BARS = 3

# ATR risk / exit model
ATR_LENGTH = 14
ATR_SL_MULTIPLIER = 3.0
ATR_SHORT_SL_MULTIPLIER = 1.5       # TEST 1: Initial stop distance = ATR * 2.0
ATR_TP_MULTIPLIER = 4.0       # TEST 1: Take-profit distance = ATR * 4.0
ATR_TRAIL_ACTIVATION = 2.0    # TEST 1: Activate trailing after +2 ATR unrealized
ATR_TRAIL_MULTIPLIER = 2.0    # TEST 1: Trail distance = ATR * 2.0

USE_ATR_SL = True
USE_ATR_TP = True
USE_ATR_TRAILING = True
USE_EMA100_EXIT = False

# Backtest execution / costs
INITIAL_CAPITAL = 10000.0
POSITION_QTY_ETH = 1.0        # Fixed position size: exactly 1 ETH per trade
POSITION_SIZE_PCT = 1.0       # Kept for compatibility; NOT used for sizing in TEST 16
LEVERAGE = 1.0
FEE_RATE = 0.0004            # 0.04% per side
SLIPPAGE_RATE = 0.0002       # 0.02% assumed execution slippage

# Backtest data
DATA_START = "2020-01-01"
DATA_END = None              # e.g. "2026-09-01"

# Output
TRADES_CSV = "backtest_trades.csv"
EQUITY_CSV = "backtest_equity.csv"


# TEST 16: Fixed 1 ETH. LONG executes on ETHUSDT; SHORT executes on ETHUSDC.
# Signals/indicators are generated from ETHUSDT; execution/exits use the selected contract.
# RSI short threshold remains <30 from TEST 15.

# TEST 26 - MACD Long momentum filter
MACD_FAST_LENGTH = 12
MACD_SLOW_LENGTH = 26
MACD_SIGNAL_LENGTH = 9
USE_MACD_LONG_FILTER = True
