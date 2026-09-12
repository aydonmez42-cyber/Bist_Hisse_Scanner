import math
import pandas as pd

import config as cfg
from data_manager import fetch_klines
from indicators import add_indicators
from strategy import long_signal, short_signal, exit_signal


def execution_price(price, side, is_entry, slippage):
    if (side == "LONG" and is_entry) or (side == "SHORT" and not is_entry):
        return price * (1 + slippage)
    return price * (1 - slippage)


def commission(notional):
    return notional * cfg.FEE_RATE


def build_exit_levels(side, entry_price, atr_value):
    levels = {"stop_loss": None, "take_profit": None, "trailing_stop": None,
              "trail_active": False, "highest_price": entry_price,
              "lowest_price": entry_price}
    if not pd.notna(atr_value) or atr_value <= 0:
        raise ValueError("ATR is invalid at entry; cannot initialize ATR exits.")
    if side == "LONG":
        if cfg.USE_ATR_SL:
            levels["stop_loss"] = entry_price - atr_value * cfg.ATR_SL_MULTIPLIER
        if cfg.USE_ATR_TP:
            levels["take_profit"] = entry_price + atr_value * cfg.ATR_TP_MULTIPLIER
    else:
        if cfg.USE_ATR_SL:
            levels["stop_loss"] = entry_price + atr_value * cfg.ATR_SHORT_SL_MULTIPLIER
        if cfg.USE_ATR_TP:
            levels["take_profit"] = entry_price - atr_value * cfg.ATR_TP_MULTIPLIER
    levels["entry_atr"] = atr_value
    return levels


def apply_slippage_to_exit(level, side):
    return level * (1 - cfg.SLIPPAGE_RATE) if side == "LONG" else level * (1 + cfg.SLIPPAGE_RATE)


def check_intrabar_exit(position, row, levels):
    high, low = float(row["high"]), float(row["low"])
    stop, tp, trail = levels.get("stop_loss"), levels.get("take_profit"), levels.get("trailing_stop")
    if position == "LONG":
        if stop is not None and low <= stop: return "ATR_SL", stop
        if trail is not None and low <= trail: return "ATR_TRAILING_SL", trail
        if tp is not None and high >= tp: return "ATR_TP", tp
    else:
        if stop is not None and high >= stop: return "ATR_SL", stop
        if trail is not None and high >= trail: return "ATR_TRAILING_SL", trail
        if tp is not None and low <= tp: return "ATR_TP", tp
    return None, None


def update_trailing(position, row, levels):
    entry, atr = levels["entry_price"], levels["entry_atr"]
    if position == "LONG":
        levels["highest_price"] = max(levels["highest_price"], float(row["high"]))
        if cfg.USE_ATR_TRAILING and levels["highest_price"] >= entry + atr * cfg.ATR_TRAIL_ACTIVATION:
            levels["trail_active"] = True
            new = levels["highest_price"] - atr * cfg.ATR_TRAIL_MULTIPLIER
            levels["trailing_stop"] = new if levels["trailing_stop"] is None else max(levels["trailing_stop"], new)
    else:
        levels["lowest_price"] = min(levels["lowest_price"], float(row["low"]))
        if cfg.USE_ATR_TRAILING and levels["lowest_price"] <= entry - atr * cfg.ATR_TRAIL_ACTIVATION:
            levels["trail_active"] = True
            new = levels["lowest_price"] + atr * cfg.ATR_TRAIL_MULTIPLIER
            levels["trailing_stop"] = new if levels["trailing_stop"] is None else min(levels["trailing_stop"], new)


def close_position(position, px, row, entry_price, entry_fee, reason, equity):
    qty = cfg.POSITION_QTY_ETH
    pnl_gross = (px - entry_price) * qty if position == "LONG" else (entry_price - px) * qty
    exit_fee = commission(abs(px * qty))
    pnl_net = pnl_gross - entry_fee - exit_fee
    equity += pnl_gross - exit_fee
    trade = {
        "entry_time": row["entry_time_for_trade"], "exit_time": row.name,
        "side": position, "symbol": cfg.LONG_SYMBOL if position == "LONG" else cfg.SHORT_SYMBOL,
        "qty_eth": qty, "entry_price": entry_price, "exit_price": px,
        "gross_pnl": pnl_gross, "fees": entry_fee + exit_fee,
        "net_pnl": pnl_net, "return_pct_on_equity": pnl_net / max(equity - pnl_net, 1e-12),
        "reason": reason,
    }
    return trade, equity


def run_backtest(signal_df, long_df, short_df):
    long_map = long_df.set_index("open_time")
    short_map = short_df.set_index("open_time")
    common = signal_df[signal_df["open_time"].isin(long_map.index) & signal_df["open_time"].isin(short_map.index)].reset_index(drop=True)

    equity = cfg.INITIAL_CAPITAL
    position = None
    entry_price = None
    entry_time = None
    entry_fee = 0.0
    exit_levels = None
    pending_entry = None
    pending_ema_exit = False
    trades, equity_curve = [], []

    for i in range(len(common)):
        sig = common.iloc[i]
        t = sig["open_time"]
        long_row = long_map.loc[t]
        short_row = short_map.loc[t]
        exec_row = long_row if position == "LONG" or (pending_entry and pending_entry["side"] == "LONG") else short_row

        if pending_ema_exit and position is not None:
            exec_row = long_row if position == "LONG" else short_row
            px = execution_price(float(exec_row["open"]), position, False, cfg.SLIPPAGE_RATE)
            tr = exec_row.copy(); tr["entry_time_for_trade"] = entry_time
            trade, equity = close_position(position, px, tr, entry_price, entry_fee, "EMA100_CLOSE", equity)
            trades.append(trade)
            position = entry_price = entry_time = None; entry_fee = 0.0; exit_levels = None; pending_ema_exit = False

        if pending_entry is not None and position is None:
            side = pending_entry["side"]
            exec_row = long_row if side == "LONG" else short_row
            px = execution_price(float(exec_row["open"]), side, True, cfg.SLIPPAGE_RATE)
            entry_fee = commission(abs(px * cfg.POSITION_QTY_ETH))
            equity -= entry_fee
            position, entry_price, entry_time = side, px, exec_row.name
            exit_levels = build_exit_levels(side, entry_price, pending_entry["atr"])
            exit_levels["entry_price"] = entry_price
            pending_entry = None

            if position == "LONG":
                if exit_levels["stop_loss"] is not None and float(exec_row["open"]) <= exit_levels["stop_loss"]: exit_levels["stop_loss"] = float(exec_row["open"])
                if exit_levels["take_profit"] is not None and float(exec_row["open"]) >= exit_levels["take_profit"]: exit_levels["take_profit"] = float(exec_row["open"])
            else:
                if exit_levels["stop_loss"] is not None and float(exec_row["open"]) >= exit_levels["stop_loss"]: exit_levels["stop_loss"] = float(exec_row["open"])
                if exit_levels["take_profit"] is not None and float(exec_row["open"]) <= exit_levels["take_profit"]: exit_levels["take_profit"] = float(exec_row["open"])

        if position is not None and exit_levels is not None:
            exec_row = long_row if position == "LONG" else short_row
            reason, raw_px = check_intrabar_exit(position, exec_row, exit_levels)
            if reason is not None:
                px = apply_slippage_to_exit(raw_px, position)
                tr = exec_row.copy(); tr["entry_time_for_trade"] = entry_time
                trade, equity = close_position(position, px, tr, entry_price, entry_fee, reason, equity)
                trades.append(trade)
                position = entry_price = entry_time = None; entry_fee = 0.0; exit_levels = None
            else:
                update_trailing(position, exec_row, exit_levels)

        mark_row = long_row if position == "LONG" else short_row if position == "SHORT" else long_row
        marked_equity = equity
        if position is not None:
            if position == "LONG": marked_equity += (float(long_row["close"]) - entry_price) * cfg.POSITION_QTY_ETH
            else: marked_equity += (entry_price - float(short_row["close"])) * cfg.POSITION_QTY_ETH
        equity_curve.append({"time": sig["close_time"], "equity": marked_equity, "position": position or "FLAT"})

        if i < len(common) - 1 and position is not None and cfg.USE_EMA100_EXIT and exit_signal(position, sig):
            pending_ema_exit = True
        if i < len(common) - 1 and position is None and pending_entry is None:
            if long_signal(common, i, cfg): pending_entry = {"side": "LONG", "atr": float(sig["atr"])}
            elif short_signal(common, i, cfg): pending_entry = {"side": "SHORT", "atr": float(sig["atr"])}

    if position is not None:
        exec_row = long_map.loc[common.iloc[-1]["open_time"]] if position == "LONG" else short_map.loc[common.iloc[-1]["open_time"]]
        px = execution_price(float(exec_row["close"]), position, False, cfg.SLIPPAGE_RATE)
        tr = exec_row.copy(); tr["entry_time_for_trade"] = entry_time
        trade, equity = close_position(position, px, tr, entry_price, entry_fee, "END_OF_DATA", equity)
        trades.append(trade)

    return pd.DataFrame(trades), pd.DataFrame(equity_curve), equity


def calculate_metrics(trades, equity_curve):
    if equity_curve.empty: return {}
    eq = equity_curve["equity"]; max_dd = (eq / eq.cummax() - 1.0).min()
    net_profit = trades["net_pnl"].sum() if not trades.empty else 0.0
    wins = trades[trades["net_pnl"] > 0] if not trades.empty else pd.DataFrame()
    losses = trades[trades["net_pnl"] <= 0] if not trades.empty else pd.DataFrame()
    gross_profit = wins["net_pnl"].sum() if not wins.empty else 0.0
    gross_loss = abs(losses["net_pnl"].sum()) if not losses.empty else 0.0
    pf = gross_profit / gross_loss if gross_loss else math.inf
    longs = trades[trades["side"] == "LONG"] if not trades.empty else pd.DataFrame()
    shorts = trades[trades["side"] == "SHORT"] if not trades.empty else pd.DataFrame()
    return {"initial_capital": cfg.INITIAL_CAPITAL, "final_equity": float(eq.iloc[-1]), "net_profit": float(net_profit),
            "return_pct": float((eq.iloc[-1]/cfg.INITIAL_CAPITAL-1)*100), "trades": int(len(trades)),
            "wins": int(len(wins)), "losses": int(len(losses)), "win_rate_pct": float(len(wins)/len(trades)*100) if len(trades) else 0,
            "profit_factor": float(pf), "expectancy_per_trade": float(net_profit/len(trades)) if len(trades) else 0,
            "max_drawdown_pct": float(max_dd*100), "long_trades": int(len(longs)), "short_trades": int(len(shorts)),
            "long_win_rate_pct": float((longs["net_pnl"]>0).mean()*100) if len(longs) else 0,
            "short_win_rate_pct": float((shorts["net_pnl"]>0).mean()*100) if len(shorts) else 0}


def main():
    print(f"Downloading Futures data: {cfg.LONG_SYMBOL} / {cfg.SHORT_SYMBOL} {cfg.INTERVAL}...")
    signal_df = fetch_klines(cfg.SIGNAL_SYMBOL, cfg.INTERVAL, cfg.DATA_START, cfg.DATA_END)
    long_df = fetch_klines(cfg.LONG_SYMBOL, cfg.INTERVAL, cfg.DATA_START, cfg.DATA_END, market_type="COIN_M")
    short_df = fetch_klines(cfg.SHORT_SYMBOL, cfg.INTERVAL, cfg.DATA_START, cfg.DATA_END, market_type="USD_M")
    print(f"Rows: signal={len(signal_df):,}, long={len(long_df):,}, short={len(short_df):,}")
    signal_df = add_indicators(signal_df, cfg)
    print(f"TEST 17 | Fixed {cfg.POSITION_QTY_ETH} ETH | LONG ETHUSD (COIN-M) | SHORT ETHUSDT (USD-M) | RSI long > {cfg.RSI_LONG_THRESHOLD} | RSI short < {cfg.RSI_SHORT_THRESHOLD}")
    trades, equity_curve, final_equity = run_backtest(signal_df, long_df, short_df)
    metrics = calculate_metrics(trades, equity_curve)
    trades.to_csv(cfg.TRADES_CSV, index=False); equity_curve.to_csv(cfg.EQUITY_CSV, index=False)
    print("\n========== TEST 16 RESULT ==========")
    for k,v in metrics.items(): print(f"{k:25s}: {v:.4f}" if isinstance(v,float) else f"{k:25s}: {v}")
    print("====================================")

if __name__ == "__main__": main()
