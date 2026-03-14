# 集思录筛选推送工具

从集思录网站抓取高股息股票和可转债数据，格式化后通过企业微信 Webhook 定时推送。可转债推送还会附带正股在互动易/上证e互动的最近一周董秘问答。

## 功能模块

| 模块 | 入口 | 说明 |
|------|------|------|
| 高股息筛选 | `main.py` | PE≤20, PB≤2, 股息率≥3%, ROE≥5% 等条件筛选 |
| 可转债筛选 | `cb_main.py` | 价格≤120, 到期收益率≥0%, 排除强赎/到期赎回 |
| 董秘互动查询 | `irm_query.py` | 深交所互动易 + 上证e互动，自动按股票代码路由 |

## 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `JISILU_COOKIE` | 是 | 集思录登录 Cookie |
| `WECHAT_WEBHOOK` | 是 | 高股息推送的企业微信 Webhook |
| `CB_WECHAT_WEBHOOK` | 是 | 可转债推送的企业微信 Webhook |
| `IRM_WECHAT_WEBHOOK` | 是 | 董秘互动推送的企业微信 Webhook |

## 本地测试

```bash
pip install requests

python test_preview.py        # 高股息 → preview.md
python test_cb_preview.py     # 可转债 → cb_preview.md
python test_irm_preview.py    # 董秘互动查询验证
```

## CI/CD

GitHub Actions `.github/workflows/daily_report.yml`，工作日 15:30 CST 自动运行。

需要在仓库 Settings → Secrets 中配置上述四个环境变量。
