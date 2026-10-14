# 官网内容验证工作流（website-content-verification）

对候选制造商名单做**三重实测判定**：
1. **产品**：是否生产指定品类产品（如铝管）
2. **生产设备**：是否自备关键生产设备（如挤压机）——区分「有产线」vs「贸易/代工」
3. **语言**：是否具备英文或其他外文版官网

输入：企业名称+官网 URL 名单（Excel/JSON）
输出：机器可读 JSON + 人读 Markdown 表格 + 美化 Excel

---

## 目录结构

```
website-content-verification/
├── WORKFLOW.md                    # 本文件
├── README.md                      # 判定规则+已知坑速查
├── verify.py                      # 主程序（命令行）
├── sources/
│   ├── aluminum-tube.yaml         # 铝管品类关键词配置
│   └── keywords.example.md        # 双品类配置示例+通用规则
└── templates/
    ├── verify_input.schema.json   # 输入 JSON 格式规范
    └── verify_result.schema.json  # 输出 JSON 格式规范
```

---

## 端到端流程

### 阶段 1：准备输入名单

**输入格式**（JSON 数组，每条一家）：

```json
[
  {"name": "明达铝业科技（太仓）有限公司", "website": "https://www.mintatc.com/"},
  {"name": "山东汇丰铝业股份有限公司", "website": "https://en.aluhf.com"}
]
```

**从 Excel 提取**（如 `铝管制造商_TEST.xlsx`）：

```python
import openpyxl, json
wb = openpyxl.load_workbook('铝管制造商_TEST.xlsx')
ws = wb.active
headers = [c.value for c in ws[2]]
name_col = headers.index('企业名称') + 1
site_col = headers.index('官网') + 1
items = []
for r in range(3, ws.max_row + 1):
    n = ws.cell(r, name_col).value
    w = ws.cell(r, site_col).value
    if n and w:
        if not w.startswith(('http://', 'https://')):
            w = 'https://' + w
        items.append({'name': n.strip(), 'website': w.strip()})
json.dump(items, open('_input.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
```

### 阶段 2：选择品类配置

**已有配置**：`sources/aluminum-tube.yaml`（铝管：产品/设备/贸易特征/负向词）

**新品类**：复制 `sources/keywords.example.md` 中的模板，改关键词后存为 `sources/<品类>.yaml`。必填四组：

```yaml
product_keywords:   # 产品命中（中英各一组，任一子列表≥1命中即判"有产品"）
  - ["aluminum tube", "aluminium pipe"]
  - ["铝管", "铝合金管"]
equipment_keywords: # 生产设备命中（≥1个即判"自备产线"）
  - ["extruder", "extrusion press"]
  - ["挤压机", "挤压生产线"]
trade_signals:      # 纯贸易/代理商特征（命中+无设备→降级为"否"）
  - ["trading company", "代理", "经销商"]
product_forms:
  negative: ["铝型材", "aluminium profile"]  # 负向词：防止"型材"冒充"管材"
```

### 阶段 3：运行验证

```bash
python verify.py \
  --input _input.json \
  --config sources/aluminum-tube.yaml \
  --out verify_out \
  --xlsx
```

**参数**：
- `--input`：待验证名单 JSON（数组）
- `--config`：品类 YAML 配置
- `--out`：输出目录（默认 `verify_out`）
- `--xlsx`：同时输出美化 Excel
- `--limit N`：只跑前 N 条（调试用）

**运行环境**：
- Python 3.13（`C:/Users/gogoo/AppData/Local/Programs/Python/Python313/python.exe`）
- 依赖：`PyYAML`（`import yaml`）、`openpyxl`（仅 `--xlsx` 时需要）
- 67 家约需 2-3 分钟（含网络抓取+EN 入口实测）

### 阶段 4：解读输出

**输出文件**（`verify_out/` 下）：
- `verify_result.json` — 全字段机器可读（字段规范见 `templates/verify_result.schema.json`）
- `verify_result.md` — 🟢🟡⚪ 分组表格
- `verify_result.xlsx` — 美化表格（深蓝表头+微软雅黑+冻结+auto_filter+颜色分组）

**判定字段**：

| 字段 | 取值 | 含义 |
|------|------|------|
| `has_product` | 强/弱/无 | 产品词命中（强=在 title/h1/产品列表，弱=只在正文） |
| `has_equipment` | 强/弱/无 | 设备词命中（强=与规格数字共现，弱=孤立出现） |
| `is_manufacturer` | 是/疑似/否/待核实 | 有设备=是；无设备但有产品=疑似；命中贸易特征=否；平台页/无法访问=待核实 |
| `language` | 英文/多语/中文/未知 | 英文=EN 入口实测 latin>60% 或英文词≥200 |
| `en_path` | URL | 实际可访问的英文入口 |
| `en_status` | 已验证英文版/多语官网/纯中文官网/平台店铺页/官网无法访问/无官网 | 官网类型 |

**Excel 颜色标记**：
- 浅绿：制造商=是 且 英文官网
- 浅黄：制造商=疑似
- 无填充：纯中文官网/平台店铺页/无法访问

---

## 核心判定逻辑

### 产品判定

```python
hits = [kw for kw in keywords if kw.lower() in html_lower]
strong = [kw for kw in hits if kw in title/h1/product_list]
# 强：在 title/h1/产品卡片标题中命中
# 弱：只在正文长段落中出现
# 无：未命中
# 负向词（如"铝型材"）命中且产品词未命中 → 无；两者都命中 → 降一档
```

### 设备判定（关键：挤压机）

```python
EQUIP_SPEC = re.compile(r"\d+\s*(台|条|套|吨|T|MN|mm|inch|in)")
# 设备词 200 字符窗口内出现规格数字 → 强命中
# 例："8台挤压机"、"7500 tons extruder"、"600-12500吨挤压机19条"
# 孤立出现（如"引进先进设备"）→ 弱命中
```

**挤压机相关关键词**（铝管品类）：
- 中文：挤压机、挤压生产线、挤压设备、挤压车间、挤压工艺、挤压生产
- 英文：extruder、extrusion press、extrusion line、extrusion production line

### 语言判定（英文官网）

**三信号叠加**（优先级从高到低）：

1. **URL 路径**：`/en` `/english` `/en-us` `/en-gb` → 直接实测内容
2. **hreflang/lang 属性**：`hreflang="en"` `lang="en"` → 记录信号，继续找入口
3. **语言切换按钮**：`<a href="...">English</a>` → 取 href 实测内容
4. **常见 EN 路径盲试**：`/en/` `/en` `/en/index.html` `/en/products` → 逐个试探

**英文内容实测**（`looks_english` 函数）：
- `latin_ratio > 0.6`（英文字母占正文 60% 以上）→ 英文
- 中英混合：英文词数 ≥200 且含产品/公司词汇 → 英文（兜底 `en.aluhf.com` 这类主文中文但导航英文的站）

**其他外文**（法/德/西/俄/阿）：`hreflang` 或路径（`/fr` `/de` `/es` `/ru` `/ar`）+ 内容实测

---

## 已知坑与解决方案

### 1. 抓取失败（连接超时/403/404）

**现象**：67 家中有 20 家原本失败

**解决方案**：`fetch` 自动回退策略（已实现）
- `https://` → `http://`
- `www.` → 非 `www.`
- 逐个变体尝试直到成功

**恢复率**：19/20（仅 DNS 无法解析的失败）

### 2. SaaS 模板站（cnal.com、1688.com、gys.cn）

**现象**：这些域名是平台店铺页，无独立官网

**处理**：保留店铺 URL，`en_status = "平台店铺页"`，`is_manufacturer = "待核实"`
- 不跳过、不标"无官网"
- Excel 输出"官网类型"列标注"平台店铺页"

### 3. JS 渲染站（空壳）

**现象**：curl 只能拿到 `<div id="app"></div>` 这种空壳

**处理**：`content_len < 500` → 标"疑似JS渲染(空壳)"，`en_status = "官网无法访问"`
- 需 browser_exec 兜底（打开 Chrome CDP 端口取 `document.body.innerText`）

### 4. 英文在产品页而非首页

**现象**：EN 版常只在 `/en/products` 而非首页

**处理**：除首页外，盲试 `/en/` `/en` `/en/index.html` `/en/products` 四条路径

### 5. 产品词误判（下游加工厂）

**现象**："铝管"出现在"我们用铝管做原料"（下游加工厂，不是生产商）

**处理**：要求关键词命中在 `<title>` / `<h1>` / 产品列表块中才算**强**，只在正文段落中算**弱**

### 6. 设备词误判（营销话术）

**现象**："引进德国设备""先进生产线"是营销话术，无具体规格

**处理**：要求设备关键词与**具体型号/台数/吨位**共现（正则 `\d+\s*(台|条|吨|T|MN)`）才算强命中

### 7. 混合中英文站（en.aluhf.com）

**现象**：主文中文，但导航/产品名英文，`latin_ratio < 0.6` 被漏判为中文

**处理**：`looks_english` 增加英文词数探针（≥200 个英文词+含产品/公司词汇）→ 判英文

---

## 实测数据（67家铝管制造商）

**抓取成功率**：54/67（80.6%）
- 独立官网：53 家
- 平台店铺页：11 家（cnal.com/1688.com/gys.cn，地址保留）
- 无法访问：3 家（DNS 失败/连接超时/JS 渲染）

**判定结果**：
- **制造商=是**：23 家（有设备强/弱命中）
- **制造商=疑似**：5 家（有产品但无设备，需人工确认是否代工）
- **制造商=待核实**：13 家（平台店铺页/无法访问）
- **制造商=否**：26 家（无产品/无设备，或命中贸易特征）

**设备强命中**（挤压机相关）：13 家
- 明达铝业（10台进口铝挤压生产线）
- 山东汇丰（extruder 7500/3600/2800 tons）
- 佛山兴涛美（8台挤压机+2台熔铸炉）
- 安徽盛达前亮（9 extrusion production lines）
- 山东橙易（600-12500吨挤压机19条）
- 宁波环球（630T/1250T/1350T/1800T/3600T 挤压机）
- 林西铝业（12500吨卧式挤压机/8000吨挤压机）
- 其他 6 家...

**英文官网**：19 家
- `/en/` 子路径：明达、国强和茂、兴涛美、金铝轻合金、联昌铝业
- `en.` 子域名：澳美格、哈尔滨光智
- 英文首页（无需切换）：苏州捷优、安徽盛达前亮、山东橙易、聊城万合、CHAL、林西、Gengfei
- 其他形式：`?l=2` 语言参数、`/ENGLISH/` 大写路径、`/English/Index.aspx`、`/en/index.asp`

---

## 与其他 worktree 的衔接

**上游**：`information-channel/`（候选池采集+清洗+工商验证）
- 输入：`information-channel/data/<品类>/_clean.json` 或 `_verify_queue.json`
- 输出：候选企业名称+官网 URL

**下游**：本 worktree 验证结果可直接用于：
- 投标资格审查（制造商=是 且 英文官网 → 优先联系）
- 供应商库建设（Excel 全字段可读）
- 竞品分析（设备规格/产能数据提取）

---

## 快速开始（铝管品类）

```bash
# 1. 从 Excel 提取输入名单
python -c "
import openpyxl, json
wb = openpyxl.load_workbook('铝管制造商_TEST.xlsx')
ws = wb.active
headers = [c.value for c in ws[2]]
name_col = headers.index('企业名称') + 1
site_col = headers.index('官网') + 1
items = []
for r in range(3, ws.max_row + 1):
    n = ws.cell(r, name_col).value
    w = ws.cell(r, site_col).value
    if n and w:
        if not w.startswith(('http://', 'https://')):
            w = 'https://' + w
        items.append({'name': n.strip(), 'website': w.strip()})
json.dump(items, open('_input.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
"

# 2. 运行验证
python verify.py --input _input.json --config sources/aluminum-tube.yaml --out verify_out --xlsx

# 3. 查看结果
# verify_out/verify_result.xlsx（Excel）
# verify_out/verify_result.md（Markdown 表格）
# verify_out/verify_result.json（机器可读）
```
