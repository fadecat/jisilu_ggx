# 集思录筛选推送工具

从集思录网站抓取高股息股票和可转债数据，格式化后通过企业微信 Webhook 定时推送。可转债推送还会附带正股在互动易/上证e互动的最近一周董秘问答。

## 功能模块

| 模块 | 入口 | 说明 |
|------|------|------|
| 高股息筛选 | `main.py` | PE≤20, PB≤2, 股息率≥3%, ROE≥5% 等条件筛选 |
| 可转债筛选 | `cb_main.py` | 三低排序（双低 + 剩余规模，按得分制汇总），排除 `A-`、正股含 `ST`、已公告强赎/到期赎回，保留到期收益率展示 |
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
python test_cb_list_preview.py  # 可转债列表 → cb_list_preview.md
python test_cb_filter_debug.py  # 检查指定转债为何被过滤
python test_cb_ranking_verify.py  # 独立校验三低排序结果
python test_irm_preview.py    # 董秘互动查询验证
```

## 可转债三低排序说明

可转债当前不再使用 `价格 <= 115` 的筛选条件，而是对通过基础过滤的转债做“三低排序”：

- 双低（`dblow`）越低越好
- 规模（`curr_iss_amt`）越低越好
- 不再单独重复计算 `premium_rt`，因为双低本身已包含价格与转股溢价率
- 评级仅保留 `AAA ~ A`，排除 `A-`
- 排除正股名称含 `ST`

具体实现说明见 `cb_ranking.md`。

## CI/CD

GitHub Actions `.github/workflows/daily_report.yml`，工作日 15:30 CST 自动运行。

需要在仓库 Settings → Secrets 中配置上述四个环境变量。
