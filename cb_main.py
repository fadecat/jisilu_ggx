import requests
import time

import os

from main import HEADERS, JISILU_COOKIE, MAX_MSG_LEN, send_wechat, send_alert
from irm_query import query_irm

CB_WECHAT_WEBHOOK = os.environ.get("CB_WECHAT_WEBHOOK", "")
IRM_WECHAT_WEBHOOK = os.environ.get("IRM_WECHAT_WEBHOOK", "")

CB_URL = "https://www.jisilu.cn/data/cbnew/cb_list_new/"

CB_FORM_DATA = {
    "fprice": "",
    "tprice": 115,
    "curr_iss_amt": "",
    "convert_amt_ratio": "",
    "premium_rt": "",
    # "ytm_rt": 0,
    "fyear_left": "",
    "tyear_left": "",
    "rating_cd[]": ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-"],
    "is_search": "Y",
    "market_cd[]": ["shmb", "shkc", "szmb", "szcy"],
    "show_blocked": "N",
    "min_price_only": "N",
    "btype": "",
    "listed": "Y",
    "qflag": "N",
    "sw_cd": "",
    "bond_ids": "",
    "rp": 50,
}


def fetch_cb_data():
    params = {"___jsl": f"LST___t={int(time.time() * 1000)}"}
    headers = {
        **HEADERS,
        "Cookie": JISILU_COOKIE,
        "Referer": "https://www.jisilu.cn/data/cbnew/",
    }
    resp = requests.post(CB_URL, params=params, data=CB_FORM_DATA, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def filter_cb(rows):
    """过滤可转债：排除已公告强赎(O)和到期赎回(R)，校验价格和到期收益率"""
    result = []
    for row in rows:
        c = row["cell"]
        icons = c.get("icons", {}) or {}
        # 排除已公告强赎和到期赎回
        if "O" in icons or "R" in icons:
            continue
        # 二次校验
        price = float(c.get("price", 999))
        ytm_rt = float(c.get("ytm_rt", -1) or -1)
        if price > 120 or ytm_rt < 0:
            continue
        result.append(row)
    # 按双低值升序排序
    result.sort(key=lambda r: float(r["cell"].get("dblow", 999) or 999))
    return result


def is_force_redeem_triggered(c):
    """判断是否触发强赎但未公告"""
    icons = c.get("icons", {}) or {}
    if "O" in icons:
        return False
    sprice = float(c.get("sprice", 0) or 0)
    force_redeem_price = float(c.get("force_redeem_price", 999) or 999)
    return sprice >= force_redeem_price and force_redeem_price > 0


MAX_SHOW = 50


def format_cb(idx, c):
    """格式化单只可转债"""
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
        f"  到期收益率:<font color=\"warning\">{c.get('ytm_rt', '--')}%</font>\n"
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
    "> 价格 ≤ 120元，到期收益率 ≥ 0%\n"
    "> 评级：AAA ~ A-\n"
    "> 已上市，排除停牌\n"
    "> 排除已公告强赎、到期赎回"
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
        entry = format_cb(i, row["cell"])
        if len(current) + len(entry) > MAX_MSG_LEN:
            messages.append(current.rstrip())
            current = f"**续({len(messages) + 1})**\n"
        current += entry

    if current.strip():
        messages.append(current.rstrip())

    return messages


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
