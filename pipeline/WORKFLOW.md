# 端到端操作手册

三 worktree 职责不变，本流水线串联它们并统一交付。

```bash
PY="C:/Users/gogoo/AppData/Local/Programs/Python/Python313/python.exe"
```

数据全部落在 `data/<品类>/`，跨阶段按**企业名**（去括号别名）对齐。

---

## ① 发现候选企业（information-channel）

参考 `.worktrees/information-channel/CHANNELS.md`。多渠道并行，每个 subagent 写
`data/<品类>/<channel>.json`。**渠道文件名固定**（aggregate.py 认这4个）：
`search_engine.json` `b2b_mic.json` `exhibition.json` `certification.json`

每条格式（candidate schema）：
```json
{"channel": "search_engine", "candidates": [
  {"name": "中文公司全称（含有限公司）", "website": "独立官网（非MIC子域）",
   "products": "写清产品形态", "source_url": "", "confidence": "high", "notes": ""}
]}
```
搜索词取 `sources/keywords.json` 的 cn/en 组合。英文公司名必须先解析中文全称入池
（④ 工商核验依赖中文名）。

---

## ② 清洗去重（aggregate.py）

```bash
BIG_BLACKLIST="凤铝|坚美|忠旺" $PY pipeline/scripts/aggregate.py "data/<品类>"
```
- 按官网域名去重，排除无官网+产品笼统的贸易商、黑名单大企业、境外企业
- 产物：`_clean.json`，每条带 `_channel`（搜索引擎/B2B外贸/展会/资质认证）

---

## ③ 官网内容验证（verify.py / website-content-verification）

```bash
# 转输入格式（name + website）
$PY -c "import json; c=json.load(open('data/<品类>/_clean.json',encoding='utf-8')); \
  json.dump([{'name':x['name'],'website':x.get('website','')} for x in c], \
  open('data/<品类>/_verify_in.json','w',encoding='utf-8'),ensure_ascii=False)"

$PY pipeline/scripts/verify.py --input data/<品类>/_verify_in.json \
    --config pipeline/sources/<品类>.yaml --out data/<品类> --xlsx
```
判定：产品（强/弱/无）、生产设备、是否制造商、语言（英文/多语/中文）。
产物：`data/<品类>/verify_result.json`，关键字段 `en_status` / `has_product`。
品类关键词见 `sources/<品类>.yaml`（铝管完整模板 `aluminum-tube.yaml`，换品类照抄改词）。
已知坑（抓取回退/SaaS站/JS空壳/EN入口实测）见 website-content-verification 的 README。

---

## ④ 工商核验（tyc_verify.py / business-registration-verification）

> 数据源：天眼查微信小程序接口 `api9.tianyancha.com`（2026-10 实测可用，
> 脚本内已配好请求头，`x-auth-token` 用 `***` 占位即可）。**3 秒间隔**，勿调快（会被限流返回空）。

```bash
# 名单必须命名为 <品类>.json —— 输出会是 <品类>_tyc.json，finalize 靠这个命名找
$PY -c "import json; c=json.load(open('data/<品类>/_clean.json',encoding='utf-8')); \
  json.dump([x['name'] for x in c],open('data/<品类>/<品类>.json','w',encoding='utf-8'),ensure_ascii=False)"

PYTHONPATH= $PY pipeline/scripts/tyc_verify.py data/<品类>/<品类>.json
```

> ⚠️ **文件名坑**：tyc_verify.py 输出 = 输入文件名去扩展名 + `_tyc`。输入叫 `铝管.json`
> → 输出 `铝管_tyc.json`，finalize 正好按 `data/<品类>/<品类>_tyc.json` 找。输入名不能乱起。

- 自动两级匹配：全名 → 去括号核心词重试。英文名/简称仍可能 total=0，需先转中文全称。
- 产物：`data/<品类>/<品类>_tyc.json`（字段 regCapital/regStatus/nature/established/matched_name）。
- 企业性质是组合规则推断（tagList+注册资本币种），复杂股权需人工复核。
- 109 家约 6 分钟（3s/家），长任务用 `terminal(background=True)`。

---

## ⑤ 汇总交付（finalize.py）

```bash
$PY pipeline/scripts/finalize.py "data/<品类>"
```

自动 join 三份产物（`_clean.json` + `verify_result.json` + `<品类>_tyc.json`），输出：
- `data/<品类>/制造商_验证结果.xlsx`（深蓝表头+冻结+筛选+颜色分组）
- `data/<品类>/制造商_报告.md`

**表格列**：序号 | 企业名称 | 主营产品 | 是否有英文官网 | 官网 |
存续状态 | 注册资金 | 企业性质 | 成立日期 | 信息渠道

英文官网映射：已验证英文版/多语官网 → 是；纯中文 → 否；平台店铺页 → 否（店铺页）；
无法访问/无官网 → 待核实。排序：有英文官网优先，其次注册资金降序。

**③④ 可独立缺失**：未跑的阶段对应列留空，不影响交付。

---

## 新增一个品类

1. `sources/keywords.json` 加品类 cn/en 搜索词
2. `sources/blacklist.json` 加要排除的大企业
3. 复制 `sources/aluminum-tube.yaml` → `sources/<品类>.yaml`，改产品/设备/贸易/负向关键词
4. `mkdir data/<品类>`，按 ①→⑤ 跑
