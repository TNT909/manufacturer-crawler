#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段5 汇总交付：把三段流水线的产物 join 成最终制造商名单表格。

输入（均在 data/<品类>/ 下，缺失则对应列留空）：
  - _clean.json          information-channel aggregate 产出（发现+清洗）
  - verify_result.json   website-content-verification verify.py 产出（官网内容验证）
  - <品类>_tyc.json       business-registration-verification tyc_verify.py 产出（工商核验）

输出：
  - 制造商_验证结果.xlsx   美化表格（深蓝表头+冻结+筛选+颜色分组）
  - 制造商_报告.md         Markdown 表格

表格列：序号 | 企业名称 | 主营产品 | 是否有英文官网 | 官网 |
        存续状态 | 注册资金 | 企业性质 | 成立日期 | 信息渠道

用法: python finalize.py "data/铝管"
依赖: openpyxl
"""
import json
import os
import re
import sys

COLUMNS = ["序号", "企业名称", "主营产品", "是否有英文官网", "官网",
           "存续状态", "注册资金", "企业性质", "成立日期", "信息渠道"]

# verify.py 的 en_status → 「是否有英文官网」
EN_MAP = {
    "已验证英文版": "是",
    "多语官网": "是",
    "纯中文官网": "否",
    "平台店铺页": "否（店铺页）",
    "官网无法访问": "待核实",
    "无官网": "否",
}

CH_NAME = {"search_engine": "搜索引擎", "b2b_mic": "B2B外贸",
           "exhibition": "展会", "certification": "资质认证"}


def load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def norm_name(s):
    """去括号别名，用于跨阶段按企业名对齐。"""
    return re.sub(r"[（(].*?[）)]", "", s or "").strip() or ""


def strip_site(url):
    return (url or "").replace("https://", "").replace("http://", "").strip("/")


def capital_number(cap):
    """'1000万人民币'/'5000万美元' → 数值（仅用于排序）。"""
    m = re.match(r"[\d,\.]+", str(cap or "").replace(",", ""))
    return float(m.group()) if m else 0.0


def finalize(pool_dir):
    category = os.path.basename(pool_dir.rstrip("/\\"))
    clean = load_json(os.path.join(pool_dir, "_clean.json")) or []
    verify = load_json(os.path.join(pool_dir, "verify_result.json")) or []
    tyc = load_json(os.path.join(pool_dir, f"{category}_tyc.json")) or []

    if not clean:
        print(f"未找到 {pool_dir}/_clean.json（先跑 aggregate.py）")
        sys.exit(1)

    # ---- join 官网验证（按企业名）----
    v_by = {}
    for v in verify:
        k = norm_name(v.get("name"))
        if k:
            v_by.setdefault(k, v)

    # ---- join 工商核验（按企业名；matched_name 优先，其次 input_name）----
    t_by = {}
    for t in tyc:
        for key in (t.get("matched_name"), t.get("input_name")):
            k = norm_name(key)
            if k and k not in t_by:
                t_by[k] = t
    rows = []
    n_tyc = 0
    for i, r in enumerate(clean, 1):
        name = r.get("name", "")
        v = v_by.get(norm_name(name)) or {}
        t = t_by.get(norm_name(name)) or {}
        if t.get("regCapital"):
            n_tyc += 1

        # 主营产品：优先采集时的 products，无则用官网验证的产品命中兜底
        prod = (r.get("products") or "").strip()
        if not prod:
            prod = {"强": "官网命中产品", "弱": "官网疑似产品",
                    "无": ""}.get(v.get("has_product"), "")

        channel = r.get("_channel") or ""
        rows.append({
            "序号": i,
            "企业名称": name,
            "主营产品": prod,
            "是否有英文官网": EN_MAP.get(v.get("en_status"), "待核实" if not v else "待核实"),
            "官网": strip_site(r.get("website")) or "—",
            "存续状态": t.get("regStatus", ""),
            "注册资金": t.get("regCapital", ""),
            "企业性质": t.get("nature", ""),
            "成立日期": t.get("established", ""),
            "信息渠道": CH_NAME.get(channel, channel),
        })

    # 排序：有英文官网优先，其次注册资金降序
    en_order = {"是": 0, "否（店铺页）": 1, "否": 2, "待核实": 3}
    rows.sort(key=lambda x: (en_order.get(x["是否有英文官网"], 3),
                             -capital_number(x["注册资金"])))
    for i, r in enumerate(rows, 1):
        r["序号"] = i

    n_en = sum(1 for r in rows if r["是否有英文官网"] == "是")
    stats = {"total": len(rows), "en": n_en, "tyc": n_tyc}

    xlsx = os.path.join(pool_dir, f"{category}产品制造商候选名单.xlsx")
    md = os.path.join(pool_dir, f"{category}产品制造商候选名单.md")
    write_xlsx(rows, xlsx)
    write_md(rows, md, stats)
    print(f"候选 {stats['total']} | 有英文官网 {stats['en']} | 工商核验命中 {stats['tyc']}")
    print(f"已保存 {xlsx}")
    print(f"已保存 {md}")
    return xlsx


def write_xlsx(rows, path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = "制造商"
    hf = PatternFill("solid", start_color="1F4E79")
    hfont = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
    bfont = Font(name="微软雅黑", size=10)
    en_f = PatternFill("solid", start_color="E2EFDA")
    mic_f = PatternFill("solid", start_color="FFF2CC")
    thin = Side(style="thin", color="D9D9D9")
    bd = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws.merge_cells(f"A1:{get_column_letter(len(COLUMNS))}1")
    ws["A1"] = "制造商候选名单"
    ws["A1"].font = Font(name="微软雅黑", size=14, bold=True, color="1F4E79")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 30
    for c, h in enumerate(COLUMNS, 1):
        cell = ws.cell(2, c, h)
        cell.fill = hf; cell.font = hfont; cell.border = bd
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[2].height = 28
    link_font = Font(name="微软雅黑", size=10, color="0563C1", underline="single")
    for i, r in enumerate(rows, 3):
        fill = (en_f if r["是否有英文官网"] == "是"
                else mic_f if r["是否有英文官网"] == "否（店铺页）" else None)
        for c, h in enumerate(COLUMNS, 1):
            cell = ws.cell(i, c, r[h])
            cell.font = bfont; cell.border = bd
            cell.alignment = Alignment(vertical="center", wrap_text=(h == "官网"))
            if fill:
                cell.fill = fill
            # 官网列做成可点击超级链接
            if h == "官网" and r[h] and r[h] != "—":
                url = r[h] if "://" in r[h] else "https://" + r[h]
                cell.hyperlink = url
                cell.font = link_font
    widths = {"序号": 6, "企业名称": 26, "主营产品": 18, "是否有英文官网": 13,
              "官网": 32, "存续状态": 9, "注册资金": 14, "企业性质": 11,
              "成立日期": 12, "信息渠道": 13}
    for c, h in enumerate(COLUMNS, 1):
        ws.column_dimensions[get_column_letter(c)].width = widths.get(h, 14)
    ws.freeze_panes = "A3"
    ws.auto_filter.ref = f"A2:{get_column_letter(len(COLUMNS))}{len(rows) + 2}"
    wb.save(path)


def write_md(rows, path, stats):
    lines = ["# 制造商验证结果", "",
             f"候选 {stats['total']} 家 · 有英文官网 {stats['en']} 家 · "
             f"工商核验命中 {stats['tyc']} 家", "",
             "| " + " | ".join(COLUMNS) + " |",
             "|" + "---|" * len(COLUMNS)]
    for r in rows:
        lines.append("| " + " | ".join(str(r[h]) for h in COLUMNS) + " |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    finalize(sys.argv[1] if len(sys.argv) > 1 else ".")
