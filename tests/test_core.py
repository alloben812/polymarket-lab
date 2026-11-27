import math

from pmlab import fees, stats
from pmlab.wallet import _key, _ts, build_markets, profile


def test_fee_formula_matches_docs_table():
    # docs: 100 shares at $0.50 with rate 0.05 -> $1.25; at $0.30 -> $1.05; symmetric around 0.5
    assert fees.taker_fee(100, 0.50, 0.05) == 1.25
    assert fees.taker_fee(100, 0.30, 0.05) == 1.05
    assert fees.taker_fee(100, 0.70, 0.05) == 1.05
    assert fees.taker_fee(100, 0.50, 0.01) == 0.25


def test_btc_rate_history_and_tiers():
    assert fees.btc_updown_rate(fees.FEE_CHANGE_TS - 1) == 0.07
    assert fees.btc_updown_rate(fees.FEE_CHANGE_TS) == 0.05
    assert fees.taker_rebate_rate(199_999) == 0.0 and fees.taker_rebate_rate(200_000) == 0.10
    assert fees.taker_rebate_rate(4.5e6) == 0.40 and fees.maker_rebate_rate(1.5e6) == 0.07
    assert abs(fees.implied_rate(-7.0, [(100, 0.5), (300, 0.5)]) - 0.07) < 1e-12


def test_cluster_ratio_is_wider_than_naive():
    num = [10.0, -8.0, 12.0, -9.0, 11.0]
    den = [100.0] * 5
    r, se, t = stats.ratio_cluster(num, den)
    assert abs(r - 0.032) < 1e-12 and se > 0 and abs(t) < 1.0  # five markets cannot prove an edge
    m, se2, _ = stats.mean_se([1.0, 1.0, 1.0])
    assert m == 1.0 and se2 == 0.0
    lo, hi = stats.wilson(5, 10)
    assert lo < 0.5 < hi
    assert stats.max_drawdown([1, -3, 1, -2, 5]) == 4


def test_time_parsing():
    assert _ts("2026-11-27T14:25:00Z") == 1795789500
    assert _ts("2026-11-27 14:50:16+00") == 1795791016
    assert _ts(None) is None


def _fill(side, outcome, size, price, ts, role, cond="0xc"):
    return {"side": side, "token_id": outcome, "condition_id": cond, "size": size, "price": price, "timestamp": ts,
            "slug": "btc-updown-5m-1795789200", "outcome": outcome, "transaction_hash": f"h{ts}{outcome}{price}", "role": role}


def test_market_accounting_buy_and_hold_pair():
    meta = {"0xc": {"slug": "btc-updown-5m-1795789200", "conditionId": "0xc", "endDate": "2026-11-27T14:25:00Z",
                    "eventStartTime": "2026-11-27T14:20:00Z", "outcomes": '["Up", "Down"]', "feeSchedule": {"rate": 0.05}}}
    res = {"0xc": {"resolved": True, "final": {"Up": 1.0, "Down": 0.0}}}
    fills = [_fill("BUY", "Up", 100, 0.40, 1795789260, "T"), _fill("BUY", "Down", 100, 0.55, 1795789300, "M")]
    mk = build_markets(fills, [], meta, res)
    m = mk[0]
    assert abs(m["gross"] - 5.0) < 1e-9           # 100 Up pays 100, cost 95
    assert abs(m["fee"] - 100 * 0.05 * 0.4 * 0.6) < 1e-9
    assert abs(m["net"] - (5.0 - 1.2)) < 1e-9 and not m["incomplete"]
    out = profile(fills, mk, res)
    assert out["summary"]["maker_share_usd"] == round(55 / 95, 3)


def test_selling_inventory_from_before_the_window_is_flagged():
    meta = {"0xc": {"slug": "some-market", "conditionId": "0xc", "endDate": "2026-11-27T14:25:00Z", "outcomes": '["Yes", "No"]', "feeSchedule": {"rate": 0.01}}}
    res = {"0xc": {"resolved": True, "final": {"Yes": 1.0, "No": 0.0}}}
    fills = [_fill("SELL", "Yes", 50, 0.9, 1795789260, "T")]
    mk = build_markets(fills, [], meta, res)
    assert mk[0]["incomplete"] is True


def test_split_then_sell_both_sides_is_complete():
    meta = {"0xc": {"slug": "some-market", "conditionId": "0xc", "endDate": "2026-11-27T14:25:00Z", "outcomes": '["Yes", "No"]', "feeSchedule": {"rate": 0.0}}}
    res = {"0xc": {"resolved": True, "final": {"Yes": 1.0, "No": 0.0}}}
    inv = [{"type": "SPLIT", "condition_id": "0xc", "size": 100, "usdc_size": 100, "timestamp": 1795789200}]
    fills = [_fill("SELL", "Yes", 100, 0.52, 1795789260, "M"), _fill("SELL", "No", 100, 0.50, 1795789270, "M")]
    m = build_markets(fills, inv, meta, res)[0]
    assert not m["incomplete"] and abs(m["gross"] - 2.0) < 1e-9   # sold a $1 set for $1.02


def test_role_key_is_stable():
    r = {"transaction_hash": "0xa", "token_id": "1", "side": "BUY", "price": 0.6779666667, "size": 30.0, "timestamp": 5}
    assert _key(r) == _key(dict(r))
    assert math.isclose(_key(r)[3], 0.67796667)
