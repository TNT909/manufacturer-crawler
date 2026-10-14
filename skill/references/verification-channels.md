# 工商核验渠道全景（实测 2026-10）

回答"有哪些爬取注册资金/存续状态/企业性质的方案"或为核验环节选型时读本文件。
每个渠道的状态都可能随反爬升级变化，引用前对关键结论做一次快速实测
（探测方法见文末）。

## 渠道对比表

| 渠道 | 字段完整性 | 凭证门槛 | 实测状态 | 适用 |
|---|---|---|---|---|
| 企查查移动版 API `m.qcc.com` | 注册资本/成立/存续/企业类型 | 无 | 经 web_extract 可达，命中率约43% | **默认主力**（见 SKILL.md 阶段3） |
| 爱企查 CDP（用户已登录会话） | 同上 + 法代/电话/地址 | 用户浏览器登录 | 曾被反调试检测，理论备选 | 企查查抽不到时的补查 |
| 企查查网页会话（CDP + 已登录 tab） | 同移动API，字段渲染更全 | 企查查登录 cookie | 已登录会话下 `location.href` 导航可取到全部字段 | 深字段需求 |
| 天眼查网页 | 全字段 | 登录 | 主页可开，**未登录搜索被登录墙挡住**（空壳页无字段） | 仅登录后可用 |
| gsxt.gov.cn 官网 | 最权威全字段 | 无 | **死路**：真实浏览器打开即跳 "Environment Checking" 环境检测页 | 不要投入 |
| 企查查开放平台 `openapi.qcc.com` | 全字段 | 实名 + key，接口需逐个开通 | 主页可达，未实测调用 | 付费补量 |
| agent.qcc.com MCP（146 tool） | 全字段 + 风控/知产/舆情 | `QCC_API_KEY` Bearer token | 端点握手正常，无 token 返回 401 | 自动化升级路径（持 token 后实测） |
| `zhanglunet/qcc` 开源封装 | 同上 | 同上 token | 在线可读，文档声明支持 Hermes 接入（`_inventory.json` + `manifest.yaml`） | 同上的现成封装 |
| `@qcc-design/openapi-mcp-server`（npm v0.0.9） | 工商照面信息 | OpenAPI key/secret | 包存在，未实测 | 官方 MCP 备选 |
| 阿里云/腾讯云 API 市场（爱企查 item_get 等） | 全字段 | 购买后按次计费 | 可达 | 一次性大批量 |
| 启信宝开放平台 `data.qixin.com` / MCP `@qixin-api/apiservice-mcp` | 全字段，股权穿透 12 层（最纵深） | APP_KEY + SECRET_KEY | 文档可读，未实测调用；更新 T+2 | 预算敏感的股权穿透/关联排查（0.015 元/次起） |
| 鲸海数据 `kqdaas.com` | 注册资本/经营状态/信用代码/法代/股东等 50+ 类目 | 注册+实名送 1000 次（全平台通用），之后 0.05 元/次 | 官网可达、字段页实测含全部三字段；未实测调用 | **唯一零成本可试错的商业 API**（POC 后再放量） |
| 信用中国 `creditchina.gov.cn` | 行政处罚/失信；工商字段埋在信用报告 PDF 内 | 无 | 主页可开，**搜索页强制图形验证码**、返回内容极少 | 不要投入批量提取 |
| CnOpenData `cnopendata.com` | 注册金额/登记状态/信用代码/裁判文书等百余字段，3.5 亿+ | 付费联系销售（非爬虫、可商用） | 站点 JS 渲染，字段经摘要确认 | 完全合规的批量授权源 |
| 政府开放数据平台（温州 `data.wenzhou.gov.cn` 等） | 仅企业名+信用代码 | 免费 | 实测无注册资本/存续字段 | 弃 |
| 开源 `smthdagg/business-registry-query`（MIT） | 四源聚合，字段全 | 至少一个平台登录 cookie | 2026-09 活跃、63 pytest 全过 | 免费自建聚合层（见下） |

## 字段判定规则（各渠道通用）

- 注册资金：`注册资本`，注意认缴（多数）vs 实缴之别
- 是否续存：登记状态含 存续/在营/开业 → 存活；注销/吊销 → 已终止
- 企业性质：**工商登记里是"企业类型"字段，没有直接的国企/私企标签**——
  - 含"国有/国有独资/国有控股"或平台标签"央企" → 国企
  - 含"外商/外商投资/中外合资/港澳台" → 外企
  - 其余（法人为自然人）→ 私营（排除法判定）
- 复杂股权穿透（国资控股链）需企查查实控人/UBO 类接口，纯看企业类型不够

## 开源项目（GitHub 检索实测结论）

用 GitHub 官方 REST API 检索而非 web_search——`api.github.com/search/repositories?q=...&sort=stars`，
按 star / 最近提交日 / archived 客观筛选（脚本见 `scripts/github_repo_search.py`）：

- **`smthdagg/business-registry-query`** — MIT、2026-09 活跃、Python 3.12 + FastAPI、依赖仅
  fastapi/uvicorn/requests/openpyxl。天眼查/风鸟 Riskbird/爱企查/88查 四源并行聚合，按统一信用
  代码去重+字段互补、批量导出 XLSX/CSV/JSON、关系图谱、监控名单；63 个 pytest 全过、CI 含密钥扫描。
  **唯一活跃可用的开源项目**，但它只解决「聚合+工程」层，底层仍需至少一个平台的登录 cookie。
  自用定位，勿公开部署。
- **`ballcheung/china-company-check-mcp`** — README 宣称「免费 + 无鉴权 + 数据源自 GSXT/SAMR」，
  **实测 initialize 即 401 `No authorization provided`**，名不副实。
- `sinocheck/sinocheck-mcp` — 私有 beta，需邮件申请，无自助接入。
- 其余全部（gsxt/企查查/天眼查类，含 ★184/221/333 高星项目）均已归档或 2017-2022 停更，
  极验 4.0 后全灭。

## 无凭证 MCP 端点探测法（踩坑后）

宣称「免费/无鉴权」的 MCP 不可信，**README 的话必须用握手实测推翻或证实**：

1. POST 裸 JSON-RPC：`{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{...}}}`，
   请求头带 `Accept: application/json, text/event-stream`
2. 从响应头取 `Mcp-Session-Id`，后续每个调用都带上
3. 发 `notifications/initialized`（无 id），再 `tools/list`
4. 响应可能是 SSE 而非纯 JSON——按行取 `data:` 后的内容再 json.loads
5. 401 `invalid_token` / `No authorization provided` = 实际要鉴权，README 的「免费无鉴权」作废

现成脚本：`python scripts/probe_mcp.py <url> [--call <tool> --args '<json>']`

## 可达性探测方法（踩坑后）

- **terminal curl 在本主机不可信**：终端流量被代理拦截，全域名 curl 写入报错。
  改用 execute_code 内核的 urllib 请求（走 Keenable 出口）或 browser_exec。
- **反爬行为只有真实浏览器能观察到**：如 gsxt 的 "Environment Checking"
  环境检测页、企查查登录墙，curl/urllib 只能看到空壳页或异常状态码，
  判定渠道死活前必须用浏览器实测一遍关键路径。
- 静默批量实测惯例：先提取样本公司名单（xlsx 数据行从第 3 行起），
  逐方案跑样本，最后汇总成一张对比表交付；不要逐步确认。
