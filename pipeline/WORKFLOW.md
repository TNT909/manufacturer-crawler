# 端到端操作手册

三阶段流水线：**发现（本模块）→ 官网验证（website-content-verification）→ 工商核验（business-registration-verification）**。
本模块只做「发现 + 清洗」，核验归另外两个模块。

## 阶段 1：多渠道并行爬取候选池

用 delegate_task 并行 spawn subagent，渠道见 `CHANNELS.md`。核心渠道：

| 渠道 | 文件名 | 方法 |
|---|---|---|
| 搜索引擎 | `search_engine.json` | 中文品名+官网/厂家/有限公司；英文品名+manufacturer |
| B2B外贸 | `b2b_mic.json` | 中国制造网/环球资源英文关键词，优先有出口业绩 |
| 展会 | `exhibition.json` | Bing 搜「XX展 展商名录」提取企业名，回引擎找官网 |
| 资质认证 | `certification.json` | API 5L/ISO/压力管道许可/中标榜单 |
| 微信生态 | `wechat.json` | 搜狗微信 `weixin.sogou.com/weixin?type=2`，行业公众号「中标汇总榜/专精特新」一次成批提取 |

每个 subagent 写 JSON 到 `data/<品类>/<channel>.json`：

```json
{
  "channel": "",
  "candidates": [
    {
      "name": "中文公司全称（爱企查验证依赖它）",
      "website": "独立官网（非MIC子域）",
      "address": "",
      "products": "写清产品形态（铝管 vs 型材）",
      "source_url": "",
      "has_english_site": false,
      "confidence": "",
      "notes": "英文名/渠道备注放这里"
    }
  ]
}
```

必守规则见 `CHANNELS.md`「通用采集要求」。

### ⚠️ 采集可靠性（必做，踩坑沉淀）

subagent 可能**整机失败却自报完成**（症状：完成报告写「无前序数据/目录不可访问」，而另几个同目录 subagent 却写盘成功）。

- **以落盘文件为准，不信自报的 candidates_count**：每渠道回来后先 `ls data/<品类>/` + 读 JSON 核对实际条数。
- **失败渠道立即重派**，goal 里明确写「立即开始工作，不要等待任何前序数据——这是独立任务」。
- **中途调配额用 steer 不必停掉重派**：`delegate_task(action='steer', subagent_id, message)` 把新目标注入运行中的 subagent（如下一工具结果处生效），如「每渠道30家」。
- **渠道陆续到齐时每批重跑全链**：aggregate 域名去重跨渠道生效，verify/tyc 全量重跑会干净覆盖旧结果（按企业名 join 不受影响）。新渠道到达后顺序：aggregate(全量)→verify(全量)→tyc(全量)→finalize。

### 发现期采集要求（每个 subagent 必含指令）

- **英文公司名必须先解析中文全称再入池**（工商核验依赖中文名），英文名放 notes。
- **website 必须是独立官网**：MIC/阿里子域不算；找不到留空并在 notes 标「待核实」。
- 排除境外企业（关键词 Indonesia/印尼/PT./境外）。
- **confidence 如实自标**：设备厂/贸易商/疑似非目标品类标 low 并在 notes 写明理由；不要为凑数量把无关企业标 high。
- 英文站/产品形态**不在发现期验证**，分别归官网验证模块和清洗阶段。

搜索词取 `sources/keywords.json` 的 cn/en 组合。

## 阶段 2：清洗去重

```bash
BIG_BLACKLIST="凤铝|坚美|忠旺" python scripts/aggregate.py "data/<品类>"
```

- 按官网域名去重（最可靠），同域名保留信息最全的
- **域名去重后必须再做企业名归一化二级去重**：同一企业常有多个域名/别名，域名去重合并不掉，交付表会出现重复占行。aggregate.py 已内置（去括号别名+去公司后缀，同键保留信息最全）
- 排除：黑名单大型国企/上市公司、无官网+产品笼统的贸易商、境外企业
- **黑名单还要含「卖设备不卖产品」的设备厂**（如制管机械厂会被 B2B 渠道误采）
- 产品形态过滤（用户指定特定形态时）：按 products 字段过滤
- 产物：`_clean.json`

## 阶段 3：工商核验 → 用 business-registration-verification 模块

```bash
PYTHONPATH= python tyc_verify.py data/<品类>/<品类>.json
```

天眼查接口，实测命中率 82-95%，无登录/无浏览器门槛。输出 `<品类>_tyc.json`（含注册资本/存续/性质/成立日期/**businessScope 经营范围**——供官网验证模块交叉判定）。详见该模块 WORKFLOW.md。

> 输入名单须命名为 `<品类>.json`（输出会是 `<品类>_tyc.json`，finalize 靠此命名找）。

## 阶段 4：官网验证 → 用 website-content-verification 模块

```bash
python verify.py --input _verify_in.json --config sources/<品类>.yaml --out data/<品类> --xlsx
```

三重实测（产品/设备/语言）+ 多页面深挖 + 经营范围交叉判定 + 多语种检测。详见该模块 WORKFLOW.md。

## 阶段 5：汇总交付

finalize join 三份数据（_clean + verify_result + _tyc）→ `<品类>产品制造商候选名单.xlsx/.md`（官网列超链接，英文官网优先排序）。
