# 制造商信息流水线（三 worktree 整合版）

输入一个商品品类 → 输出可筛选的制造商名单表格（xlsx + md）。

整合自三个 worktree，各自职责不变，本流水线只做**串联 + 统一交付**：

| worktree | 职责 | 脚本 |
|---|---|---|
| information-channel | 发现候选企业 + 清洗去重 | `aggregate.py` |
| website-content-verification | 官网内容实测（产品/设备/英文官网） | `verify.py` |
| business-registration-verification | 工商信息核验（存续/资金/性质） | `tyc_verify.py` |
| （本仓库新增） | 汇总三段产物成交付表格 | `finalize.py` |

```
input: 品类
  │  ① 发现   information-channel   agent多渠道爬取 → <channel>.json
  │  ② 清洗   aggregate.py          → _clean.json
  ▼  ③ 官网验证 website-content-verification  verify.py → verify_result.json
  │  ④ 工商核验 business-registration-verification  tyc_verify.py → <品类>_tyc.json
  ▼  ⑤ 汇总   finalize.py           → 制造商_验证结果.xlsx / 制造商_报告.md
```

## 目录

```
pipeline/
├── README.md                 # 本文件
├── WORKFLOW.md               # 端到端操作手册
├── scripts/
│   ├── aggregate.py          # ② 清洗去重（来自 information-channel）
│   ├── verify.py             # ③ 官网内容验证（来自 website-content-verification）
│   ├── tyc_verify.py         # ④ 工商核验（来自 business-registration-verification）
│   └── finalize.py           # ⑤ 汇总交付（本仓库新增）
└── sources/
    ├── keywords.json         # 品类搜索关键词（来自 information-channel）
    ├── blacklist.json        # 品类大企业黑名单
    └── aluminum-tube.yaml    # 铝管官网验证关键词（来自 website-content-verification）
data/
└── <品类>/                   # 每品类一个数据目录，各阶段产物落此
```

## 快速开始（以铝管为例）

```bash
PY="C:/Users/gogoo/AppData/Local/Programs/Python/Python313/python.exe"

# ① 发现：agent 按 CHANNELS.md 多渠道爬，产出 4 个 <channel>.json 到 data/铝管/
# ② 清洗
BIG_BLACKLIST="凤铝|坚美|忠旺" $PY pipeline/scripts/aggregate.py "data/铝管"
# ③ 官网内容验证
$PY -c "import json; c=json.load(open('data/铝管/_clean.json',encoding='utf-8')); \
  json.dump([{'name':x['name'],'website':x.get('website','')} for x in c], \
  open('data/铝管/_verify_in.json','w',encoding='utf-8'),ensure_ascii=False)"
$PY pipeline/scripts/verify.py --input data/铝管/_verify_in.json \
    --config pipeline/sources/aluminum-tube.yaml --out data/铝管 --xlsx
# ④ 工商核验（3秒间隔，109家约6分钟）
$PY -c "import json; c=json.load(open('data/铝管/_clean.json',encoding='utf-8')); \
  json.dump([x['name'] for x in c],open('data/铝管/铝管.json','w',encoding='utf-8'),ensure_ascii=False)"
PYTHONPATH= $PY pipeline/scripts/tyc_verify.py data/铝管/铝管.json
# ⑤ 汇总
$PY pipeline/scripts/finalize.py "data/铝管"
```

## 输出表格列

| 列 | 来源 |
|---|---|
| 序号 | finalize 生成 |
| 企业名称 | ① 采集 |
| 主营产品 | ① 采集 / ③ 官网验证兜底 |
| 是否有英文官网 | ③ 官网验证 |
| 官网 | ① 采集 |
| 存续状态 | ④ 工商核验 |
| 注册资金 | ④ 工商核验 |
| 企业性质 | ④ 工商核验 |
| 成立日期 | ④ 工商核验 |
| 信息渠道 | ① 采集 |

排序：有英文官网优先，其次注册资金降序。

## 各阶段独立性

- ③④ 可只跑一个：未跑的阶段对应列留空，不影响其他列。
- ④ 工商核验依赖天眼查接口（实测可用，`tyc_verify.py` 内已配好请求头）。
- 数据契约见 `WORKFLOW.md`。
