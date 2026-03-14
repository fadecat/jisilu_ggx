# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

集思录高股息股票筛选工具。从集思录网站抓取符合条件的高股息股票数据，格式化为 Markdown 消息，通过企业微信 Webhook 定时推送。

## Architecture

单文件 Python 项目 (`main.py`)，流程：`fetch_data()` → `build_messages()` → `send_wechat()`

- `fetch_data()`: POST 请求集思录 API，需要登录 Cookie 认证
- `build_messages()`: 将股票数据格式化为企业微信 Markdown 消息，自动分片（单条不超过 2048 字符，最多展示前 50 只）
- `send_wechat()`: 逐条推送到企业微信群机器人
- `test_preview.py`: 本地测试脚本，抓取数据并输出到 `preview.md` 预览

## Commands

```bash
# 安装依赖
pip install requests

# 本地预览（不推送，生成 preview.md）
python test_preview.py

# 正式运行（需要环境变量）
JISILU_COOKIE="..." WECHAT_WEBHOOK="..." python main.py
```

## Environment Variables

- `JISILU_COOKIE`: 集思录登录 Cookie（不设置则使用代码中的默认值，可能过期）
- `WECHAT_WEBHOOK`: 企业微信群机器人 Webhook URL（必需）

## CI/CD

GitHub Actions 工作流 `.github/workflows/daily_report.yml`：工作日 15:30 CST 自动运行，Secrets 中配置 `JISILU_COOKIE` 和 `WECHAT_WEBHOOK`。支持 `workflow_dispatch` 手动触发。

## Filtering Criteria (FORM_DATA)

PE ≤ 20, PB ≤ 2, 股息率 ≥ 3%, ROE ≥ 5%, PE/PB温度 ≤ 25, 连续分红 ≥ 1年, 平均ROE ≥ 5%
