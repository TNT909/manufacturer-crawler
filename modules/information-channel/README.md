# 国内工业品制造商信息渠道

面向投标的国内工业品制造商候选池采集、清洗、工商核验、英文官网验证的标准化流水线。

## 目录结构

```
information-channel/
├── README.md                 # 本文件
├── CHANNELS.md               # 渠道源清单（搜索引擎/B2B/展会/资质/海关）与取舍理由
├── WORKFLOW.md               # 端到端操作手册（4阶段，含爱企查验证踩坑）
├── scripts/
│   ├── aggregate.py          # 清洗去重（域名去重+黑名单+形态过滤）→ _clean.json
│   └── finalize.py           # 汇总+美化Excel → 制造商_验证结果.xlsx
├── sources/
│   ├── blacklist.json        # 按品类的大型企业黑名单（排除国企/上市公司）
│   └── keywords.json         # 按品类的搜索关键词模板（中/英、平台限定词）
├── templates/
│   ├── candidate.schema.json # 单渠道产出 JSON 的字段规范（subagent 必须遵守）
│   └── report.md             # Markdown 交付报告模板
└── data/
    └── <品类>/               # 每个品类一个数据子目录，产物见 WORKFLOW.md
```

## 快速开始

```bash
# 1. 清洗去重（4渠道 JSON 已在 data/<品类>/ 下）
python scripts/aggregate.py "data/<品类>"       # 品类黑名单用 BIG_BLACKLIST 环境变量

# 2. 汇总美化（前置：data/<品类>/_final_small.json 与 _aiqicha_results.json 已生成）
python scripts/finalize.py "data/<品类>"
```

完整流程（含 4 渠道并行爬取、爱企查逐个核验、英文官网验证）见 `WORKFLOW.md`。
频道选取理由与各渠道实测取舍见 `CHANNELS.md`。

## 约定

- **工作根目录**在 `制造商爬虫/` 下；本渠道仓库只放可复用代码/模板/规则，数据落盘到 `data/<品类>/`。
- 品类编号沿用主仓库习惯：`01.<品类>` 起。
- 所有 subagent 产出必须符合 `templates/candidate.schema.json`。
