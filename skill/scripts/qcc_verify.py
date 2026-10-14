#!/usr/bin/env python3
"""
企查查移动API批量工商验证 (在 execute_code 内核里分批调用, 每批<=20家)
输入: <pool_dir>/_verify_queue.json  (含 name/website/en_status/products)
输出: <pool_dir>/_qcc_verify.json   (追加落盘, 断点续跑)

字段来源:
  搜索页 m.qcc.com/search?key=<公司名>: 注册资本/成立日期/firm_id/命中家数
  firm页 m.qcc.com/firm/<id>.html: 登记状态(存续)/企业类型(国企/私营/外资)
企业性质判断: '国有'->国企; '外商|港澳台|外国法人'->外资/港澳台; '自然人'->私营

运行约束: 必须在 execute_code 内核跑(hermes_tools专属); Python313独立进程
无 hermes_tools 且 requests 直连被风控返回空。每批<=20家防5分钟超时,
每家居即 json.dump 落盘断点续跑。
"""
import json, re, urllib.parse, time, os
from hermes_tools import web_extract

BATCH_LIMIT = 18   # 每批家数, 防 execute_code 5分钟超时
CHAR_LIMIT = 2500

def _search(name, retries=1):
    url = f"https://m.qcc.com/search?key={urllib.parse.quote(name)}"
    for _ in range(retries + 1):
        try:
            content = web_extract(urls=[url], char_limit=CHAR_LIMIT)['results'][0].get('content', '')
            if len(content) < 20:
                continue
            cnt = re.search(r'搜索到\s*(\d+)\s*家', content)
            if not cnt:
                return {"found": "0", "reg_capital": "", "established": "", "firm_id": "", "qcc_name": ""}
            firm = re.search(r'\(/firm/([a-f0-9]+)\.html\)', content)
            cap = re.search(r'注册资本\s*\n+\s*([\d,\.]+\s*[万元美元]*)', content)
            est = re.search(r'成立日期\s*\n+\s*([\d\-]+)', content)
            ename = re.search(r'\[([^\]]{4,40})\]\(/firm/', content)
            return {"found": cnt.group(1),
                    "qcc_name": ename.group(1) if ename else "",
                    "reg_capital": cap.group(1).strip() if cap else "",
                    "established": est.group(1) if est else "",
                    "firm_id": firm.group(1) if firm else ""}
        except Exception:
            pass
    return {"found": "err", "reg_capital": "", "established": "", "firm_id": "", "qcc_name": ""}

def _firm_detail(firm_id, retries=1):
    url = f"https://m.qcc.com/firm/{firm_id}.html"
    for _ in range(retries + 1):
        try:
            content = web_extract(urls=[url], char_limit=CHAR_LIMIT)['results'][0].get('content', '')
            if len(content) < 30:
                continue
            op = re.search(r'登记状态\s*\n+\s*([^\n]+)', content)
            ct = re.search(r'企业类型\s*\n+\s*([^\n]+)', content)
            return {"operating": op.group(1).strip() if op else "",
                    "company_type": ct.group(1).strip() if ct else ""}
        except Exception:
            pass
    return {"operating": "", "company_type": ""}

def nature(company_type):
    """企业类型 -> 企业性质"""
    if not company_type:
        return "待验证"
    if '国有' in company_type:
        return "国企"
    if '外商' in company_type or '港澳台' in company_type or '外国法人' in company_type:
        return "外资/港澳台"
    if '自然人' in company_type:
        return "私营"
    return company_type[:12]

def run_batch(pool_dir):
    """跑一批(<=BATCH_LIMIT家), 每家居即落盘, 返回剩余未验证数"""
    queue = json.load(open(os.path.join(pool_dir, "_verify_queue.json"), encoding="utf-8"))
    out_file = os.path.join(pool_dir, "_qcc_verify.json")
    results = json.load(open(out_file, encoding="utf-8")) if os.path.exists(out_file) else []
    done = {r['name'] for r in results}
    n0 = len(results)
    for r in queue:
        if len(results) - n0 >= BATCH_LIMIT:
            break
        if r['name'] in done:
            continue
        res = _search(r['name'])
        if res.get('firm_id') and not res.get('company_type'):
            res.update(_firm_detail(res['firm_id']))
        res['website'] = r.get('website', '')
        res['en_status'] = r.get('en_status', '')
        results.append(res)
        json.dump(results, open(out_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    remaining = len([r for r in queue if r['name'] not in {x['name'] for x in results}])
    hit = len([x for x in results if x.get('reg_capital') and x.get('operating')])
    print(f"已存 {len(results)} 家(完整 {hit} 家), 剩余 {remaining} 家")
    return remaining

# execute_code 内用法: 反复调用 run_batch(pool_dir) 直到 remaining==0
if __name__ == "__main__":
    import sys
    pool = sys.argv[1] if len(sys.argv) > 1 else "."
    while run_batch(pool) > 0:
        pass
