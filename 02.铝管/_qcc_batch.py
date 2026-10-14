import json, re, urllib.parse, time, os
import requests

base = r"E:/OneDrive/00.其他必要事务/制造商爬虫/02.铝管"
queue = json.load(open(base+"/_verify_queue.json", encoding="utf-8"))
out_file = base+"/_qcc_verify.json"

results = []
done_names = set()
if os.path.exists(out_file):
    results = json.load(open(out_file, encoding="utf-8"))
    done_names = {r['name'] for r in results}
    print(f"断点续跑: 已完成 {len(done_names)} 家", flush=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

def fetch(url, retries=3):
    for _ in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200 and len(r.text) > 100:
                return r.text
        except Exception:
            time.sleep(1.5)
    return ""

def strip_html(html):
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.S)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.S)
    html = re.sub(r'<a[^>]*href="/firm/([a-f0-9]+)\.html"[^>]*>(.*?)</a>', r' [FIRM:\1]\2 ', html, flags=re.S)
    text = re.sub(r'<[^>]+>', '\n', html)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n', text)
    return text

def verify_qcc(name):
    url = f"https://m.qcc.com/search?key={urllib.parse.quote(name)}"
    html = fetch(url)
    if not html:
        return {"name":name,"found":"err","reg_capital":"","established":"","firm_id":"","qcc_name":"","company_type":""}
    text = strip_html(html)
    cnt = re.search(r'搜索到\s*(\d+)\s*家', text)
    if not cnt:
        return {"name":name,"found":"0","reg_capital":"","established":"","firm_id":"","qcc_name":"","company_type":""}
    firm = re.search(r'\[FIRM:([a-f0-9]+)\]', text)
    cap = re.search(r'注册资本\s*\n+\s*([\d,\.]+\s*[万元美元]*)', text)
    est = re.search(r'成立日期\s*\n+\s*([\d\-]+)', text)
    ename = re.search(r'\[FIRM:[a-f0-9]+\]\s*([^\n\[]{4,40})', text)
    return {"name":name,"found":cnt.group(1),
            "qcc_name": ename.group(1).strip() if ename else "",
            "reg_capital": cap.group(1).strip() if cap else "",
            "established": est.group(1) if est else "",
            "firm_id": firm.group(1) if firm else "",
            "company_type":""}

def fetch_firm_detail(firm_id):
    url = f"https://m.qcc.com/firm/{firm_id}.html"
    html = fetch(url)
    if not html: return {"operating":"","company_type":""}
    text = strip_html(html)
    op = re.search(r'登记状态\s*\n+\s*([^\n]+)', text)
    ct = re.search(r'企业类型\s*\n+\s*([^\n]+)', text)
    return {"operating": op.group(1).strip() if op else "",
            "company_type": ct.group(1).strip() if ct else ""}

for i, r in enumerate(queue):
    if r['name'] in done_names: continue
    res = verify_qcc(r['name'])
    if res.get('firm_id') and not res.get('company_type'):
        detail = fetch_firm_detail(res['firm_id'])
        res.update(detail)
    res['website'] = r.get('website','')
    res['en_status'] = r.get('en_status','')
    results.append(res)
    ok = "Y" if res.get('reg_capital') else "N"
    print(f"[{len(results):2}/{len(queue)}]{ok} {res['name'][:16]:16} | {res.get('found',''):3}家 | {res.get('reg_capital','') or '-':9} | {(res.get('operating','') or '-')[:10]:10} | {(res.get('company_type','') or '-')[:14]}", flush=True)
    json.dump(results, open(out_file,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    time.sleep(0.5)

ok_n = len([x for x in results if x.get('reg_capital')])
print(f"\n完成: {ok_n}/{len(results)} 家拿到注册资金")
