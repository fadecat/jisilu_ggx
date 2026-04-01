"""测试脚本: 获取可转债数据并输出 markdown 预览到 cb_preview.md"""
from collections import Counter

from cb_main import (
    build_cb_messages,
    export_cb_rows_to_csv,
    fetch_cb_data,
    fetch_cb_index_quote,
    filter_cb,
    get_cb_filter_reasons,
)

data = fetch_cb_data()
index_data = fetch_cb_index_quote()
raw_rows = data.get("rows", [])
filtered_rows = filter_cb(raw_rows)
messages = build_cb_messages(data, index_data)
csv_path = export_cb_rows_to_csv(data)

with open("cb_preview.md", "w", encoding="utf-8") as f:
    for i, msg in enumerate(messages, 1):
        f.write(f"---\n\n### 第 {i} 条消息 ({len(msg)} 字符)\n\n")
        f.write(msg + "\n\n")

excluded = []
reason_counter = Counter()
for row in raw_rows:
    reasons = get_cb_filter_reasons(row["cell"])
    if not reasons:
        continue
    excluded.append((row["cell"], reasons))
    reason_counter.update(reasons)

print(f"接口原始返回: {len(raw_rows)} 只")
print(f"本地过滤后: {len(filtered_rows)} 只")
print(f"本地排除: {len(excluded)} 只")
if reason_counter:
    print("排除原因统计:")
    for reason, count in reason_counter.items():
        print(f"- {reason}: {count} 只")
if excluded:
    print("被排除明细:")
    for cell, reasons in excluded:
        print(
            f"- {cell.get('bond_nm', '--')}({cell.get('bond_id', '--')}) "
            f"正股:{cell.get('stock_nm', '--')} 原因:{', '.join(reasons)}"
        )

print(f"已生成 cb_preview.md, 共 {len(messages)} 条消息")
print(f"已生成 {csv_path}, 共导出 {len(raw_rows)} 条记录")
