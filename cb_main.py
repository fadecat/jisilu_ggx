import csv
import json
import os
import time
from urllib.parse import urlencode

import requests

from main import HEADERS, JISILU_COOKIE, MAX_MSG_LEN, send_wechat, send_alert
from irm_query import query_irm

CB_WECHAT_WEBHOOK = os.environ.get("CB_WECHAT_WEBHOOK", "")
IRM_WECHAT_WEBHOOK = os.environ.get("IRM_WECHAT_WEBHOOK", "")

CB_URL = "https://www.jisilu.cn/data/cbnew/cb_list_new/"
CB_INDEX_QUOTE_URL = "https://www.jisilu.cn/webapi/cb/index_quote/"
CB_PAGE_SIZE = 1000
CB_MAX_PRICE = 115
CB_ALLOWED_RATINGS = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-"]
CB_ALLOWED_MARKETS = ["shmb", "shkc", "szmb", "szcy"]

CB_FORM_DATA = {
    "fprice": "",
    "tprice": CB_MAX_PRICE,
    "curr_iss_amt": "",
    "convert_amt_ratio": "",
    "premium_rt": "",
    "fyear_left": "",
    "tyear_left": "",
    "rating_cd[]": CB_ALLOWED_RATINGS,
    "is_search": "Y",
    "market_cd[]": CB_ALLOWED_MARKETS,
    "show_blocked": "N",
    "min_price_only": "N",
    "btype": "",
    "listed": "Y",
    "qflag": "N",
    "sw_cd": "",
    "bond_ids": "",
    "rp": CB_PAGE_SIZE,
}


def build_cb_request_urls(timestamp_ms=None, form_data=None):
    """构造实际请求 URL 和便于调试复制的完整 URL"""
    ts = timestamp_ms or int(time.time() * 1000)
    params = {"___jsl": f"LST___t={ts}"}
    post_url = requests.Request("POST", CB_URL, params=params).prepare().url
    payload = form_data or CB_FORM_DATA
    form_query = urlencode(payload, doseq=True)
    debug_url = post_url if not form_query else f"{post_url}&{form_query}"
    return params, post_url, debug_url


def fetch_cb_data(form_data=None):
    payload = form_data or CB_FORM_DATA
    params, post_url, debug_url = build_cb_request_urls(form_data=payload)
    print(f"CB POST URL: {post_url}")
    print(f"CB DEBUG URL: {debug_url}")
    headers = {
        **HEADERS,
        "Cookie": JISILU_COOKIE,
        "Referer": "https://www.jisilu.cn/data/cbnew/",
    }
    resp = requests.post(CB_URL, params=params, data=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    rows = data.get("rows", [])
    total = data.get("total")
    if isinstance(total, int) and len(rows) < total:
        raise RuntimeError(
            f"可转债接口返回疑似未取全：rows={len(rows)}, total={total}，三低排序可能失真"
        )

    return data


def fetch_cb_index_quote():
    headers = {
        **HEADERS,
        "Cookie": JISILU_COOKIE,
        "Referer": "https://www.jisilu.cn/data/cbnew/",
    }
    resp = requests.get(CB_INDEX_QUOTE_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != 200:
        raise RuntimeError(f"可转债概览接口返回异常: {payload}")
    return payload.get("data", {})


def get_cb_filter_reasons(c):
    """返回命中的过滤原因；为空表示通过"""
    reasons = []
    icons = c.get("icons", {}) or {}
    if "O" in icons:
        reasons.append("已公告强赎(O)")
    if "R" in icons:
        reasons.append("到期赎回(R)")
    # 正股名称里只要包含 ST（例如 ST / *ST / st），对应转债就从备选池中排除
    stock_nm = (c.get("stock_nm") or "").upper()
    if "ST" in stock_nm:
        reasons.append("正股含ST")

    return reasons


def filter_cb(rows):
    """过滤可转债：排除正股含ST、已公告强赎(O)和到期赎回(R)"""
    result = []
    for row in rows:
        c = row["cell"]
        if get_cb_filter_reasons(c):
            continue
        result.append(row)
    return sort_cb_rows(result)


def is_force_redeem_triggered(c):
    """判断是否触发强赎但未公告"""
    icons = c.get("icons", {}) or {}
    if "O" in icons:
        return False
    sprice = float(c.get("sprice", 0) or 0)
    force_redeem_price = float(c.get("force_redeem_price", 999) or 999)
    return sprice >= force_redeem_price and force_redeem_price > 0


MAX_SHOW = 50
THREE_LOW_FACTORS = [
    ("dblow", "双低"),
    ("curr_iss_amt", "规模"),
]


def to_float(value, default=float("inf")):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_numeric_value(row, field_name):
    value = row["cell"].get(field_name)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def assign_factor_scores(rows, field_name, label):
    ranked = []
    for index, row in enumerate(rows):
        value = get_numeric_value(row, field_name)
        if value is not None:
            ranked.append((index, row, value))

    ranked.sort(key=lambda item: (item[2], item[0]))
    total = len(ranked)
    rank_key = f"{field_name}_rank"
    score_key = f"{field_name}_score"
    for rank, (_, row, _) in enumerate(ranked, 1):
        row[rank_key] = rank
        row[score_key] = total - rank + 1
    for row in rows:
        row.setdefault(rank_key, None)
        row.setdefault(score_key, 0)
    return total


def sort_cb_rows(rows):
    """按双低/规模两项排名得分求和后降序排序"""
    ranked_rows = list(rows)
    for field_name, label in THREE_LOW_FACTORS:
        assign_factor_scores(ranked_rows, field_name, label)

    for row in ranked_rows:
        row["total_score"] = (
            row.get("dblow_score", 0) +
            row.get("curr_iss_amt_score", 0)
        )

    return sorted(
        ranked_rows,
        key=lambda row: (
            -row["total_score"],
            to_float(row["cell"].get("dblow")),
            to_float(row["cell"].get("premium_rt")),
            to_float(row["cell"].get("price")),
            to_float(row["cell"].get("curr_iss_amt")),
        ),
    )


def format_cb(idx, row):
    """格式化单只可转债"""
    c = row["cell"]
    sprice = c.get("sprice")
    sprice_text = "--" if sprice in (None, "") else str(sprice)
    if sprice not in (None, ""):
        try:
            if float(sprice) < 5:
                sprice_text = f"**<font color=\"warning\">{sprice}</font>**"
        except (TypeError, ValueError):
            pass

    line = (
        f"**{idx}. {c['bond_nm']}**({c['bond_id']})\n"
        f"> 价格:<font color=\"comment\">{c['price']}</font>"
        f"  双低:{c.get('dblow', '--')}"
        f"  溢价率:{c.get('premium_rt', '--')}%"
        f"  规模:{c.get('curr_iss_amt', '--')}"
        f"  到期收益率:<font color=\"warning\">{c.get('ytm_rt', '--')}%</font>\n"
        f"> 三低总分:<font color=\"info\">{row.get('total_score', '--')}</font>"
        f"  双低:排{row.get('dblow_rank', '--')}/{row.get('dblow_score', '--')}分"
        f"  规模:排{row.get('curr_iss_amt_rank', '--')}/{row.get('curr_iss_amt_score', '--')}分\n"
        f"> 评级:{c.get('rating_cd', '--')}"
        f"  剩余年限:{c.get('year_left', '--')}年"
        f"  正股:{c.get('stock_nm', '--')}"
        f"  正股价:{sprice_text}\n"
    )
    if is_force_redeem_triggered(c):
        line += f"> <font color=\"warning\">⚠已触发强赎（未公告）</font>\n"
    return line


CB_RULE_MSG = (
    "**📋 可转债筛选规则**\n"
    f"> 价格：≤ {CB_MAX_PRICE}\n"
    "> 评级：AAA ~ A-\n"
    "> 已上市，排除停牌\n"
    "> 排除正股含 ST\n"
    "> 排除已公告强赎、到期赎回\n"
    "> 排序：双低/规模排名得分相加，总分越高越靠前"
)


def build_cb_index_quote_message(index_data):
    """构建可转债市场概览消息"""
    if not index_data:
        return ""

    return (
        "**📈 可转债市场概览**\n"
        f"> 转债等权指数：{float(index_data.get('cur_index', 0)):.3f}"
        f" +{float(index_data.get('cur_increase_val', 0)):.3f}"
        f" +{float(index_data.get('cur_increase_rt', 0)):.3f}%\n"
        f"> 温度：{float(index_data.get('temperature', 0)):.2f}\n"
        f"> 成交额：{float(index_data.get('volume', 0)):.2f}亿元\n"
        f"> 价格中位数：{float(index_data.get('mid_price', 0)):.3f}\n"
        f"> 溢价率中位数：{float(index_data.get('mid_premium_rt', 0)):.2f}%\n"
        f"> 到期收益率：{float(index_data.get('avg_ytm_rt', 0)):.2f}%"
    )


def build_cb_messages(data, index_data=None):
    """构建可转债消息列表，每条不超过 MAX_MSG_LEN"""
    rows = filter_cb(data.get("rows", []))
    total = len(rows)
    messages = [CB_RULE_MSG]
    index_msg = build_cb_index_quote_message(index_data)
    if index_msg:
        messages.append(index_msg)
    if not rows:
        messages.append("暂无符合条件的可转债数据")
        return messages

    show_rows = rows[:MAX_SHOW]
    header = f"**集思录可转债筛选** (共 {total} 只)\n"
    if total > MAX_SHOW:
        header += f"以下展示前 {MAX_SHOW} 只\n"
    current = header

    for i, row in enumerate(show_rows, 1):
        entry = format_cb(i, row)
        if len(current) + len(entry) > MAX_MSG_LEN:
            messages.append(current.rstrip())
            current = f"**续({len(messages) + 1})**\n"
        current += entry

    if current.strip():
        messages.append(current.rstrip())

    return messages


def export_cb_rows_to_csv(data, path="cb_raw_rows.csv"):
    """导出接口返回的可转债原始字段到 CSV，便于查看全部列"""
    rows = data.get("rows", [])
    fieldnames = ["id"]
    for row in rows:
        for key in row.get("cell", {}).keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with open(path, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            cell = row.get("cell", {})
            record = {"id": row.get("id", "")}
            for key in fieldnames[1:]:
                value = cell.get(key, "")
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                record[key] = value
            writer.writerow(record)

    return path


def build_irm_messages(rows):
    """查询每只转债正股的董秘互动，构建推送消息"""
    # 去重：同一正股只查一次
    seen = set()
    stocks = []
    for row in rows:
        c = row["cell"]
        stock_id = c.get("stock_id", "")
        if stock_id and stock_id not in seen:
            seen.add(stock_id)
            stocks.append((c.get("stock_nm", ""), stock_id))

    all_parts = []
    for stock_nm, stock_id in stocks:
        qas = query_irm(stock_nm, stock_id)
        if not qas:
            continue
        part = f"**{stock_nm}**({stock_id})\n"
        for qa in qas[:3]:  # 每只最多3条
            q = qa["question"][:80] + ("..." if len(qa["question"]) > 80 else "")
            a = qa["answer"][:150] + ("..." if len(qa["answer"]) > 150 else "")
            part += f"> Q: {q}\n> A: {a}\n"
        all_parts.append(part)

    if not all_parts:
        return []

    header = "**📣 正股董秘互动（最近一周）**\n"
    messages = []
    current = header
    for part in all_parts:
        if len(current) + len(part) > MAX_MSG_LEN:
            if current.strip():
                messages.append(current.rstrip())
            current = "**📣 正股董秘互动（续）**\n"
        current += part
    if current.strip():
        messages.append(current.rstrip())
    return messages


def main():
    if not CB_WECHAT_WEBHOOK:
        raise ValueError("缺少 CB_WECHAT_WEBHOOK 环境变量")

    try:
        data = fetch_cb_data()
        index_data = fetch_cb_index_quote()
    except Exception as e:
        send_alert(f"⚠️ 可转债推送系统异常：数据获取失败，Cookie 可能已过期。\n错误信息：{e}", CB_WECHAT_WEBHOOK)
        return

    if not data.get("rows"):
        send_alert("⚠️ 可转债推送系统异常：获取到的数据为空，Cookie 可能已过期。", CB_WECHAT_WEBHOOK)
        return

    messages = build_cb_messages(data, index_data)
    for msg in messages:
        print(msg)
        print("---")
    send_wechat(messages, CB_WECHAT_WEBHOOK)

    # 查询正股董秘互动问答
    rows = filter_cb(data.get("rows", []))
    irm_messages = build_irm_messages(rows)
    if irm_messages:
        for msg in irm_messages:
            print(msg)
            print("---")
        send_wechat(irm_messages, IRM_WECHAT_WEBHOOK)


if __name__ == "__main__":
    main()
