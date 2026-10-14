#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""官网内容验证器：判定 (1) 是否有指定产品 (2) 是否有生产设备 (3) 是否有英文/外文官网。

用法:
    python verify.py --input <名单.json> --config sources/aluminum-tube.yaml --out <输出目录> [--xlsx]

输入 JSON: [{"name": ..., "website": ...}, ...]
输出: <out>/verify_result.json, <out>/verify_result.md, [<out>/verify_result.xlsx]
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

try:
    import yaml
except ImportError:
    print("缺 PyYAML: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "en,zh-CN;q=0.9"}
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# SaaS 模板/平台域名：统一中文，无 EN 入口，直接标 SaaS模板 不重试
SAAS_HOSTS = ("cnal.com", "1688.com", "gys.cn", "b2b.", "made-in-china.com")

# 其他外文路径特征
LANG_PATHS = {
    "en": ("/en", "/en/", "/english", "/en-us", "/en/index.html", "/en/products"),
    "fr": ("/fr", "/fr/", "/french"),
    "de": ("/de", "/de/", "/german"),
    "es": ("/es", "/es/", "/spanish"),
    "ru": ("/ru", "/ru/", "/russian"),
    "ar": ("/ar", "/ar/", "/arabic"),
    "pt": ("/pt", "/pt/", "/portuguese"),
}
LANG_BUTTONS = {"en": ("english", "en"), "fr": ("français", "french", "fr"),
                "de": ("deutsch", "german", "de"), "es": ("español", "spanish", "es"),
                "ru": ("русский", "russian", "ru"), "ar": ("العربية", "arabic", "ar")}

EN_STRONG_SIGNALS = ('hreflang="en"', "hreflang='en'", 'hreflang="en-us"',
                     'hreflang="en-gb"', 'lang="en"', "lang='en'", "lang=en-us",
                     'href="/en"', "href='/en'", "english")


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


# ---------------------------------------------------------------- 抓取

def fetch(url: str, timeout: int = 10, max_bytes: int = 300_000) -> tuple[int, str, str]:
    """返回 (status, final_url, text)。失败 status=-1。
    自动回退：https→http，www→非www，http→https。"""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url.lstrip("/")
    parsed = re.match(r"(https?)://(www\.)?(.+)", url)
    variants = [url]
    if parsed:
        proto, www, rest = parsed.groups()
        variants.append(url.replace("https://", "http://", 1))
        if www:
            variants.append(f"{proto}://{rest}")
        else:
            variants.append(f"{proto}://www.{rest}")
    # 去重保序
    seen, uniq = set(), []
    for v in variants:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    last_err = ""
    for v in uniq:
        try:
            req = urllib.request.Request(v, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
                raw = r.read(max_bytes)
                charset = r.headers.get_content_charset() or "utf-8"
                try:
                    text = raw.decode(charset, "ignore")
                except LookupError:
                    text = raw.decode("utf-8", "ignore")
                return r.status, r.geturl(), text
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            # 403/404 也继续试下一个变体
            continue
        except Exception as e:
            last_err = str(e)[:50]
            continue
    return -1, uniq[0], ""


def strip_text(html_text: str) -> str:
    """去标签、去 script/style、实体解码，返回纯文本。"""
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html_text)
    t = re.sub(r"(?is)<!--.*?-->", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = html_mod.unescape(t)
    return re.sub(r"\s+", " ", t)


def text_stats(text: str) -> dict:
    """统计字符构成，用于判定实际语种。"""
    n = len(text)
    if n == 0:
        return {"len": 0, "cjk": 0, "latin": 0, "cjk_ratio": 0.0, "latin_ratio": 0.0}
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    return {"len": n, "cjk": cjk, "latin": latin,
            "cjk_ratio": cjk / n, "latin_ratio": latin / n}


# ---------------------------------------------------------------- 关键词

def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_hits(haystack_l: str, keywords) -> list[str]:
    flat = [k for g in keywords for k in g] if keywords and isinstance(keywords[0], list) else keywords
    return sorted({kw for kw in flat if kw.lower() in haystack_l})


def strong_context(html_text: str, hits: list[str]) -> list[str]:
    """title/h1/h2/产品卡片 中命中的词。"""
    heads = []
    for m in re.findall(r"(?is)<title[^>]*>(.*?)</title>", html_text):
        heads.append(m)
    for m in re.findall(r"(?is)<h[12][^>]*>(.*?)</h[12]>", html_text):
        heads.append(m)
    for m in re.findall(r'(?is)class="[^"]*(?:product|item|list|card)[^"]*"[^>]*>(.*?)<', html_text):
        heads.append(m)
    blob = " ".join(heads).lower()
    return [k for k in hits if k.lower() in blob]


EQUIP_SPEC = re.compile(r"\d+(?:\.\d+)?\s*(?:台|条|套|吨|T|MN|mm|inch|in)", re.I)


def equip_strong(html_text: str, hits: list[str]) -> list[str]:
    """设备词 200 字符窗口内出现规格数字 → 强。"""
    text_l = strip_text(html_text).lower()
    out = []
    for kw in hits:
        start = 0
        while True:
            i = text_l.find(kw.lower(), start)
            if i < 0:
                break
            window = text_l[i:i + 200]
            if EQUIP_SPEC.search(window):
                out.append(kw)
                break
            start = i + len(kw)
    return out


def grade(strong: list, weak_all: list) -> str:
    if strong:
        return "强"
    if weak_all:
        return "弱"
    return "无"


def looks_english(html_text: str) -> bool:
    """判定页面是否为英文内容。latin_ratio 阈值 0.6 会漏判 en.aluhf.com 这类
    主文中文、但导航/产品名英文的混合站；因此增加英文内容词探针作为补充。"""
    stats = text_stats(strip_text(html_text))
    if stats["latin_ratio"] > 0.6:
        return True
    if stats["cjk"] > 0 and EN_CONTENT_PROBE.search(html_text):
        # 中英混合：英文词数 ≥200 才认（防止只出现一两个英文术语）
        words = re.findall(r"[A-Za-z]{3,}", strip_text(html_text))
        if len(words) >= 200:
            return True
    return False


# 疑似英文的正向信号：语种统计把中文算作低 latin_ratio，但页面若含英文产品词或英文导航
EN_CONTENT_PROBE = re.compile(
    r"\b(product|products|about us|contact us|solution|solutions|certificate|certification"
    r"|aluminum|aluminium|profile|extrusion|manufacturer|factory|equipment|quality)\b", re.I)


# ---------------------------------------------------------------- 语言

def detect_en_entry(root_url: str, html_text: str) -> tuple[str, str, list]:
    """返回 (language, en_path, signals)。实测 EN 入口内容，英文比例 >60% 才算英文。"""
    signals = []
    low = html_text.lower()

    # 信号1: URL 路径
    parsed = re.match(r"(https?://[^/]+)(.*)", root_url)
    path = parsed.group(2) if parsed else ""
    if re.match(r"^/(en|english|en-us|en-gb)(/|$)", path, re.I):
        signals.append("en-path")
        if looks_english(html_text):
            return "英文", root_url, signals
        # en 路径但内容仍中文 → 继续找别的入口
        signals.append("en-path-but-zh-content")

    # 信号2: hreflang / lang 属性
    for sig in ('hreflang="en"', 'hreflang=\'en\'', 'hreflang="en-us"', 'hreflang="en-gb"',
                'lang="en"', "lang='en'"):
        if sig in low:
            signals.append(f"hreflang:{sig}")
            break

    # 语言切换按钮（正则大小写不敏感，标签内任意属性顺序均可）
    for m in re.finditer(r'(?is)<a\b[^>]*>(.*?)</a>', html_text):
        href_m = re.search(r'href=["\']([^"\']+)["\']', m.group(0))
        label = re.sub(r"<[^>]+>", " ", m.group(1))
        label = re.sub(r"\s+", " ", label).strip().lower()
        if label in ("english", "en", "英文", "english site") and href_m:
            signals.append("EN-link")
            en_url = urllib.parse.urljoin(root_url, href_m.group(1))
            st, fu, body = fetch(en_url, timeout=8)
            if st == 200 and body:
                if looks_english(body):
                    return "英文", fu, signals
                signals.append("EN-link-content-not-en")
            break

    # 常见 EN 路径盲试
    base = re.match(r"(https?://[^/]+)", root_url)
    if base:
        for p in ("/en/", "/en", "/en/index.html", "/en/products"):
            st, fu, body = fetch(base.group(1) + p, timeout=6)
            if st == 200 and body:
                if looks_english(body):
                    return "英文", fu, signals + [f"blind:{p}"]
                signals.append(f"blind:{p}-not-en")

    # 其他外文
    others = []
    for lang, paths in LANG_PATHS.items():
        if lang == "en":
            continue
        if any(f'hreflang="{lang}"' in low or f'lang="{lang}"' in low for _ in [0]):
            others.append(lang)
    if others:
        signals.append("other-lang:" + ",".join(others))
        return "多语", "", signals

    return "中文", "", signals


# ---------------------------------------------------------------- 主流程

def verify_one(item: dict, cfg: dict) -> dict:
    name = item.get("name", "")
    url = (item.get("website") or "").strip()
    res = {
        "name": name, "website": url, "final_url": "", "fetch_status": -1,
        "fetch_note": "", "content_len": 0,
        "product_hits": [], "product_strong": [],
        "equip_hits": [], "equip_strong": [],
        "trade_hits": [], "negative_hits": [],
        "has_product": "无", "has_equipment": "无", "is_manufacturer": "否",
        "language": "未知", "lang_detail": "", "en_path": "",
        "en_status": "无官网", "en_verified_by": [],
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }
    if not url:
        res["fetch_note"] = "无独立官网"
        return res

    host = urllib.parse.urlparse(url if "://" in url else "https://" + url).netloc.lower()
    if any(s in host for s in SAAS_HOSTS):
        res["fetch_note"] = "平台店铺页（非独立官网）"
        res["en_status"] = "平台店铺页"
        res["language"] = "中文"
        res["is_manufacturer"] = "待核实"
        return res

    st, final_url, body = fetch(url)
    res["fetch_status"], res["final_url"] = st, final_url
    if st == -1 or not body:
        res["fetch_note"] = "官网无法访问（保留地址待人工核实）"
        res["en_status"] = "官网无法访问"
        res["is_manufacturer"] = "待核实"
        return res
    if st != 200:
        res["fetch_note"] = f"HTTP {st}（保留地址待人工核实）"
        res["en_status"] = "官网无法访问"
        res["is_manufacturer"] = "待核实"
        return res
    if len(body.strip()) < 500:
        res["fetch_note"] = "疑似JS渲染(空壳)"
        res["en_status"] = "官网无法访问"
        return res

    text = strip_text(body)
    res["content_len"] = len(text)
    low = body.lower()

    # 产品
    pk = cfg.get("product_keywords") or []
    hits_p = find_hits(low, pk)
    strong_p = strong_context(body, hits_p)
    neg = cfg.get("product_forms", {}).get("negative", []) or []
    neg_hits = find_hits(low, neg)
    hp = grade(strong_p, hits_p)
    if neg_hits and not hits_p:
        hp = "无"
    elif neg_hits and hp == "强":
        hp = "弱"
    res["product_hits"], res["product_strong"], res["negative_hits"] = hits_p, strong_p, neg_hits
    res["has_product"] = hp

    # 设备
    ek = cfg.get("equipment_keywords") or []
    hits_e = find_hits(low, ek)
    strong_e = equip_strong(body, hits_e)
    res["equip_hits"], res["equip_strong"] = hits_e, strong_e
    res["has_equipment"] = grade(strong_e, hits_e)

    # 贸易特征
    ts = cfg.get("trade_signals") or []
    res["trade_hits"] = find_hits(low, ts)

    # 是否制造商
    if res["has_equipment"] in ("强", "弱") and res["trade_hits"] == []:
        res["is_manufacturer"] = "是"
    elif res["has_equipment"] in ("强", "弱"):
        res["is_manufacturer"] = "是"
    elif res["has_product"] in ("强", "弱") and res["trade_hits"]:
        res["is_manufacturer"] = "否"
    elif res["has_product"] in ("强", "弱"):
        res["is_manufacturer"] = "疑似"
    else:
        res["is_manufacturer"] = "否"

    # 语言
    lang, en_path, sigs = detect_en_entry(final_url or url, body)
    res["language"], res["en_path"], res["en_verified_by"] = lang, en_path, sigs
    stats = text_stats(text)
    res["lang_detail"] = f"eng={stats['latin_ratio']:.0%} cjk={stats['cjk_ratio']:.0%}"
    res["en_status"] = ("已验证英文版" if lang == "英文" else
                        "多语官网" if lang == "多语" else "纯中文官网")
    return res


# ---------------------------------------------------------------- 输出

MD_EMOJI = {"强": "🟢", "弱": "🟡", "无": "⚪", "是": "🟢", "疑似": "🟡", "否": "⚪"}


def write_md(results: list[dict], path: str) -> None:
    lines = ["# 官网内容验证结果", "",
             f"共 {len(results)} 条 · 生成于 {datetime.now():%Y-%m-%d %H:%M}", "",
             "| 公司 | 官网 | 产品 | 设备 | 制造商 | 语言 | EN入口 | 状态 |",
             "|---|---|---|---|---|---|---|---|"]
    for r in results:
        lines.append(
            "| {name} | [{url}]({final_url}) | {p} | {e} | {m} | {lang} | {ep} | {st} |".format(
                name=r["name"],
                url=(r["website"] or "-")[:40],
                final_url=r["final_url"] or r["website"],
                p=MD_EMOJI.get(r["has_product"], r["has_product"]),
                e=MD_EMOJI.get(r["has_equipment"], r["has_equipment"]),
                m=MD_EMOJI.get(r["is_manufacturer"], r["is_manufacturer"]),
                lang=r["language"],
                ep=r["en_path"] or "-",
                st=r["en_status"] + (f"({r['fetch_note']})" if r["fetch_note"] else ""),
            ))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_xlsx(results: list[dict], path: str) -> bool:
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        print("跳过 xlsx（缺 openpyxl）", file=sys.stderr)
        return False
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "官网内容验证"
    heads = ["公司", "官网", "最终URL", "状态", "产品判定", "设备判定", "是否制造商",
             "语言", "语言细节", "EN入口", "产品命中", "设备命中", "贸易特征", "负向命中", "备注", "官网类型"]
    ws.append(heads)
    fill = PatternFill("solid", fgColor="1F4E79")
    for c in ws[1]:
        c.fill = fill
        c.font = Font(color="FFFFFF", bold=True, name="微软雅黑")
        c.alignment = Alignment(vertical="center", horizontal="center")
    green = PatternFill("solid", fgColor="E2EFDA")
    yellow = PatternFill("solid", fgColor="FFF2CC")
    for r in results:
        ws.append([
            r["name"], r["website"], r["final_url"], r["fetch_status"],
            r["has_product"], r["has_equipment"], r["is_manufacturer"],
            r["language"], r["lang_detail"], r["en_path"],
            ", ".join(r["product_hits"][:8]),
            ", ".join(r["equip_hits"][:8]),
            ", ".join(r["trade_hits"]),
            ", ".join(r["negative_hits"]),
            r["fetch_note"],
            "平台店铺页" if r["en_status"] == "平台店铺页" else
            "独立官网" if r["en_status"] in ("已验证英文版", "多语官网", "纯中文官网") else
            "无法访问",
        ])
        row = ws[ws.max_row]
        ok = r["is_manufacturer"] == "是" and r["en_status"] in ("已验证英文版", "多语官网")
        maybe = r["is_manufacturer"] == "疑似"
        for c in row:
            c.font = Font(name="微软雅黑")
            c.alignment = Alignment(vertical="center", wrap_text=False)
            if ok:
                c.fill = green
            elif maybe:
                c.fill = yellow
    widths = [30, 34, 40, 8, 10, 10, 12, 8, 16, 30, 40, 40, 20, 20, 24, 12]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(len(heads))}{ws.max_row}"
    wb.save(path)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="待验证名单 JSON（数组）")
    ap.add_argument("--config", required=True, help="品类 YAML 配置")
    ap.add_argument("--out", default="verify_out", help="输出目录")
    ap.add_argument("--xlsx", action="store_true", help="同时输出 Excel")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 条（调试用）")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    cfg = load_config(args.config)
    with open(args.input, encoding="utf-8") as f:
        items = json.load(f)
    if args.limit:
        items = items[: args.limit]

    results = []
    total = len(items)
    for i, item in enumerate(items, 1):
        log(f"[{i}/{total}] {item.get('name', '?')} — {item.get('website', '无官网')}")
        r = verify_one(item, cfg)
        results.append(r)
        log(f"    产品={r['has_product']} 设备={r['has_equipment']} "
            f"制造商={r['is_manufacturer']} 语言={r['language']} {r['fetch_note']}")
        time.sleep(0.3)

    with open(os.path.join(args.out, "verify_result.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    write_md(results, os.path.join(args.out, "verify_result.md"))
    if args.xlsx:
        write_xlsx(results, os.path.join(args.out, "verify_result.xlsx"))

    n_man = sum(1 for r in results if r["is_manufacturer"] == "是")
    n_en = sum(1 for r in results if r["en_status"] in ("已验证英文版", "多语官网"))
    n_prod = sum(1 for r in results if r["has_product"] == "强")
    log(f"完成：制造商 {n_man}/{total} · 产品强命中 {n_prod} · 英文/多语官网 {n_en}")
    log(f"输出目录: {args.out}")
    return 0


if __name__ == "__main__":
    import urllib.parse  # noqa: E402  (verify_one 用)
    sys.exit(main())
