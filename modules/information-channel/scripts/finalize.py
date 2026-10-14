#!/usr/bin/env python3
"""
爱企查批量验证 + 美化Excel (在 browser_exec 内联调用验证逻辑, 本脚本负责结果汇总+美化)
前置: _aiqicha_results.json 已由 browser_exec 验证环节生成
用法: python finalize.py <pool_dir>
"""
import json, re, sys, os, urllib.request, ssl
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def classify(r):
    s = (r.get('products','') or '') + (r.get('orig','') or '')
    for kw,cat in [('铝管','铝管'),('tube','铝管'),('pipe','铝管'),
                   ('型材','铝型材'),('profile','铝型材'),('extrusion','铝型材')]:
        if kw in s.lower(): return cat
    return "铝管/型材"

def finalize(pool_dir):
    final = json.load(open(os.path.join(pool_dir,"_final_small.json"),encoding="utf-8"))
    en_path = os.path.join(pool_dir,"_en_checked.json")
    en_checked = {r['search']:r for r in json.load(open(en_path,encoding="utf-8"))} if os.path.exists(en_path) else {}
    ch_map = {"搜索引擎":"搜索引擎","B2B外贸(MIC)":"B2B外贸","海关数据(ImportYeti)":"海关数据","展会":"展会","资质认证":"资质认证"}

    recs=[]
    for r in final:
        en=r.get('has_en'); st=en_checked.get(r['search'],{}).get('en_site_accessible','') if en else ''
        disp="已验证" if (en and 'OK' in st) else ("MIC子域" if en else "—")
        web=(r.get('website') or '').replace('https://','').replace('http://','')
        recs.append({"企业名称":r['search'],"产品类别":classify(r),"注册资金(万元)":r.get('reg_capital',''),
            "存续状态":r.get('operating',''),"企业性质":r.get('soe',''),"英文官网":disp,"官网":web,
            "地址":r.get('address',''),"联系人(法人)":r.get('legal',''),"联系电话":r.get('contact',''),
            "信息渠道":' / '.join(ch_map.get(c,c) for c in r.get('channels',[]))})
    def sk(x):
        t={"已验证":0,"MIC子域":1,"—":2}[x['英文官网']]
        cap=float(x['注册资金(万元)'].replace(',','')) if x['注册资金(万元)'] else 0
        return (t,-cap)
    recs.sort(key=sk)

    # 美化Excel
    wb=Workbook(); ws=wb.active; ws.title="制造商"
    hf=PatternFill("solid",start_color="1F4E79"); hfont=Font(name="微软雅黑",size=11,bold=True,color="FFFFFF")
    bfont=Font(name="微软雅黑",size=10)
    en_f=PatternFill("solid",start_color="E2EFDA"); mic_f=PatternFill("solid",start_color="FFF2CC")
    bd=Border(*[Side(style='thin',color='D9D9D9')]*4)
    ws.merge_cells(f'A1:{get_column_letter(len(recs[0]))}1')
    ws['A1']="制造商候选名单（中小型私营 · 存续）"; ws['A1'].font=Font(name="微软雅黑",size=14,bold=True,color="1F4E79")
    ws['A1'].alignment=Alignment(horizontal="center",vertical="center"); ws.row_dimensions[1].height=32
    headers=list(recs[0].keys())
    for c,h in enumerate(headers,1):
        cell=ws.cell(2,c,h); cell.fill=hf; cell.font=hfont; cell.border=bd
        cell.alignment=Alignment(horizontal="center",vertical="center",wrap_text=True)
    ws.row_dimensions[2].height=28
    for i,r in enumerate(recs,3):
        fill=en_f if r['英文官网']=='已验证' else (mic_f if r['英文官网']=='MIC子域' else None)
        for c,h in enumerate(headers,1):
            cell=ws.cell(i,c,r[h]); cell.font=bfont; cell.border=bd
            cell.alignment=Alignment(vertical="center",wrap_text=(h in['地址','官网']))
            if fill: cell.fill=fill
    widths={"企业名称":24,"产品类别":12,"注册资金(万元)":13,"存续状态":9,"企业性质":9,"英文官网":10,"官网":38,"地址":36,"联系人(法人)":12,"联系电话":14,"信息渠道":20}
    for c,h in enumerate(headers,1): ws.column_dimensions[get_column_letter(c)].width=widths.get(h,14)
    ws.freeze_panes="A3"; ws.auto_filter.ref=f"A2:{get_column_letter(len(headers))}{len(recs)+2}"
    out=os.path.join(pool_dir,"制造商_验证结果.xlsx"); wb.save(out)
    print(f"已保存 {out} | {len(recs)}家")
    return out

if __name__=="__main__":
    finalize(sys.argv[1] if len(sys.argv)>1 else ".")
