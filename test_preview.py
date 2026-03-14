"""测试脚本: 获取数据并输出 markdown 预览到 preview.md"""
from main import fetch_data, build_messages

data = fetch_data()
messages = build_messages(data)

with open("preview.md", "w", encoding="utf-8") as f:
    for i, msg in enumerate(messages, 1):
        f.write(f"---\n\n### 第 {i} 条消息 ({len(msg)} 字符)\n\n")
        f.write(msg + "\n\n")

print(f"已生成 preview.md, 共 {len(messages)} 条消息")
