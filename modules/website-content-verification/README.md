# 官网内容验证器（website-content-verification）

对候选制造商的独立官网做**内容实测**：判定
1. 是否生产**指定产品**（产品关键词命中）；
2. 是否自备**生产设备**（设备关键词命中，区分「有产线 / 仅贸易或代工」）；
3. 是否具备**英文或其他外文版**官网（含 EN 子路径、语言切换按钮、语种分布）。

输出：JSON（机器可读）+ Markdown 表格（人读）+ 可选 Excel。

## 用法

```bash
python verify.py --input <待验证名单.json> --config <品类.yaml> --out <输出目录>
```

**输入 JSON**（数组，每条一家）：

```json
{
  "name": "江苏XX铝业有限公司",
  "website": "https://www.xx-alu.com/",
  "products": "渠道采集时记录的候选产品形态"
}
```

**config YAML**（每品类一份，见 `sources/keywords.yaml` 模板）：

```yaml
product_keywords:        # 产品命中（任一子列表≥1个命中即判"有产品"）
  - ["seamless", "aluminum tube", "aluminium pipe"]
  - ["无缝铝管", "精密铝管", "铝圆管"]
equipment_keywords:      # 生产设备命中（≥1个即判"自备产线"）
  - ["extrusion press", "挤压机", "extruder", "drawbench", "拉拔机"]
  - ["annealing furnace", "退火炉", "spark test", "涡流检测"]
trade_signals:           # 纯贸易/代理商特征（命中且无设备命中→降级）
  - ["trading company", "代理", "distributor of", "importer"]
product_forms:           # 可选：产品形态负向词（防止"型材"冒充"管材"）
  negative: ["extruded profile", "铝型材", "window profile", "门窗型材"]
```

## 判定规则

| 字段 | 取值 | 含义 |
|------|------|------|
| `has_product` | 强 / 弱 / 无 | 关键词命中数（含子标题、产品列表、meta 描述） |
| `has_equipment` | 强 / 弱 / 无 | 设备关键词命中（产线描述、设备参数表、车间展示） |
| `is_manufacturer` | 是 / 疑似 / 否 | 有设备=是；无设备但产品命中=疑似（可能代工）；命中贸易特征=否 |
| `language` | 英文 / 多语 / 中文 / 未知 | 见下 |
| `en_path` | `/en` 或语言切换链接 | 实际可访问的英文入口 |

**语言判定**（三信号叠加）：
1. URL 路径含 `/en` `/english` `/en-us` `/gb`；
2. HTML 含 `lang="en"` 或 `<link rel="alternate" hreflang="en">`；
3. 语言切换按钮文本（English/EN/英文）指向的 URL 实测返回 200 且为英文内容。

> 只用信号 1+2 会误判（很多中文站也有 en 路径但内容仍是中文），必须对 EN 入口做**内容实测**：抽 2000 字符统计中英文字符比例，英文字母 > 60% 才算英文站。

**其他外文**（法/德/西/俄/阿）：`hreflang` 或路径（`/fr` `/de` `/es` `/ru` `/ar`）+ 内容实测。

## 已知坑

1. **首页重定向**：很多站 `https://domain.com` 重定向到带语言的落地页，先跟 30 秒 10 跳内的 redirect 链再判定。
2. **SaaS 模板站**（cnal.com、1688.com 子页）：统一中文，无 EN 入口，直接标 `SaaS模板` 不重试。
3. **JS 渲染站**：curl 只能拿到空壳或 `noscript`。对 status 200 但 body < 500 字节的，走 browser_exec 取 `document.body.innerText`。
4. **英文在产品页而非首页**：EN 版常只在产品详情页。除首页外，再试 `/en` `/en/index.html` `/en/products` 三条常见路径。
5. **产品词误判**："铝管"可能出现在"我们用铝管做原料"（下游加工厂）。要求关键词命中在 `<title>` / `<h1>` / 产品列表块中才算**强**，只在正文段落中算**弱**。
6. **设备词误判**："引进德国设备""先进生产线"是营销话术。要求设备关键词与**具体型号/台数/吨位**共现（正则 `\d+\s*(台|条|吨|T|MN)`）才算强命中。

## 输出

- `<out>/verify_result.json` — 全字段机器可读
- `<out>/verify_result.md` — 分组表格（🟢强 / 🟡弱 / ⚪无）
- `<out>/verify_result.xlsx` — 可选，需 `--xlsx`，含 en_status / is_manufacturer / language 列
