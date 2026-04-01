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
    "rp": 50,
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
    return resp.json()


def get_cb_filter_reasons(c):
    """返回命中的过滤原因；为空表示通过"""
    reasons = []
    icons = c.get("icons", {}) or {}
    if "O" in icons:
        reasons.append("已公告强赎(O)")
    if "R" in icons:
        reasons.append("到期赎回(R)")

    try:
        price = float(c.get("price", 999) or 999)
    except (TypeError, ValueError):
        price = 999
    if price > CB_MAX_PRICE:
        reasons.append(f"价格>{CB_MAX_PRICE}")

    return reasons


def filter_cb(rows):
    """过滤可转债：排除已公告强赎(O)和到期赎回(R)，校验价格"""
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


def to_float(value, default=float("inf")):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def assign_rank_score(rows, field_name, value_getter):
    ranked = sorted(
        enumerate(rows),
        key=lambda item: (value_getter(item[1]), item[0]),
    )
    last_value = None
    last_rank = 0
    for position, (_, row) in enumerate(ranked, 1):
        current_value = value_getter(row)
        if current_value != last_value:
            last_value = current_value
            last_rank = position
        row[field_name] = last_rank


def sort_cb_rows(rows):
    """按价格/规模/溢价率三项名次分求和后升序排序"""
    ranked_rows = list(rows)
    assign_rank_score(ranked_rows, "price_rank_score", lambda row: to_float(row["cell"].get("price")))
    assign_rank_score(ranked_rows, "scale_rank_score", lambda row: to_float(row["cell"].get("curr_iss_amt")))
    assign_rank_score(ranked_rows, "premium_rank_score", lambda row: to_float(row["cell"].get("premium_rt")))

    for row in ranked_rows:
        row["total_rank_score"] = (
            row["price_rank_score"] +
            row["scale_rank_score"] +
            row["premium_rank_score"]
        )

    return sorted(
        ranked_rows,
        key=lambda row: (
            row["total_rank_score"],
            to_float(row["cell"].get("price")),
            to_float(row["cell"].get("curr_iss_amt")),
            to_float(row["cell"].get("premium_rt")),
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
        f"  溢价率:{c.get('premium_rt', '--')}%"
        f"  规模:{c.get('curr_iss_amt', '--')}"
        f"  到期收益率:<font color=\"warning\">{c.get('ytm_rt', '--')}%</font>\n"
        f"> 三低总分:<font color=\"info\">{row.get('total_rank_score', '--')}</font>"
        f"  价格名次:{row.get('price_rank_score', '--')}"
        f"  规模名次:{row.get('scale_rank_score', '--')}"
        f"  溢价名次:{row.get('premium_rank_score', '--')}\n"
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
    f"> 价格 ≤ {CB_MAX_PRICE}元\n"
    "> 评级：AAA ~ A-\n"
    "> 已上市，排除停牌\n"
    "> 排除已公告强赎、到期赎回\n"
    "> 排序：价格/规模/溢价率名次分相加，总分越低越靠前"
)


def build_cb_messages(data):
    """构建可转债消息列表，每条不超过 MAX_MSG_LEN"""
    rows = filter_cb(data.get("rows", []))
    total = len(rows)
    if not rows:
        return [CB_RULE_MSG, "暂无符合条件的可转债数据"]

    show_rows = rows[:MAX_SHOW]
    header = f"**集思录可转债筛选** (共 {total} 只)\n"
    if total > MAX_SHOW:
        header += f"以下展示前 {MAX_SHOW} 只\n"
    messages = [CB_RULE_MSG]
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
    except Exception as e:
        send_alert(f"⚠️ 可转债推送系统异常：数据获取失败，Cookie 可能已过期。\n错误信息：{e}", CB_WECHAT_WEBHOOK)
        return

    if not data.get("rows"):
        send_alert("⚠️ 可转债推送系统异常：获取到的数据为空，Cookie 可能已过期。", CB_WECHAT_WEBHOOK)
        return

    messages = build_cb_messages(data)
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
