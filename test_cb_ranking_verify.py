"""独立校验可转债三低排序结果是否正确。"""
from cb_main import fetch_cb_data, filter_cb, get_cb_filter_reasons


THREE_LOW_FIELDS = ("dblow", "curr_iss_amt")


def to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_filtered_rows(raw_rows):
    return [row for row in raw_rows if not get_cb_filter_reasons(row["cell"])]


def assign_scores(rows, field_name):
    ranked = []
    for index, row in enumerate(rows):
        value = to_float(row["cell"].get(field_name))
        if value is not None:
            ranked.append((index, row, value))

    ranked.sort(key=lambda item: (item[2], item[0]))
    total = len(ranked)
    result = {}
    for rank, (_, row, _) in enumerate(ranked, 1):
        result[row["cell"]["bond_id"]] = {
            "rank": rank,
            "score": total - rank + 1,
        }
    return result


def build_expected_result(rows):
    score_maps = {field_name: assign_scores(rows, field_name) for field_name in THREE_LOW_FIELDS}

    enriched = []
    for row in rows:
        bond_id = row["cell"]["bond_id"]
        dblow_detail = score_maps["dblow"].get(bond_id, {"rank": None, "score": 0})
        scale_detail = score_maps["curr_iss_amt"].get(bond_id, {"rank": None, "score": 0})
        total_score = dblow_detail["score"] + scale_detail["score"]
        enriched.append(
            {
                "row": row,
                "bond_id": bond_id,
                "dblow_rank": dblow_detail["rank"],
                "dblow_score": dblow_detail["score"],
                "curr_iss_amt_rank": scale_detail["rank"],
                "curr_iss_amt_score": scale_detail["score"],
                "total_score": total_score,
            }
        )

    enriched.sort(
        key=lambda item: (
            -item["total_score"],
            to_float(item["row"]["cell"].get("dblow"), float("inf")),
            to_float(item["row"]["cell"].get("price"), float("inf")),
            to_float(item["row"]["cell"].get("curr_iss_amt"), float("inf")),
        )
    )
    return enriched


def verify_rows(actual_rows, expected_rows):
    actual_ids = [row["cell"]["bond_id"] for row in actual_rows]
    expected_ids = [item["bond_id"] for item in expected_rows]

    if actual_ids != expected_ids:
        mismatch_index = next(
            index for index, (actual_id, expected_id) in enumerate(zip(actual_ids, expected_ids), 1)
            if actual_id != expected_id
        )
        raise AssertionError(
            f"排序顺序不一致，第 {mismatch_index} 位实际为 {actual_ids[mismatch_index - 1]}，"
            f"预期为 {expected_ids[mismatch_index - 1]}"
        )

    expected_by_id = {item["bond_id"]: item for item in expected_rows}
    for index, row in enumerate(actual_rows, 1):
        bond_id = row["cell"]["bond_id"]
        expected = expected_by_id[bond_id]
        for field in (
            "dblow_rank",
            "dblow_score",
            "curr_iss_amt_rank",
            "curr_iss_amt_score",
            "total_score",
        ):
            actual_value = row.get(field)
            expected_value = expected[field]
            if actual_value != expected_value:
                raise AssertionError(
                    f"{bond_id} 第 {index} 位字段 {field} 不一致：实际 {actual_value}，预期 {expected_value}"
                )


def print_top_preview(actual_rows, limit=20):
    print("")
    print(f"前三低预览（前 {min(limit, len(actual_rows))} 条）:")
    for index, row in enumerate(actual_rows[:limit], 1):
        cell = row["cell"]
        print(
            f"[{index}] {cell.get('bond_nm', '--')}({cell.get('bond_id', '--')}) "
            f"dblow={cell.get('dblow', '--')} "
            f"scale={cell.get('curr_iss_amt', '--')} "
            f"premium={cell.get('premium_rt', '--')} "
            f"scores={row.get('dblow_score', '--')}/"
            f"{row.get('curr_iss_amt_score', '--')} "
            f"total={row.get('total_score', '--')}"
        )


def main():
    data = fetch_cb_data()
    raw_rows = data.get("rows", [])
    actual_rows = filter_cb(raw_rows)
    filtered_rows = build_filtered_rows(raw_rows)
    expected_rows = build_expected_result(filtered_rows)

    print(f"接口原始数量: {len(raw_rows)}")
    print(f"过滤后数量: {len(filtered_rows)}")
    print(f"排序后数量: {len(actual_rows)}")

    verify_rows(actual_rows, expected_rows)

    print("校验通过：三低排序结果与独立验算一致。")
    print_top_preview(actual_rows)


if __name__ == "__main__":
    main()
