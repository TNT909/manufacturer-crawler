# -*- coding: utf-8 -*-
"""企业工商信息核验工作流 — 统一入口
=====================================
输入: 一个 .xlsx（A 列=企业名称，从第 2 行起）或 .json（[{"name": ...}]）
输出: 同名 _tyc.json（原始结果）+ _tyc.xlsx（美化交付表）

数据源: 天眼查微信小程序逆向接口 api9.tianyancha.com
       (方案源自 bouxin/company-crawler，2026-10-10 实测可用)

用法:
  python tyc_verify.py 名单.xlsx
  python tyc_verify.py companies.json
"""
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ---------------- 配置 ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

# 天眼查小程序请求头（bouxin/company-crawler 原值；当前接口不校验 token，仍照传）
AUTHORIZATION = "0###oo34J0VKzLlpdvf8kgFkMlfU_IPY###1642087379312###22494f3155c2e5a4be76e503837fa439"
X_AUTH_TOKEN = "***"
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36",
    "version": "TYC-XCX-WX",
    "Authorization": AUTHORIZATION,
    "x-auth-token": X_AUTH_TOKEN,
    "Accept": "application/json",
}
SEARCH_API = "https://api9.tianyancha.com/services/v3/search/sNorV3/{q}"
DETAIL_API = "https://api9.tianyancha.com/services/v3/t/common/baseinfoV5/{eid}"

INTERVAL = 3.0          # 礼貌间隔(秒)；<1s 会被限流返回空 companyList
RETRY = 3

# ---------------- 工具函数 ----------------
def http_get(url):
    for attempt in range(RETRY):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=REQUEST_HEADERS),
                                       timeout=15, context=CTX)
            return r.status, r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "ignore")[:400]
        except Exception as e:
            if attempt == RETRY - 1:
                return None, f"{type(e).__name__}: {str(e)[:120]}"
            time.sleep(2)


def strip_em(s):
    return (s or "").replace("<em>", "").replace("</em>", "").strip()


def parse_established(ts):
    """天眼查 estiblishTime 是毫秒时间戳字符串"""
    try:
        return time.strftime("%Y-%m-%d", time.localtime(int(ts) / 1000))
    except Exception:
        return (ts or "")[:10] if ts else ""


def capital_to_number(cap):
    """注册资本字符串 -> (数值, 币种)"""
    if not cap:
        return 0.0, ""
    cur = "人民币"
    if "美元" in cap: cur = "美元"
    elif "港元" in cap: cur = "港元"
    elif "欧元" in cap: cur = "欧元"
    num = re.match(r"[\d,\.]+", cap.replace(",", ""))
    return (float(num.group()) if num else 0.0), cur


def judge_nature(comp):
    """组合规则判定 国有/外资/私营（非权威，重大决策需人工复核）"""
    tags = " ".join(str(t) for t in (comp.get("tagList") or [])
                    + (comp.get("tagListV2") or []) + (comp.get("tagListV3") or []))
    text = tags + " " + str(comp.get("orgTypeName") or "") + " " + str(comp.get("companyShowBizTypeName") or "")
    cap = str(comp.get("regCapital") or "")
    nature = []
    if any(k in text for k in ["国有", "央企", "国企"]):
        nature.append("国有")
    if any(k in text for k in ["外商", "外资", "中外合资", "港澳台"]):
        nature.append("外资")
    if any(c in cap for c in ["美元", "港元", "欧元"]) and "外资" not in nature:
        nature.append("外资(外币注册资本)")
    if not nature:
        nature.append("私营")
    return "/".join(nature)


def core_name(name):
    """去括号别名，取核心词，用于未匹配时重试"""
    return re.sub(r"[（(].*?[）)]", "", name or "").strip()


def lookup(name):
    """搜索并返回结构化结果；未命中返回 matched=False。疑似限流(200但空列表)自动退避重试。"""
    rec = {"input_name": name}
    for attempt in range(2):
        q = urllib.parse.quote(name)
        st, body = http_get(SEARCH_API.format(q=q))
        rec["http"] = st
        try:
            j = json.loads(body)
            data = j.get("data") or {}
            comps = data.get("companyList") or []
            rec["total"] = data.get("companyCount")
            if not comps:
                # total=None 或 0；total=None 多为限流，退避后重试一次
                if data.get("companyCount") is None and attempt == 0:
                    time.sleep(5)
                    continue
                rec["matched"] = False
                return rec
            comp = comps[0]
            cap, cur = capital_to_number(comp.get("regCapital"))
            rec.update({
                "matched": True,
                "matched_name": strip_em(comp.get("name")),
                "regCapital": comp.get("regCapital"),
                "capital_number": cap,
                "capital_currency": cur,
                "regStatus": comp.get("regStatus"),
                "nature": judge_nature(comp),
                "creditCode": comp.get("creditCode") or comp.get("regNumber"),
                "legalPerson": comp.get("legalPersonName"),
                "established": parse_established(comp.get("estiblishTime")) or (comp.get("estiblishTime") or "")[:10],
                "base": comp.get("base"),
                "orgType": comp.get("orgTypeName"),
                "address": comp.get("regLocation"),
                "phone": (comp.get("phone") or "").split("\t")[0].strip() if comp.get("phone") else "",
                "historyNames": comp.get("historyNames"),
                "eid": comp.get("id"),
            })
            return rec
        except Exception as e:
            rec["matched"] = False
            rec["error"] = str(e)[:150]
            return rec
    return rec


def lookup_with_retry(name):
    """先全名，未命中则去括号核心词重试"""
    r = lookup(name)
    if not r.get("matched"):
        core = core_name(name)
        if core and core != name:
            r2 = lookup(core)
            r2["input_name"] = name
            r2["retried_as"] = core
            return r2
    return r

# ---------------- 读取输入 ----------------
def load_names(path):
    if path.lower().endswith(".json"):
        data = json.load(open(path, encoding="utf-8"))
        return [d["name"] if isinstance(d, dict) else d for d in data]
    # xlsx: A 列，第 2 行起
    import openpyxl
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    names = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[0] and str(row[0]).strip():
            names.append(str(row[0]).strip())
    return names

# ---------------- 主流程 ----------------
def main():
    if len(sys.argv) < 2:
        print("用法: python tyc_verify.py <名单.xlsx|名单.json>")
        sys.exit(1)
    src = sys.argv[1]
    names = load_names(src)
    print(f"读取 {len(names)} 家企业，开始核验...\n")

    results = []
    for i, name in enumerate(names):
        r = lookup_with_retry(name)
        results.append(r)
        flag = "✓" if r.get("matched") else "✗"
        cap = r.get("regCapital", "-")
        status = r.get("regStatus", "-")
        nature = r.get("nature", "-")
        print(f"[{i+1}/{len(names)}] {flag} {name[:26]:26s} | {cap:14s} | {status:4s} | {nature}")
        time.sleep(INTERVAL)

    # 输出 JSON
    stem = os.path.splitext(src)[0]
    out_json = f"{stem}_tyc.json"
    json.dump(results, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # 输出 Excel
    out_xlsx = f"{stem}_tyc.xlsx"
    write_excel(results, out_xlsx)

    hit = sum(1 for r in results if r.get("matched"))
    print(f"\n完成: 命中 {hit}/{len(results)} ({hit*100//len(results)}%)")
    print(f"JSON:  {out_json}")
    print(f"Excel: {out_xlsx}")


def write_excel(results, path):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "核验结果"

    headers = ["企业名称", "匹配名称", "注册资金", "存续状态", "企业性质",
               "统一信用代码", "法定代表人", "成立日期", "省份", "地址", "电话"]
    ws.append(["企业工商信息核验结果（数据源: 天眼查 · 2026-10）"])
    ws.append(headers)

    header_fill = PatternFill("solid", fgColor="1F4E79")
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for c in ws[2]:
        c.font = Font(name="微软雅黑", bold=True, color="FFFFFF", size=10)
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = border

    for r in results:
        ws.append([
            r.get("input_name"), r.get("matched_name") or "未匹配",
            r.get("regCapital") or "-", r.get("regStatus") or "-", r.get("nature") or "-",
            r.get("creditCode") or "-", r.get("legalPerson") or "-",
            r.get("established") or "-", r.get("base") or "-",
            r.get("address") or "-", r.get("phone") or "-",
        ])

    # 存续状态着色
    status_color = {"存续": "C6EFCE", "在业": "D9EAD3", "注销": "FFC7CE", "吊销": "FF9999"}
    for row in ws.iter_rows(min_row=3, max_row=ws.max_row):
        for c in row:
            c.font = Font(name="微软雅黑", size=9)
            c.border = border
        st = row[3].value
        if st in status_color:
            row[3].fill = PatternFill("solid", fgColor=status_color[st])
        if row[1].value == "未匹配":
            row[1].font = Font(name="微软雅黑", size=9, color="999999", italic=True)

    widths = [30, 30, 16, 10, 14, 22, 12, 12, 8, 40, 16]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    ws.freeze_panes = "A3"
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    ws["A1"].font = Font(name="微软雅黑", bold=True, size=12)
    ws["A1"].alignment = Alignment(horizontal="center")
    wb.save(path)


if __name__ == "__main__":
    main()
