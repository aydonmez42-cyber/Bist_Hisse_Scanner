# TEST 20

- Timeframe: 4h
- Signal source: ETHUSDT Futures
- LONG: ETHUSD_PERP (Binance COIN-M), modeled at fixed 1 ETH exposure
- SHORT: ETHUSDT (Binance USD-M), fixed 1 ETH exposure
- Long RSI: >55
- Short RSI: <30
- Supertrend: 10 / 7.5
- EMA: 50 / 200
- ADX: >25
- Bollinger: OFF
- Long SL: 2 ATR
- Short SL: 1.5 ATR
- TP: 4 ATR
- Trailing: activates +2 ATR, distance 2 ATR
- EMA exit: OFF

Run on Railway SSH:
`python backtest.py`

Note: ETHUSD_PERP is Binance COIN-M. This backtest models a fixed 1 ETH economic exposure; actual live COIN-M order sizing must account for the contract size and inverse contract mechanics.


TEST 22: Baz TEST 20. Long Stoch RSI koşulu: K, D'yi yukarı keser ve D > 30. Diğer parametreler değiştirilmemiştir.


TEST 23: TEST 22 baz alınmıştır. Long CCI koşulu +50 olarak korunmuş, CCI_VALID_BARS 3'ten 1'e indirilmiştir. Diğer parametreler değiştirilmemiştir.


TEST 24: TEST 23 baz alınmıştır. Long CCI eşiği +50'den +100'e çıkarılmıştır. ADX >25 ve diğer tüm parametreler aynıdır.


TEST 25A: TEST 24 baz alınmıştır. Long ATR Stop Loss 2.0 -> 2.5 ATR olarak değiştirilmiştir. Short ATR SL 1.5 ATR olarak korunmuştur. Diğer parametreler aynıdır.


TEST 25B: TEST 25A baz alınmıştır. Long ATR Stop Loss 2.5 -> 3.0 ATR olarak değiştirilmiştir. Short ATR SL 1.5 ATR olarak korunmuştur. Diğer parametreler aynıdır.


TEST 26: TEST 25B baz alınmıştır. Yalnızca Long tarafına MACD(12,26,9) momentum filtresi eklenmiştir: MACD line > Signal ve histogram > 0. Short tarafı değişmemiştir.

TEST 26B: Daily (1D) timeframe variant of TEST 26. Only INTERVAL is changed from 4h to 1d; all strategy/risk parameters remain unchanged.
