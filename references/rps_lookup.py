"""陶博士 RPS 真实取数桥接 (方案A: 通达信 EXTDATA) —— 自包含, 仅标准库。

数据根 (用户机器固定):
  D:\\Sofeware\\TongDaXin\\T0002\\extdata\\extdata_{sid}.{dat,idx}

结构 (已逆向 + 全 ID 精确验证, 2026-08-07):
  .idx 记录 = 固定 29 字节: [0:2]保留 / [2:8] 6位ASCII代码 / [8:25]0填充 / [25:29] 该股票记录数 count(uint32 LE)
  .dat = 变长紧打包, 与 .idx 顺序一一对应: 股票 i 数据起始 = Σ(count[0..i-1])*12, 段长 count[i]*12
  每条记录 12 字节: date(uint32 LE,YYYYMMDD) + 保留4 + value(float32); 存储值 = RPS*10 → RPS = value/10

ID 映射:
  个股: 1=RPS250 2=RPS120 3=RPS50 4=RPS20 5=RPS10
  板块: 11=板块RPS5 12=板块RPS10 13=板块RPS20

提供:
  get_stock_rps(code)  -> {'RPS250':..,'RPS120':..,'RPS50':..,'RPS20':..,'RPS10':..} 或 None
  get_sector_rps(code) -> {'RPS5':..,'RPS10':..,'RPS20':..} 或 None   (code=880xxx板块 / 399xxx指数)
  get_stock_rps_series(code) -> {'RPS250':[(d,rps)...], ...} 或 None
  get_sector_rps_series(code) -> {'RPS5':[(d,rps)...], ...} 或 None   (板块全序列)
  asof(series, date)   -> 取 <=date 最近一条值 (无前视, 回测取历史RPS用)
  eval_c4c5c6(rps)     -> {'C4':bool,'C5':bool,'C6':bool}  按陶博士锚定定义
  build_block_map()    -> (个股->880xxx板块, 880xxx->中文名)  解析 infoharbor_block.dat
  get_stock_boards(code) -> [(880xxx, 中文名), ...]  所属板块
  get_double_rps(code) -> 双RPS共振判定 (个股RPS + 所属板块RPS)

CLI:
  python rps_lookup.py 600999            # 个股 RPS + C4/C5/C6 判定
  python rps_lookup.py --sector 880575   # 板块 RPS
  python rps_lookup.py --double 600999   # 双RPS 共振判定
  python rps_lookup.py 600999 --json
"""
import os
import sys
import json
import re
import struct
import argparse

TDX = r"D:\Sofeware\TongDaXin"
ED = os.path.join(TDX, "T0002", "extdata")
RECORD = 12
_IDX_CACHE = {}      # sid -> (codes, counts, offsets)  避免重复读 idx

# 个股 RPS ID
STOCK_IDS = {"RPS250": "1", "RPS120": "2", "RPS50": "3", "RPS20": "4", "RPS10": "5"}
# 板块 RPS ID
SECTOR_IDS = {"RPS5": "11", "RPS10": "12", "RPS20": "13"}

# 陶博士锚定阈值 (不可修改)
RPS_LINE = 90.0          # 一线红/三线红门槛
RPS_RELAX = 85.0         # C4 放宽门槛 (基本面特别优秀品种)

# 双RPS: 个股 -> 所属 880xxx 板块 映射 (infoharbor_block.dat 文本格式)
HC = os.path.join(TDX, "T0002", "hq_cache")
INFOHARBOR = os.path.join(HC, "infoharbor_block.dat")
_BOARD_RE = re.compile(r"^(880|881|882|883)\d{3}$")
_MEM_RE = re.compile(r"^(\d)#(\d{6})$")
_BLOCK_MAP = None        # code -> set(880xxx板块码)
_BOARD_NAMES = None      # 880xxx板块码 -> 中文名
_BOARD_IS_GN = None      # 880xxx板块码 -> bool(是否概念板块 #GN_；False=风格板块 #FG_，不参与best_board/共振)


def is_valid_date(d):
    return 19900101 <= d <= 20301231


def _load_index(sid):
    if sid in _IDX_CACHE:
        return _IDX_CACHE[sid]
    idx_path = os.path.join(ED, f"extdata_{sid}.idx")
    with open(idx_path, "rb") as f:
        idx = f.read()
    n = len(idx) // 29
    codes, counts, offsets = [], [], [0]
    for i in range(n):
        codes.append(idx[i * 29 + 2:i * 29 + 8].decode())
        counts.append(struct.unpack("<I", idx[i * 29 + 25:i * 29 + 29])[0])
    for c in counts[:-1]:
        offsets.append(offsets[-1] + c * RECORD)
    _IDX_CACHE[sid] = (codes, counts, offsets)
    return _IDX_CACHE[sid]


def _read_series(sid, code):
    dat_path = os.path.join(ED, f"extdata_{sid}.dat")
    codes, counts, offsets = _load_index(sid)
    if code not in codes:
        return None
    i = codes.index(code)
    off = offsets[i]
    cnt = counts[i]
    with open(dat_path, "rb") as f:
        f.seek(off)
        raw = f.read(cnt * RECORD)
    series = []
    for r in range(cnt):
        o = r * RECORD
        d = struct.unpack("<I", raw[o:o + 4])[0]
        v = struct.unpack("<f", raw[o + 8:o + 12])[0]
        if not is_valid_date(d):
            break
        series.append((d, v / 10.0))
    return series


def get_stock_rps(code):
    """返回 {RPS250,RPS120,RPS50,RPS20,RPS10} 最新值 (date 统一为该代码最新日期)。"""
    out = {}
    for name, sid in STOCK_IDS.items():
        s = _read_series(sid, code)
        if s:
            out[name] = round(s[-1][1], 1)
    return out or None


def get_stock_rps_series(code):
    """返回 {RPS250:[(d,rps)...], ...} 全序列。"""
    out = {}
    for name, sid in STOCK_IDS.items():
        s = _read_series(sid, code)
        if s:
            out[name] = s
    return out or None


def get_sector_rps(code):
    """返回 {RPS5,RPS10,RPS20} 最新值 (板块代码 880xxx / 指数 399xxx)。"""
    out = {}
    for name, sid in SECTOR_IDS.items():
        s = _read_series(sid, code)
        if s:
            out[name] = round(s[-1][1], 1)
    return out or None


def get_sector_rps_series(code):
    """返回 {RPS5:[(d,rps)...], RPS10:..., RPS20:...} 板块全序列 (回测取历史用)。"""
    out = {}
    for name, sid in SECTOR_IDS.items():
        s = _read_series(sid, code)
        if s:
            out[name] = s
    return out or None


def asof(series, date):
    """series: list[(date,val)] 升序。返回 <=date 的最后一条 val；无则 None。

    用于回测：在给定信号日取「当日或之前最近」的 RPS 值 (无前视)。"""
    import bisect
    if not series:
        return None
    dates = [x[0] for x in series]
    i = bisect.bisect_right(dates, date) - 1
    return series[i][1] if i >= 0 else None


def eval_c4c5c6(rps):
    """按陶博士锚定定义判定 C4/C5/C6 (输入须含 RPS50/RPS120/RPS250)。"""
    r250 = rps.get("RPS250")
    r120 = rps.get("RPS120")
    r50 = rps.get("RPS50")
    if None in (r250, r120, r50):
        return {"C4": None, "C5": None, "C6": None, "note": "RPS数据不全"}
    # C4 — RPS优先一切: RPS120≥90 或 RPS250≥90 (放宽至≥85的基本面优秀品种由人工把握)
    c4 = (r120 >= RPS_LINE) or (r250 >= RPS_LINE)
    # C5 — 一线红: RPS50/120/250 任一≥90
    c5 = (r50 >= RPS_LINE) or (r120 >= RPS_LINE) or (r250 >= RPS_LINE)
    # C6 — 三线红: RPS50&RPS120&RPS250 均≥90
    c6 = (r50 >= RPS_LINE) and (r120 >= RPS_LINE) and (r250 >= RPS_LINE)
    return {"C4": c4, "C5": c5, "C6": c6}


# ---------------------------------------------------------------------------
# 双RPS: 个股 -> 所属板块 (880xxx) 自动映射 + 共振判定
# ---------------------------------------------------------------------------
def build_block_map():
    """解析 infoharbor_block.dat (文本格式), 建立 个股->880xxx板块 映射。
    块头: #GN_中文名,短码,880xxx,创建日,更新日,,  成员: X#YYYYYY(逗号分隔)
    #FG_ 为风格板块头, 同样作为板块边界处理 (2026-08-20 修复: 此前只识别 #GN_, 导致
    MLCC概念(880588, 最后一个GN块)之后的所有 #FG_ 风格板块成员被错误并入MLCC, 成分暴增到全市场)
    """
    global _BLOCK_MAP, _BOARD_NAMES, _BOARD_IS_GN
    if _BLOCK_MAP is not None:
        return _BLOCK_MAP, _BOARD_NAMES
    stock_boards = {}
    board_names = {}
    board_is_gn = {}
    cur = None
    cur_is_gn = False
    with open(INFOHARBOR, "r", encoding="gbk", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("#GN_") or line.startswith("#FG_"):
                fields = line[4:].split(",")
                name = fields[0] if fields else ""
                bcode = None
                for fld in fields[1:]:
                    if _BOARD_RE.match(fld):
                        bcode = fld
                        break
                cur = bcode  # 无论是否找到板块码, 都重置 cur (风格板块无码时置 None)
                cur_is_gn = line.startswith("#GN_")
                if bcode:
                    board_names[bcode] = name
                    board_is_gn[bcode] = cur_is_gn
                continue
            if cur is None:
                continue
            for tok in line.split(","):
                m = _MEM_RE.match(tok.strip())
                if m:
                    stock_boards.setdefault(m.group(2), set()).add(cur)
    _BLOCK_MAP = stock_boards
    _BOARD_NAMES = board_names
    _BOARD_IS_GN = board_is_gn
    return _BLOCK_MAP, _BOARD_NAMES


def get_stock_boards(code):
    """返回个股所属 880xxx 概念板块 [(code, name), ...] (按板块码排序)。
    仅返回概念板块(#GN_), 排除风格板块(#FG_, 如基金重仓/周期股/控制变更等)。"""
    sb, bn = build_block_map()
    is_gn = _BOARD_IS_GN or {}
    return [(b, bn.get(b, "?")) for b in sorted(sb.get(code, set())) if is_gn.get(b, True)]


def get_double_rps(code):
    """双RPS 共振判定: 个股RPS(C4-C6) + 所属板块RPS(880xxx)。

    返回结构:
      stock_rps / c4c5c6       个股RPS与C4-C6判定
      boards[]                 所属板块 {code,name,RPS5,RPS10,RPS20,resonance(板块RPS20≥90)}
      best_board              板块RPS20最高的板块
      stock_strong/block_strong/double_rps
      verdict                 双RPS共振·强 / 个股独立行情·板块逆风 / 板块强·个股弱 / 个股弱·板块弱
    """
    rps = get_stock_rps(code)
    ev = eval_c4c5c6(rps) if rps else {"C4": None, "C5": None, "C6": None}
    sb, bn = build_block_map()
    is_gn = _BOARD_IS_GN or {}
    boards = sorted(sb.get(code, set()))
    board_info = []
    best = None
    for b in boards:
        sr = get_sector_rps(b)
        r5 = sr.get("RPS5") if sr else None
        r10 = sr.get("RPS10") if sr else None
        r20 = sr.get("RPS20") if sr else None
        # 概念内涵: 仅 #GN_ 概念板块参与共振与 best_board; #FG_ 风格板块(周期股/基金重仓/控制变更等)不参与
        concept = is_gn.get(b, True)
        info = {"code": b, "name": bn.get(b, "?"),
                "RPS5": r5, "RPS10": r10, "RPS20": r20,
                "concept": concept,
                "resonance": (concept and r20 is not None and r20 >= RPS_LINE)}
        board_info.append(info)
        if concept and r20 is not None and (best is None or r20 > best["RPS20"]):
            best = info
    stock_strong = bool(ev.get("C4"))
    block_strong = any(b["resonance"] for b in board_info)
    if stock_strong and block_strong:
        verdict = "双RPS共振·强"
    elif stock_strong and not block_strong:
        verdict = "个股独立行情·板块逆风"
    elif (not stock_strong) and block_strong:
        verdict = "板块强·个股弱"
    else:
        verdict = "个股弱·板块弱"
    return {
        "code": code,
        "stock_rps": rps,
        "c4c5c6": ev,
        "boards": board_info,
        "best_board": best,
        "stock_strong": stock_strong,
        "block_strong": block_strong,
        "double_rps": stock_strong and block_strong,
        "verdict": verdict,
    }


def _fmt(code, rps, sector=False):
    tag = "板块RPS" if sector else "个股RPS"
    print(f"[{tag}] {code}")
    if not rps:
        print("  无数据 (代码不在索引 / 未刷新)")
        return
    if sector:
        print(f"  RPS5={rps.get('RPS5','-')}  RPS10={rps.get('RPS10','-')}  RPS20={rps.get('RPS20','-')}")
    else:
        print(f"  RPS250={rps.get('RPS250','-')}  RPS120={rps.get('RPS120','-')}  "
              f"RPS50={rps.get('RPS50','-')}  RPS20={rps.get('RPS20','-')}  RPS10={rps.get('RPS10','-')}")
        if all(k in rps for k in ("RPS50", "RPS120", "RPS250")):
            ev = eval_c4c5c6(rps)
            print(f"  C4(RPS120≥90或RPS250≥90): {'✅' if ev['C4'] else '❌'}  "
                  f"C5(一线红·任一≥90): {'✅' if ev['C5'] else '❌'}  "
                  f"C6(三线红·三者≥90): {'✅' if ev['C6'] else '❌'}")


def _fmt_double(d):
    print(f"[双RPS] {d['code']}  判定: {d['verdict']}")
    ev = d.get("c4c5c6") or {}
    print(f"  个股RPS={d['stock_rps']}")
    print(f"  C4(≥90二选一)={'✅' if ev.get('C4') else '❌'}  "
          f"C5(一线红)={'✅' if ev.get('C5') else '❌'}  "
          f"C6(三线红)={'✅' if ev.get('C6') else '❌'}")
    print(f"  个股强势={d['stock_strong']}  板块强势={d['block_strong']}  "
          f"双RPS共振={d['double_rps']}")
    print(f"  所属板块 {len(d['boards'])} 个:")
    for b in d["boards"]:
        flag = "🔥" if b["resonance"] else "  "
        print(f"    {flag} {b['code']} {b['name']}: RPS5={b['RPS5']} RPS10={b['RPS10']} RPS20={b['RPS20']}")
    if d["best_board"]:
        bb = d["best_board"]
        print(f"  最佳板块(按RPS20)={bb['code']} {bb['name']} RPS20={bb['RPS20']}")


def main():
    ap = argparse.ArgumentParser(description="陶博士 RPS 真实取数 (通达信 extdata)")
    ap.add_argument("code", nargs="?", help="6位代码")
    ap.add_argument("--sector", help="板块代码 (880xxx/399xxx)")
    ap.add_argument("--double", metavar="CODE", help="双RPS共振判定 (个股代码)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.double:
        d = get_double_rps(args.double)
        if args.json:
            print(json.dumps(d, ensure_ascii=False, indent=2))
        else:
            _fmt_double(d)
        return

    if args.sector:
        rps = get_sector_rps(args.sector)
        if args.json:
            print(json.dumps({"code": args.sector, "rps": rps}, ensure_ascii=False))
        else:
            _fmt(args.sector, rps, sector=True)
        return
    if not args.code:
        ap.print_help()
        return
    rps = get_stock_rps(args.code)
    if args.json:
        ev = eval_c4c5c6(rps) if rps else None
        print(json.dumps({"code": args.code, "rps": rps, "eval": ev}, ensure_ascii=False))
    else:
        _fmt(args.code, rps)


if __name__ == "__main__":
    main()
