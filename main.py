import requests
import json
import os
import time

JISILU_URL = "https://www.jisilu.cn/data/stock/dividend_rate_list/"
DEFAULT_COOKIE = (
    "kbz_newcookie=1; "
    "kbzw__user_login=7Obd08_P1ebax9aX7tHY1urf3NrC38PV6JakptzY1enY5unX1r6bxtqspaCwnqmbqcLb2aSqw9aYrNqtzNyi2JnamLCwrN6Cq47p4tnH1peolqmZqq-omZydosjX0pSqo66Ur5mpsKStgquOybrTxqS55tzfzePYoq2PoIGc0N7X3dvu1Zavy5ekqI-gnJTQ3tevoLKC7peroJO50eDN2dDay8TV65GrlK6lpq6BmKy8zcK1pYzjy-HGl77Y28zfipS83dvo2dyRp5WspaOmkZ6RlMzWz9re4JGrlK6lpq6BtcXbqKadrpqnkKaPpw..; "
    "kbzw__Session=vda9dk34mvagfkq1vt897k3680; "
    "Hm_lvt_164fe01b1433a19b507595a43bf58262=1772981225,1773325708,1773414431,1773476221; "
    "HMACCOUNT=F1E3013DB5F2B093; "
    "Hm_lpvt_164fe01b1433a19b507595a43bf58262=1773476823"
)
JISILU_COOKIE = os.environ.get("JISILU_COOKIE", "") or DEFAULT_COOKIE
WECHAT_WEBHOOK = os.environ.get("WECHAT_WEBHOOK", "")

FORM_DATA = {
    "market[]": ["sh", "sz"],
    "industry": "",
    "province": "",
    "pe": 20,
    "pb": 2,
    "dividend_rate": 3,
    "roe": 5,
    "pe_temperature": 25,
    "pb_temperature": 25,
    "aft_dividend": 1,
    "roe_average": 5,
    "revenue_average": 0,
    "profit_average": 0,
    "eps_growth_ttm": "",
    "cashflow_average": 0,
    "int_debt_rate": "",
    "total_value_a": "",
    "total_value_b": "",
    "float_value_a": "",
    "float_value_b": "",
    "rp": 500,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.jisilu.cn/data/stock/dividend_rate/",
    "Origin": "https://www.jisilu.cn",
}


def fetch_data():
    params = {"___jsl": f"LST___t={int(time.time() * 1000)}"}
    headers = {**HEADERS, "Cookie": JISILU_COOKIE}
    resp = requests.post(JISILU_URL, params=params, data=FORM_DATA, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


MAX_MSG_LEN = 2048
MAX_SHOW = 50


def format_stock(idx, c):
    """格式化单只股票信息"""
    return (
        f"**{idx}. {c['stock_nm']}**({c['stock_id']}) {c['industry_nm']}\n"
        f"> 价格:<font color=\"comment\">{c['price']}</font>"
        f"  股息率:<font color=\"warning\">{c['dividend_rate']}%</font>"
        f"  PE:{c['pe']}  PB:{c['pb']}  ROE:{c['roe']}\n"
    )


def build_messages(data):
    """构建消息列表, 每条不超过 MAX_MSG_LEN"""
    rows = data.get("rows", [])
    total = len(rows)
    if not rows:
        return ["暂无符合条件的股票数据"]

    show_rows = rows[:MAX_SHOW]
    header = f"**集思录高股息筛选** (共 {total} 只)\n"
    if total > MAX_SHOW:
        header += f"以下展示股息率前 {MAX_SHOW} 名\n"
    messages = []
    current = header

    for i, row in enumerate(show_rows, 1):
        entry = format_stock(i, row["cell"])
        if len(current) + len(entry) > MAX_MSG_LEN:
            messages.append(current.rstrip())
            current = f"**续({len(messages) + 1})**\n"
        current += entry

    if current.strip():
        messages.append(current.rstrip())

    return messages


def send_wechat(messages):
    for i, content in enumerate(messages, 1):
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": content},
        }
        resp = requests.post(WECHAT_WEBHOOK, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if result.get("errcode") != 0:
            raise RuntimeError(f"企业微信推送失败: {result}")
        print(f"第 {i}/{len(messages)} 条推送成功 ({len(content)} 字符)")
        if i < len(messages):
            time.sleep(1)


def main():
    if not WECHAT_WEBHOOK:
        raise ValueError("缺少 WECHAT_WEBHOOK 环境变量")

    data = fetch_data()
    messages = build_messages(data)
    for msg in messages:
        print(msg)
        print("---")
    send_wechat(messages)


if __name__ == "__main__":
    main()
