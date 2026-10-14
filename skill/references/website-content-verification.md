# 官网内容实测：产品/设备/语言判定规则

对候选制造商独立官网做内容实测，判定 (1) 是否生产指定产品 (2) 是否自备生产设备
(3) 是否有英文/外文官网。工具: `scripts/verify.py`，配置: `templates/keywords.yaml`。

## 输入输出

```bash
python scripts/verify.py --input <名单.json> --config templates/keywords.yaml \
    --out <输出目录> [--xlsx] [--limit N]
```

- 输入 JSON 数组: `[{"name","website","products"?}]`；website 留空 → en_status=无官网
- 输出: verify_result.json(全字段) / verify_result.md(🟢🟡⚪表) / verify_result.xlsx(浅绿=强, 浅黄=疑似)
- 用 Python313 解释器跑(hermes venv 无 PyYAML)

## 品类关键词配置(YAML)

```yaml
product_keywords:   # list-of-lists, 中英各一组; 任一子列表≥1命中即候选
  - ["aluminium tube", "aluminum pipe", ...]
  - ["无缝铝管", "精密铝管", ...]
equipment_keywords: # 同上, 生产设备词
  - ["extrusion press", "挤压机", "drawbench", "拉拔机", ...]
trade_signals:      # 纯贸易/代理特征
  - ["trading company", "代理", "distributor"]
product_forms:
  negative: ["铝型材", "aluminium profile", ...]  # 形态负向词
```

## 判定规则

| 字段 | 取值 | 规则 |
|------|------|------|
| has_product | 强/弱/无 | 强=关键词命中 title/h1/h2/产品卡片块; 弱=仅正文段落命中; negative单独命中→无, 与产品词同命中→强降弱 |
| has_equipment | 强/弱/无 | 强=设备词200字符窗口内共现规格数字 `\d+(台|条|套|吨|T|MN|mm)`; 弱=孤立出现; 营销话术(先进设备/自动化产线)不算 |
| is_manufacturer | 是/疑似/否 | 设备命中(强弱均可)→是; 无设备但产品命中→疑似(可能代工); 产品命中+贸易特征→否; 都无→否 |
| language | 英文/多语/中文/未知 | 见下 |

## 语言判定(四信号+内容实测)

1. **EN路径**: URL 含 `/en|/english|/en-us|/en-gb` → 对页面内容实测
2. **hreflang/lang属性**: `hreflang="en"`、`lang="en"` 等 → 只作线索
3. **语言切换链接**: 解析全部 `<a>` 的 label(english/en/英文)→href, 跟随实测
4. **盲试**: 根域+`/en/` `/en` `/en/index.html` `/en/products`

每个候选 EN 入口都要 `looks_english()` 内容实测:

- `latin_ratio > 0.6`(去标签文本英文字母占比) → 英文
- 混合站补充: 含CJK 且 英文词数(≥3字母) ≥200 且 命中英文内容词探针
  (product/about us/certificate/aluminum/extrusion/manufacturer/factory/equipment 等) → 英文
- 其他外文: hreflang/path(`/fr /de /es /ru /ar /pt`) → 多语

**只看 HTML 信号必误判**: SaaS 模板站(yybcdn/cnal.com等)注入
`var adviceLanguages='en'` 语言包, hreflang/lang 全中但无 EN 入口; 反向
`en.xxx.com` 也可能是中文站。信号只是入口候选, 内容实测才是结论。

## 抓取坑

- **SaaS/平台店铺页直接跳过**: host 含 cnal.com/1688.com/gys.cn/made-in-china.com
  → en_status=SaaS模板, 不重试
- **首页重定向**: urllib 自动跟随, 用 final_url 判定
- **JS 渲染空壳**: body<500 字节 → "疑似JS渲染", 标官网无法访问(需 browser_exec 兜底)
- **EN 入口常在产品页**: 除首页外盲试 4 条常见 EN 路径
- 抓取超时 10s/8s/6s 三档, 失败标"官网无法访问"不拖批

## 已知残留误判(待调优)

- `zeyialuminum.com`(yybcdn模板, 无独立EN站)、`hxalu.com`(有 cn.子域但主站即英文)
  等仍可能误判; 遇到新模板站先 dump 首页找语言切换链接再补规则
