#!/usr/bin/env python3
"""
制造商挖掘 - 清洗去重 + 验证结果汇总 + 美化Excel
用法: python aggregate.py <pool_dir>
依赖: openpyxl
"""
import json, re, sys, os

def run(pool_dir):
    # 1. 合并5渠道JSON
    channel_files = ["search_engine.json","b2b_mic.json","customs_importyeti.json",
                     "exhibition.json","certification.json"]
    ch_names = {"search_engine.json":"搜索引擎","b2b_mic.json":"B2B外贸",
                "customs_importyeti.json":"海关数据","exhibition.json":"展会",
                "certification.json":"资质认证"}
    all_c = []
    for f in channel_files:
        p = os.path.join(pool_dir, f)
        if not os.path.exists(p): continue
        d = json.load(open(p, encoding="utf-8"))
        cands = d.get("candidates", d if isinstance(d,list) else [])
        for c in cands:
            c["_channel"] = ch_names[f]
            all_c.append(c)

    # 2. 域名去重(最可靠)
    def domain(url):
        if not url: return ""
        m = re.search(r'https?://([^/\s]+)', url)
        return m.group(1).lower().replace('www.','') if m else ""
    def score(x): return sum([bool(x.get('products')), bool(x.get('address')), len(x.get('_channels',[1]))])
    by_domain, no_domain = {}, []
    for v in all_c:
        d = domain(v.get("website",""))
        if not d: no_domain.append(v); continue
        if d not in by_domain or score(v) > score(by_domain[d]):
            by_domain[d] = v
    merged = list(by_domain.values()) + no_domain

    # 2b. 企业名归一化二级去重(同一企业多个域名/别名的合并成一条,保留信息最全的)
    def name_key(nm):
        s = re.sub(r'[（(].*?[）)]', '', nm or '')      # 去括号别名
        s = re.sub(r'(股份有限)?(责任)?公司|集团|有限|公司', '', s)  # 去公司后缀
        return re.sub(r'[\s·]', '', s)
    by_name = {}
    for v in merged:
        k = name_key(v.get('name', ''))
        if not k:
            continue
        if k not in by_name or score(v) > score(by_name[k]):
            by_name[k] = v
    merged = list(by_name.values())

    # 3. 排除大型(黑名单按品类传入, 这里用通用)
    BIG = os.environ.get("BIG_BLACKLIST","").split("|") if os.environ.get("BIG_BLACKLIST") else []
    clean = []
    for v in merged:
        nm = v.get('name','') or ''
        generic = (v.get('products','') or '').strip() in ['铝型材/铝制品','']
        if not v.get('website') and generic: continue  # 无官网+产品笼统
        if any(b and b in nm for b in BIG): continue
        clean.append(v)
    json.dump(clean, open(os.path.join(pool_dir,"_clean.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"合并{len(all_c)}→去重{len(merged)}→清洗{len(clean)}")
    return clean

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv)>1 else ".")
