"""测试脚本: 验证董秘互动问答查询"""
from irm_query import query_irm

TEST_STOCKS = [
    ("蓝帆医疗", "002382"),  # 深交所
    ("洽洽食品", "002557"),  # 深交所
    ("贵州茅台", "600519"),  # 上交所
]

for name, code in TEST_STOCKS:
    print(f"\n{'='*50}")
    print(f"查询: {name}({code})")
    print(f"{'='*50}")
    qas = query_irm(name, code)
    if not qas:
        print("  无最近一周问答")
        continue
    for i, qa in enumerate(qas, 1):
        print(f"\n  [{i}] {qa['date']}")
        q = qa['question'][:80] + ("..." if len(qa['question']) > 80 else "")
        a = qa['answer'][:80] + ("..." if len(qa['answer']) > 80 else "")
        print(f"  Q: {q}")
        print(f"  A: {a}")

print(f"\n{'='*50}")
print("测试完成")
