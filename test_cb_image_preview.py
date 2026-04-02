"""测试脚本：将可转债 markdown 消息渲染为 PNG 预览图。"""

from cb_image_preview import render_messages_to_image
from cb_main import build_cb_messages, fetch_cb_data, fetch_cb_index_quote


def main():
    data = fetch_cb_data()
    index_data = fetch_cb_index_quote()
    messages = build_cb_messages(data, index_data)
    output_path = render_messages_to_image(messages, "cb_preview.png")

    print(f"已生成图片预览: {output_path}")
    print(f"共渲染 {len(messages)} 条消息")


if __name__ == "__main__":
    main()
