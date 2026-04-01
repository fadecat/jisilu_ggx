"""测试脚本: 获取可转债数据并输出 markdown 预览到 cb_preview.md"""
from cb_main import build_cb_messages, export_cb_rows_to_csv, fetch_cb_data

data = fetch_cb_data()
messages = build_cb_messages(data)
csv_path = export_cb_rows_to_csv(data)

with open("cb_preview.md", "w", encoding="utf-8") as f:
    for i, msg in enumerate(messages, 1):
        f.write(f"---\n\n### 第 {i} 条消息 ({len(msg)} 字符)\n\n")
        f.write(msg + "\n\n")

print(f"已生成 cb_preview.md, 共 {len(messages)} 条消息")
print(f"已生成 {csv_path}, 共导出 {len(data.get('rows', []))} 条记录")
