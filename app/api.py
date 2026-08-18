# -*- coding: utf-8 -*-
"""数据源模块。

默认使用腾讯财经历史 K 线接口（web.ifzq.gtimg.cn），失败后自动切换新浪财经接口。
仅解析部分为纯函数，便于单元测试；网络请求依赖 requests（Android 上由 buildozer 打包）。
"""
import json
import re

try:
    import requests
except ImportError:  # 纯逻辑测试环境无 requests 也可导入本模块
    requests = None
else:
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:  # noqa: BLE001
        pass

from . import config

TIMEOUT = 12
UA = ("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36")

TENCENT_KLINE = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
SINA_KLINE = "https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_=/CN_MarketDataService.getKLineData"
TENCENT_QUOTE = "https://qt.gtimg.cn/q="


# --------------------------------------------------------------------------
# 代码规范化与版本自动选择
# --------------------------------------------------------------------------

def normalize_code(raw):
    """把用户输入规范成小写代码；6 位纯数字自动补市场前缀。

    例：'600519' -> 'sh600519'，'000001' -> 'sz000001'，'HSTECH' -> 'hstech'，
        'SH.000852' -> 'sh000852'，'hk00700' -> 'hk00700'，'usAAPL' -> 'usaappl'
    """
    code = (raw or "").strip().lower().replace(" ", "").replace(".", "")
    if not code:
        raise ValueError("请输入股票代码")
    if re.fullmatch(r"\d{6}", code):
        if code[0] == "6":
            return "sh" + code
        if code[0] in ("0", "1", "3"):
            return "sz" + code
        if code[0] in ("4", "8", "9"):
            return "bj" + code
        return "sh" + code
    return code


def detect_version(code):
    """按代码自动选择牛门线版本。

    - sh000xxx（上证系列指数）/ sz399xxx（深证系列指数）→ 指数版
    - A股个股（sh60x / sz0x / sz3x / bj）→ 标的版
    - 其他（港股、美股、期货、HSTECH 等英文代码）→ 基础主图版
    """
    code = normalize_code(code)
    m = re.fullmatch(r"(sh|sz)(\d{6})", code)
    if m:
        num = m.group(2)
        if (m.group(1) == "sh" and num.startswith("000")) or \
           (m.group(1) == "sz" and num.startswith("399")):
            return config.VERSION_INDEX
        return config.VERSION_STOCK
    if re.fullmatch(r"bj\d{6}", code):
        return config.VERSION_STOCK
    return config.VERSION_BASIC


# --------------------------------------------------------------------------
# 解析（纯函数）
# --------------------------------------------------------------------------

def _normalize_date(d):
    """将日期统一为 YYYY-MM-DD 字符串（兼容 '20240102' 等数字格式）。"""
    s = str(d).strip()
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", s)
    if m:
        return "%s-%s-%s" % (m.group(1), m.group(2), m.group(3))
    return s


def _rows_to_dicts(rows, o, c, h, l, v):
    """将腾讯 K 线行转成 dict 列表；row[6] 若存在且合理则视为当日成交额(元)。"""
    out = []
    for row in rows:
        try:
            date = _normalize_date(row[0])
            open_ = float(row[o])
            close_ = float(row[c])
            high_ = float(row[h])
            low_ = float(row[l])
            raw_v = row[v]
            volume = float(raw_v) if raw_v not in (None, "") else 0.0
        except (IndexError, TypeError, ValueError):
            continue
        amount = None
        if len(row) > 6:
            try:
                amt = float(row[6])
                # 合理性校验：成交额(元) 应明显大于 成交量(手)
                if amt > volume and amt > 0:
                    amount = amt
            except (TypeError, ValueError):
                amount = None
        out.append({
            "date": date,
            "open": open_,
            "high": high_,
            "low": low_,
            "close": close_,
            "volume": volume,
            "amount": amount,
        })
    return out


def _validate(rows):
    """OHLC 合理性校验：low <= min(o,c) 且 high >= max(o,c)。"""
    if not rows:
        return False
    ok = 0
    for r in rows:
        if r["low"] <= min(r["open"], r["close"]) + 1e-9 and \
           r["high"] >= max(r["open"], r["close"]) - 1e-9:
            ok += 1
    return ok >= max(1, len(rows) * 0.8)


def parse_tencent(text):
    """解析腾讯 fqkline 接口返回的 JSON 文本。

    行序有两种历史版本，解析后通过 OHLC 合理性校验自动识别：
      A) [日期, 开, 收, 高, 低, 量(, 额)]
      B) [日期, 开, 高, 低, 收, 量(, 额)]
    """
    data = json.loads(text)
    if data.get("code") not in (0, None) or not isinstance(data.get("data"), dict):
        raise ValueError("腾讯接口返回异常")
    payload = None
    for code_key, obj in data["data"].items():
        if not isinstance(obj, dict):
            continue
        for key in ("qfqday", "day"):
            rows = obj.get(key)
            if isinstance(rows, list) and rows:
                payload = {"code_key": code_key, "rows": rows, "qt": obj.get("qt", {})}
                break
        if payload:
            break
    if not payload:
        raise ValueError("腾讯接口未返回K线数据")

    dicts_a = _rows_to_dicts(payload["rows"], o=1, c=2, h=3, l=4, v=5)
    if _validate(dicts_a):
        rows = dicts_a
    else:
        dicts_b = _rows_to_dicts(payload["rows"], o=1, h=2, l=3, c=4, v=5)
        if _validate(dicts_b):
            rows = dicts_b
        else:
            raise ValueError("K线数据格式无法识别")

    return {
        "rows": rows,
        "name": _extract_tencent_qt_name(payload["qt"]),
        "code_key": payload["code_key"],
    }


def _extract_tencent_qt_name(qt):
    """从 qt 子对象中提取证券名称（字段1）。"""
    try:
        for val in qt.values():
            if isinstance(val, (list, tuple)) and len(val) > 2 and isinstance(val[1], str) and val[1]:
                return val[1]
    except Exception:
        pass
    return None


def parse_sina(text):
    """解析新浪 K 线 JSONP 文本（字段名明确：day/open/high/low/close/volume）。"""
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        raise ValueError("新浪接口返回异常")
    arr = json.loads(m.group(0))
    rows = []
    for item in arr:
        try:
            rows.append({
                "date": _normalize_date(item["day"]),
                "open": float(item["open"]),
                "high": float(item["high"]),
                "low": float(item["low"]),
                "close": float(item["close"]),
                "volume": float(item.get("volume") or 0.0),
                "amount": None,
            })
        except (KeyError, TypeError, ValueError):
            continue
    if not rows:
        raise ValueError("新浪接口未返回K线数据")
    return {"rows": rows, "name": None, "code_key": None}


# --------------------------------------------------------------------------
# 网络获取
# --------------------------------------------------------------------------

def _session():
    if requests is None:
        raise RuntimeError("缺少 requests 库，无法联网")
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA})
    return sess


def _get(sess, url, **kw):
    """带 SSL 兜底的 GET：个别机型证书库不全会导致校验失败，此时关闭校验重试。"""
    try:
        return sess.get(url, timeout=TIMEOUT, **kw)
    except requests.exceptions.SSLError:
        return sess.get(url, timeout=TIMEOUT, verify=False, **kw)


def _fetch_tencent(code):
    sess = _session()
    url = TENCENT_KLINE
    params = {"param": "%s,day,,,%d,qfq" % (code, config.KLINE_COUNT)}
    r = _get(sess, url, params=params)
    r.raise_for_status()
    parsed = parse_tencent(r.text)
    name = parsed["name"]
    if not name:
        name = _fetch_tencent_quote_name(code, sess)
    return parsed["rows"], name, "腾讯"


def _fetch_tencent_quote_name(code, sess):
    """通过 qt.gtimg.cn 实时行情获取证券名称（GBK 编码，字段1为名称）。"""
    try:
        r = _get(sess, TENCENT_QUOTE + code)
        r.encoding = "gbk"
        m = re.search(r'="([^"]*)"', r.text)
        if m:
            fields = m.group(1).split("~")
            if len(fields) > 1 and fields[1]:
                return fields[1]
    except Exception:
        pass
    return None


def _fetch_sina(code):
    sess = _session()
    params = {
        "symbol": code,
        "scale": "240",
        "ma": "no",
        "datalen": str(config.KLINE_COUNT),
    }
    r = _get(sess, SINA_KLINE, params=params)
    r.raise_for_status()
    parsed = parse_sina(r.text)
    return parsed["rows"], parsed["name"], "新浪"


def fetch_klines(code):
    """默认腾讯，失败自动切换新浪；两者均失败则抛出带原因的异常。"""
    code = normalize_code(code)
    errors = []
    rows = name = source = None
    try:
        rows, name, source = _fetch_tencent(code)
    except Exception as e:  # noqa: BLE001
        errors.append("腾讯：%s" % e)
    if not rows:
        try:
            rows, name, source = _fetch_sina(code)
        except Exception as e:  # noqa: BLE001
            errors.append("新浪：%s" % e)
    if not rows:
        raise RuntimeError(
            "获取 %s 数据失败（%s）。请检查代码是否正确"
            "（如 sh000852 / 600519 / HSTECH），或稍后重试。" % (code, "；".join(errors))
        )
    return {"code": code, "rows": rows, "name": name, "source": source}
