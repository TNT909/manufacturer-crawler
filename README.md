# 制造商挖掘（manufacturer-crawler）

面向投标的国内工业品制造商发现、清洗、官网验证、工商核验、汇总的一条龙工具集。

## 仓库结构

```
manufacturer-crawler/
├── pipeline/             # 日常跑批用（整合版流水线，一条命令跑全流程）
│   ├── README.md / WORKFLOW.md
│   ├── scripts/          #   aggregate / verify / tyc_verify / finalize
│   └── sources/          #   品类关键词 / 黑名单 / 官网验证 YAML
├── modules/              # 日常迭代改这里（三模块分模块源码）
│   ├── information-channel/        # 发现：多渠道采集候选 + 清洗去重
│   ├── website-content-verification/  # 官网内容实测：产品/设备/英文官网
│   └── business-registration-verification/  # 工商核验：天眼查存续/资金/性质
├── skill/                # 可移植 skill（供其他电脑/智能体使用）
│   ├── SKILL.md          #   给智能体读的工作流手册（含全部踩坑经验）
│   ├── scripts/          #   与 pipeline/scripts 同源的整合脚本
│   ├── references/       #   渠道全景、官网验证规则、工商核验渠道
│   └── templates/        #   品类关键词模板
├── data/                 # 各品类挖掘结果（_clean/verify_result/_tyc/候选名单）
└── .gitignore
```

## 三者关系

| 目录 | 用途 | 何时用 |
|---|---|---|
| `pipeline/` | 日常跑批，整合版脚本一条命令跑全流程 | 实际挖掘某个品类时 |
| `modules/` | 三模块分模块源码，改功能/加渠道时 | 迭代开发时 |
| `skill/` | 可移植 skill，SKILL.md + 同源脚本 | 其他电脑/其他智能体使用 |

`pipeline/scripts` 与 `skill/scripts` 保持同源（定期同步）；`modules/` 是分模块的演进源头，改完把整合版同步到 pipeline 和 skill。

## 依赖

- Python 3.13（`C:/Users/gogoo/AppData/Local/Programs/Python/Python313/python.exe`，hermes venv 无 PyYAML）
- 依赖包：`pyyaml`、`openpyxl`
- 工商核验（tyc_verify.py）走天眼查接口，无需登录，3 秒间隔

## 数据契约

阶段产物在 `data/<品类>/` 用固定文件名接力：
`<channel>.json` →（aggregate）`_clean.json` →（verify）`verify_result.json` →（tyc_verify）`<品类>_tyc.json` →（finalize）`<品类>产品制造商候选名单.xlsx/.md`

详细工作流与踩坑见 `skill/SKILL.md`。
