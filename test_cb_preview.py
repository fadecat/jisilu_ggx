"""测试脚本: 获取可转债数据并输出 markdown 预览到 cb_preview.md"""
from cb_main import fetch_cb_data, build_cb_messages

data = fetch_cb_data()
messages = build_cb_messages(data)

with open("cb_preview.md", "w", encoding="utf-8") as f:
    for i, msg in enumerate(messages, 1):
        f.write(f"---\n\n### 第 {i} 条消息 ({len(msg)} 字符)\n\n")
        f.write(msg + "\n\n")

print(f"已生成 cb_preview.md, 共 {len(messages)} 条消息")
