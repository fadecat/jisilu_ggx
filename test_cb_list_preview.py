"""测试脚本: 使用与 cb_main 相同的请求和筛选条件，输出转债列表预览"""
from cb_main import fetch_cb_data, filter_cb, is_force_redeem_triggered


OUTPUT_FILE = "cb_list_preview.md"


def format_icons(cell):
    icons = cell.get("icons", {}) or {}
    if not icons:
        return "-"
    return ", ".join(sorted(icons.keys()))


def build_preview(rows, raw_total):
    lines = [
        "# 可转债列表预览",
        "",
        f"- 原始返回数量: {raw_total}",
        f"- 筛选后数量: {len(rows)}",
        "",
    ]

    if not rows:
        lines.append("暂无符合条件的可转债")
        return "\n".join(lines)

    for idx, row in enumerate(rows, 1):
        cell = row["cell"]
        lines.extend([
            f"## {idx}. {cell.get('bond_nm', '--')}({cell.get('bond_id', '--')})",
            "",
            f"- 价格: {cell.get('price', '--')}",
            f"- 溢价率: {cell.get('premium_rt', '--')}%",
            f"- 到期收益率: {cell.get('ytm_rt', '--')}%",
            f"- 双低: {cell.get('dblow', '--')}",
            f"- 评级: {cell.get('rating_cd', '--')}",
            f"- 剩余年限: {cell.get('year_left', '--')}年",
            f"- 正股: {cell.get('stock_nm', '--')}({cell.get('stock_id', '--')})",
            f"- 正股价: {cell.get('sprice', '--')}",
            f"- 强赎价: {cell.get('force_redeem_price', '--')}",
            f"- 已触发强赎未公告: {'是' if is_force_redeem_triggered(cell) else '否'}",
            f"- 图标: {format_icons(cell)}",
            "",
        ])

    return "\n".join(lines)


def main():
    data = fetch_cb_data()
    raw_rows = data.get("rows", [])
    rows = filter_cb(raw_rows)

    preview = build_preview(rows, len(raw_rows))
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(preview)

    print(f"已生成 {OUTPUT_FILE}")
    print(f"原始返回数量: {len(raw_rows)}")
    print(f"筛选后数量: {len(rows)}")

    if rows:
        print("转债预览:")
        for idx, row in enumerate(rows[:100], 1):
            cell = row["cell"]
            print(
                f"[{idx}] {cell.get('bond_nm', '--')}({cell.get('bond_id', '--')}) "
                f"价格:{cell.get('price', '--')} "
                f"溢价率:{cell.get('premium_rt', '--')}% "
                f"到期收益率:{cell.get('ytm_rt', '--')}% "
                f"双低:{cell.get('dblow', '--')}"
            )


if __name__ == "__main__":
    main()
