# taobo-O'Neil · 追踪记录 Schema（track-log）

> 每只被追踪个股一个 JSON 文件：`deliverables/oneil-position/tracks/<code>.json`
> 双轨：`mode=SIMULATION`（虚拟仓）/ `mode=REAL`（实盘）

## JSON Schema

```json
{
  "code": "600519",
  "name": "贵州茅台",
  "mode": "SIMULATION",
  "state": "WATCH",
  "source_signal": {
    "skill": "taobo-O'Neil",
    "date": "2026-08-06",
    "buy_pattern": "C13杯柄突破",
    "trigger_price": 1510.00
  },
  "position": {
    "target_pct_total": 20,
    "builds": [
      {"stage": 1, "ratio": 0.50, "pct_total": 10, "price": 1510.00, "shares": 1000, "date": "2026-08-06"},
      {"stage": 2, "ratio": 0.30, "pct_total": 6, "price": 1540.00, "shares": 600, "date": "2026-08-07"},
      {"stage": 3, "ratio": 0.20, "pct_total": 4, "price": 1570.00, "shares": 400, "date": "2026-08-10"}
    ],
    "avg_cost": 1525.00,
    "total_shares": 2000
  },
  "trailing": {
    "mode": "albrooks",
    "be_line_pct": 3,
    "start_line_pct": 10,
    "anchor_type": "swing_low",
    "anchor_price": 1560.00,
    "pad_pct": 1.5,
    "updated_at": "2026-08-12"
  },
  "stop": {
    "type": "cost_based",
    "pct": -8,
    "stop_price": 1403.00
  },
  "events": [
    {"date": "2026-08-06", "type": "build", "stage": 1, "price": 1510.00, "note": "建仓50%(目标仓位)"},
    {"date": "2026-08-09", "type": "be", "price": 1525.00, "note": "浮盈+3% BE保护"},
    {"date": "2026-08-12", "type": "anchor_up", "price": 1560.00, "note": "新更高低点，锚上移"},
    {"date": "2026-08-20", "type": "sell_all", "price": 1760.00, "note": "收盘跌破锚1640"}
  ],
  "result": {
    "closed_at": "2026-08-20",
    "total_return_pct": 15.8,
    "hold_days": 46,
    "max_drawdown_pct": -5.4,
    "pnl_sim": 15800.0
  }
}
```

## 字段说明

| 字段 | 说明 |
|------|------|
| `state` | IDLE / WATCH / OPEN / MANAGING / CLOSED |
| `mode` | SIMULATION（触发价模拟）/ REAL（实际成本与操作） |
| `position.builds[].ratio` | 占**单票目标仓位**比例（0.50/0.30/0.20） |
| `position.builds[].pct_total` | 占总资金比例（10/6/4） |
| `trailing.anchor_price` | 当前移动止盈锚（swing low 或均线），只上不下 |
| `stop.stop_price` | 单票成本价 -8%（成本上方时止损让位于移动锚） |
| `events` | 全信号流水（建仓/加仓/BE/锚上移/减仓/清仓） |
| `result` | CLOSED 时的全程收益总结 |

## 主索引

`deliverables/oneil-position/tracks/index.json`：所有追踪标的的轻量索引（code/name/state/mode/最近信号），供每日复盘快速读取。

## 退出优先级（引擎判定顺序）

1. **清仓-止损**：收盘 ≤ 成本价 -8%（未盈利期兜底）
2. **清仓-移动锚**：收盘跌破移动止盈锚（锚 ≥ 成本价后，止损让位于锚）
3. **减仓-混合锁定**：hybrid 模式达 +20~25% 锁定 1/3~1/2
4. **区间市**：横盘不再创新高 → 区间上沿减仓/离场
5. **到期**：TRACK_DAYS（250 交易日）未清仓按市价了结
