import json, re
base = r"E:/OneDrive/00.其他必要事务/制造商爬虫/02.铝管"
queue = json.load(open(base+"/_verify_queue.json", encoding="utf-8"))
qcc = {r['name']: r for r in json.load(open(base+"/_qcc_verify.json", encoding="utf-8"))}

def nature(ct):
    if not ct: return "待验证"
    if '国有' in ct: return "国企"
    if '外商' in ct or '港澳台' in ct or '外国法人' in ct: return "外资/港澳台"
    if '自然人' in ct: return "私营"
    return ct[:12]

def tube_type(r):
    p = (r.get('products','') or '')
    types = []
    for kw,label in [('无缝','无缝铝管'),('毛细','毛细铝管'),('精密','精密铝管'),('扁管','扁管/多孔管'),
                     ('方管','方管'),('圆管','圆管'),('薄壁','薄壁铝管'),('大口径','大口径铝管'),
                     ('散热','散热铝管'),('热交换','热交换铝管')]:
        if kw in p: types.append(label)
    return '/'.join(types[:3]) if types else "铝管"

recs = []
for r in queue:
    q = qcc.get(r['name'], {})
    en = r.get('en_status','')
    enmap = {"已验证英文版":"★已核实英文版","纯中文官网":"纯中文","官网无法访问":"无法访问","未验证":"未验证","MIC英文店铺页":"MIC店铺页"}
    recs.append({
        "企业名称": r.get('name',''),
        "铝管品类": tube_type(r),
        "主营产品": (r.get('products','') or '')[:60],
        "英文官网": enmap.get(en,en),
        "官网": (r.get('website') or '').replace('https://','').replace('http://',''),
        "存续状态": q.get('operating','') or "待验证",
        "注册资金": q.get('reg_capital','') or "待验证",
        "企业性质": nature(q.get('company_type','')),
        "成立日期": q.get('established','') or "待验证",
        "信息渠道": ' / '.join(r.get('_channels',[])),
    })

def sk(x):
    verified = 0 if (x['注册资金']!='待验证' and x['存续状态']!='待验证') else 1
    star = 0 if '★' in x['英文官网'] else 1
    return (verified, star)
recs.sort(key=sk)

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
wb=Workbook(); ws=wb.active; ws.title="铝管制造商"
hf=PatternFill("solid",start_color="1F4E79"); hfont=Font(name="微软雅黑",size=11,bold=True,color="FFFFFF")
bfont=Font(name="微软雅黑",size=10)
star_f=PatternFill("solid",start_color="E2EFDA")
pend_f=PatternFill("solid",start_color="FFF2CC")
ok_f=PatternFill("solid",start_color="DDEBF7")
bd=Border(*[Side(style='thin',color='D9D9D9')]*4)
ncol=len(recs[0])
ws.merge_cells(f'A1:{get_column_letter(ncol)}1')
ws['A1']="铝管制造商候选名单（4渠道 · 企查查工商验证）"
ws['A1'].font=Font(name="微软雅黑",size=14,bold=True,color="1F4E79")
ws['A1'].alignment=Alignment(horizontal="center",vertical="center"); ws.row_dimensions[1].height=32
headers=list(recs[0].keys())
for c,h in enumerate(headers,1):
    cell=ws.cell(2,c,h); cell.fill=hf; cell.font=hfont; cell.border=bd
    cell.alignment=Alignment(horizontal="center",vertical="center",wrap_text=True)
ws.row_dimensions[2].height=30
for i,r in enumerate(recs,3):
    is_star='★' in r['英文官网']
    is_verified = r['注册资金']!='待验证'
    for c,h in enumerate(headers,1):
        cell=ws.cell(i,c,r[h]); cell.font=bfont; cell.border=bd
        cell.alignment=Alignment(vertical="center",wrap_text=(h in['主营产品','地址','官网']))
        if is_star: cell.fill=star_f
        elif h in ['存续状态','注册资金','企业性质','成立日期'] and not is_verified: cell.fill=pend_f
        elif h in ['存续状态','注册资金','企业性质','成立日期'] and is_verified: cell.fill=ok_f
widths={"企业名称":26,"铝管品类":15,"主营产品":32,"英文官网":13,"官网":28,"存续状态":14,"注册资金":11,"企业性质":11,"成立日期":12,"信息渠道":16}
for c,h in enumerate(headers,1): ws.column_dimensions[get_column_letter(c)].width=widths.get(h,12)
ws.freeze_panes="A3"; ws.auto_filter.ref=f"A2:{get_column_letter(ncol)}{len(recs)+2}"
out=base+"/铝管制造商_验证结果.xlsx"; wb.save(out)

from openpyxl import load_workbook
wb2=load_workbook(out); ws2=wb2.active
hdr={ws2.cell(2,c).value:c for c in range(1,ws2.max_column+1)}
wc=hdr.get("官网")
for i in range(3, ws2.max_row+1):
    cell=ws2.cell(i, wc); url=cell.value
    if url:
        full=url if url.startswith('http') else 'http://'+url
        cell.hyperlink=full; cell.font=Font(name="微软雅黑",size=10,color="0563C1",underline="single")
wb2.save(out)
n_ver=len([r for r in recs if r['注册资金']!='待验证'])
n_star=len([r for r in recs if '★' in r['英文官网']])
print(f"已保存 {out}")
print(f"总计{len(recs)}家 | 工商已验证{n_ver}家 | 英文版已核实{n_star}家")
