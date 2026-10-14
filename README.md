# 制造商挖掘（manufacturer-crawler）

面向投标的国内工业品制造商发现、清洗、官网验证、工商核验、汇总的一条龙工具集。

## 仓库结构

```
manufacturer-crawler/
├── skill/                  # 可移植 skill（SKILL.md + scripts + references + templates）
│   ├── SKILL.md            #   给智能体读的工作流手册（含全部踩坑经验）
│   ├── scripts/            #   整合版脚本：aggregate / verify / tyc_verify / finalize / qcc_verify
│   ├── references/         #   渠道全景、官网验证规则、工商核验渠道
│   └── templates/          #   品类关键词模板
├── modules/                # 三模块迭代版（日常开发改这里）
│   ├── information-channel/        # 发现：多渠道采集候选 + 清洗去重
│   ├── website-content-verification/  # 官网内容实测：产品/设备/英文官网
│   └── business-registration-verification/  # 工商核验：天眼查存续/资金/性质
├── data/                   # 各品类挖掘结果（_clean/verify_result/_tyc/候选名单）
└── .gitignore
```

## 两种使用方式

**方式A — 直接用整合脚本**（推荐，一条命令跑全流程）：
用 `skill/scripts/` 下的脚本，按 `skill/SKILL.md` 的阶段 1→5 跑。脚本与 `modules/` 三模块同源，已端到端验证。

**方式B — 改分模块**（迭代开发时）：
改 `modules/` 下对应模块的源码，改完把更新同步回 `skill/scripts/`。

## 依赖

- Python 3.13（`C:/Users/gogoo/AppData/Local/Programs/Python/Python313/python.exe`，hermes venv 无 PyYAML）
- 依赖包：`pyyaml`、`openpyxl`
- 工商核验（tyc_verify.py）走天眼查接口，无需登录，3 秒间隔

## 数据契约

阶段产物在 `data/<品类>/` 用固定文件名接力：
`<channel>.json` →（aggregate）`_clean.json` →（verify）`verify_result.json` →（tyc_verify）`<品类>_tyc.json` →（finalize）`<品类>产品制造商候选名单.xlsx/.md`

详细工作流与踩坑见 `skill/SKILL.md`。
