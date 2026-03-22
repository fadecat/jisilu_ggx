"""测试脚本: 检查指定可转债为何被当前筛选规则排除"""
from cb_main import CB_ALLOWED_MARKETS, CB_ALLOWED_RATINGS, CB_FORM_DATA, fetch_cb_data, get_cb_filter_reasons


TARGET_BONDS = ["家悦转债", "蓝帆转债", "闻泰转债"]


def build_relaxed_form_data():
    data = dict(CB_FORM_DATA)
    data["tprice"] = ""
    data["rating_cd[]"] = []
    data["market_cd[]"] = CB_ALLOWED_MARKETS
    data["show_blocked"] = "N"
    data["listed"] = "Y"
    data["rp"] = 200
    return data


def main():
    print("当前正式筛选条件:")
    print(f"- 价格 <= {CB_FORM_DATA['tprice']}")
    print(f"- 评级: {', '.join(CB_ALLOWED_RATINGS)}")
    print("- 已上市")
    print("- 排除停牌")
    print("- 排除已公告强赎(O) / 到期赎回(R)")
    print("")

    data = fetch_cb_data(build_relaxed_form_data())
    rows = data.get("rows", [])
    found = set()

    for row in rows:
        cell = row["cell"]
        bond_nm = cell.get("bond_nm", "")
        if bond_nm not in TARGET_BONDS:
            continue

        found.add(bond_nm)
        reasons = get_cb_filter_reasons(cell)
        rating = cell.get("rating_cd", "--")
        if rating not in CB_ALLOWED_RATINGS:
            reasons.append(f"评级不在范围内({rating})")

        print(f"{bond_nm}({cell.get('bond_id', '--')})")
        print(f"  价格: {cell.get('price', '--')}")
        print(f"  溢价率: {cell.get('premium_rt', '--')}%")
        print(f"  到期收益率: {cell.get('ytm_rt', '--')}%")
        print(f"  评级: {rating}")
        print(f"  图标: {cell.get('icons', {}) or '-'}")
        print(f"  正股: {cell.get('stock_nm', '--')}({cell.get('stock_id', '--')})")
        if reasons:
            print(f"  排除原因: {'; '.join(reasons)}")
        else:
            print("  排除原因: 未命中当前 Python 过滤，若正式结果里没有，说明被服务端其他条件排除了")
        print("")

    missing = [bond for bond in TARGET_BONDS if bond not in found]
    if missing:
        print("以下转债在放宽价格/评级后的接口返回里也没找到:")
        for bond in missing:
            print(f"  - {bond}")
        print("这通常说明它们被接口侧其他条件排除了，或名称与当前接口返回不一致。")


if __name__ == "__main__":
    main()
