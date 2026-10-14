# 产品/设备/语言关键词配置（按品类各一份）

## 铝管（aluminum tube）

```yaml
product_keywords:
  - ["seamless aluminum tube", "aluminium tube", "aluminum pipe", "aluminium pipe",
     "precision tube", "capillary tube", "straight tube"]
  - ["无缝铝管", "精密铝管", "铝圆管", "毛细铝管", "薄壁铝管", "大口径铝管", "拉花铝管"]

equipment_keywords:
  - ["extrusion press", "extruder", "挤压机", "挤压生产线", "drawbench", "拉拔机",
     "tube drawing", "cold drawing mill", "冷轧管机", "pilger mill", "皮尔格轧机",
     "annealing furnace", "退火炉", "spark test", "涡流检测", "ultrasonic testing", "超声检测"]
  - ["CNC machining center", "数控车床", "lathe", "sawing machine", "锯床"]

trade_signals:
  - ["trading company", "import & export", "代理", "经销商", "distributor", "supplier of"]

product_forms:
  negative: ["extruded profile", "aluminium profile", "铝型材", "工业铝型材",
             "window profile", "门窗型材", "curtain wall", "幕墙型材"]
```

## 玻璃绝缘子（glass insulator）— 示例，可另存为 `玻璃绝缘子.yaml`

```yaml
product_keywords:
  - ["glass insulator", "disc insulator", "suspension insulator", "toughened glass",
     "cap and pin", "ball and socket"]
  - ["玻璃绝缘子", "钢化玻璃绝缘子", "盘形悬式", "玻璃伞盘"]

equipment_keywords:
  - ["annealing lehr", "退火炉", "tempering furnace", "钢化炉",
     "glass melting furnace", "玻璃熔窑", "glazing kiln", "上釉窑",
     "hydrothermal test", "热冲击试验", "radio interference voltage", "无线电干扰试验"]

trade_signals:
  - ["trading company", "agent for", "经销", "代理"]

product_forms:
  negative: ["composite insulator", "复合绝缘子", "porcelain insulator", "电瓷绝缘子"]
```

## 通用规则

- **中英各一组**，任一子列表 ≥1 命中即算 `has_product` 候选。
- **strong 判定**：关键词出现在 `<title>` / `<h1>` / `<h2>` / 产品卡片标题 / `product list` 区块 → 强；只在正文长段落出现 → 弱。
- **设备 strong 判定**：设备词 200 字符窗口内出现 `\d+\s*(台|条|套|吨|T|MN|mm)` → 强；孤立出现 → 弱。
- **negative 命中**：若 negative 命中而 product_keywords 未命中 → `has_product=无`；两者都命中 → 降一档（强→弱）。
- 关键词全部**小写匹配**（中文不区分大小写），匹配前对 HTML 做去标签、实体解码。
