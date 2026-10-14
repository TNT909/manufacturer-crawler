---
name: industrial-manufacturer-discovery
description: "Find Chinese manufacturers, verify registration & website."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [manufacturer, sourcing, crawling, aiqicha, bidding, china]
    category: research
    related_skills: [bid-project-background-research, grounded-citations]
---

# Industrial Manufacturer Discovery (国内工业品制造商挖掘)

## When to Use

- "找XX品类的制造商/厂家"（铝型材、阀门、绝缘子、电力金具等任意工业品）
- 被要求"建立信息渠道"/"梳理有哪些发现渠道"/列渠道清单时（先实测探测再答，见阶段1）
- 投标需要筛选合格制造商候选池并做工商核验
- 需要产出带存续状态/注册资金/企业性质/英文官网的制造商名单

User runs this repeatedly across projects: each product category becomes a
folder under the scratch/alu_pool-style dir. Deliverable = 美化 Excel + Markdown
报告，英文官网企业优先排前。

## Workflow (阶段0标书解析 → 4渠道发现 → 清洗 → 工商核验 → 官网验证 → 整合交付)

### 阶段0: 标书解析(输入是招标文件时)
先读标书提取: 产品规格(材质/标准/尺寸/壁厚)、数量与分标(Lot)、用途与业主、截标日期、投标资格(是否仅制造商/ISO要求)、价值量级估算(数量→理论吨位→单价×汇率, 给用户一个 $/人民币 数量级判断即可, 不要求精确)。据此定: 品类关键词(cn/en)、该品类国企/大型上市黑名单、产品/设备/负向词 YAML。例: SONELGAZ 管线钢管标=API 5L PSL2 无缝+3LPE/环氧, 928km/≈$35M, 仅制造商可投。

### 阶段1: 4渠道并行爬取候选池
用 delegate_task 并行 spawn 4 个 subagent（每个产 ≥30家，JSON格式统一）：

- **关键词试点已验证搜索引擎是核心渠道**: 单品类跑3组查询(中文品名+厂家/官网、中文品名+制造+有限公司、英文品名+manufacturer)约得24条原始结果, 可直接挖出约10家有独立官网的企业, 无需先建庞大关键词表再开跑——小样验证后按发现的企业类型迭代扩词即可。
2. **B2B外贸(MIC)** — 中国制造网英文关键词翻分类页，抓供应商详情页
3. **展会** — 搜行业展参展商名录(官网常不可达000,改用Bing搜'XX展 展商名录')，逐家核实官网
4. **资质认证** — 搜'产品 ISO9001/CE/高新技术企业/专精特新'等，参考行业协会会员名录
5. **微信生态** — 搜狗微信搜索 `weixin.sogou.com/weixin?type=2`（实测可搜、无验证码）: 行业公众号常发"国网中标企业汇总榜"/"XX厂家排名"/"专精特新推荐", 一次查询即可成批提取企业名（实测"绝缘子厂家 公司"→10条真实企业名单）。文章是第三方转载非厂商一手信息, 拿到企业名仍需回搜索引擎找独立官网; 搜狗有 antispider, 需控制请求频率。
6. **抖音等 JS 重、反爬强的平台** — 免登采集走不通（搜索接口返回 status_code 2483/verify_check）, 必须第三方开源项目 + 登录 cookie, 按 `references/platform-scraper-integration.md` 的流程搭建

(海关渠道不在发现模块范围: ImportYeti搜索只收单词(空格→422)、返回的是美国进口商不是中国供应商、官方API需key(401)，并已实测当前403封锁; UN Comtrade API `https://comtradeapi.un.org/public/v1/preview/C/A/HS?reporterCode=156&period=2024&cmdCode=<HS>&flowCode=X`免费无需key、已实测可返回(count≈193条,HS7604铝型材)，但仅国家级汇总。两者都定位不到具体企业 → 归独立的品类背景模块, 不列入发现渠道清单。)

**发现渠道全景(实测底稿)**: `references/discovery-channels.md` — 搜索引擎/B2B外贸/B2B内贸/行业垂直/展会五类, 每类带实测可达性与坑。渠道状态会变, 回答'有哪些渠道'类问题前先实测探测再答(见下), 该文件只作底稿不作答案。

**被要求梳理渠道清单时, 先实测再回答**: 不要凭记忆或本文档直接罗列。用 execute_code 并行跑 `curl -sS -o /dev/null -L --max-time 12 -w "%{http_code}|%{url_effective}|%{time_total}" -A "Mozilla/5.0..."` 探测每个源的可访问性, 再用 web_search 跑1组小品类查询实测候选产出量, 最后才整理成渠道表。实测能发现文档未记的不可达源与真实产出。

**发现期采集要求(每个 subagent 的必含指令, 只含发现模块范围)**:
- **英文公司名必须先解析中文全称再入池**: name字段最终是中文公司名(企查查/爱企查验证依赖中文名)，英文名放notes。解析途径: 官网About页、百度搜索英文名+地名、MIC详情页中文标注。
- **website 必须是独立官网**: MIC子域名(en.made-in-china.com)是平台店铺页不算官网，须找到企业独立域名；找不到的标"待核实"。
- 排除境外展商/供应商(关键词: Indonesia/印尼/PT./境外)。
- **confidence 必须如实自标**: 设备厂/贸易商/疑似非目标品类标 low 并在 notes 写明理由(如"制管设备厂, 建议剔除"/"规模偏大归属需复核"), 汇总时按 confidence 过滤; 不要为凑每渠道 30 家的数量把无关企业标 high

**以下两项不属发现期要求, 各由独立模块处理, 发现期不要求subagent验证**:
- 英文站(has_english_site) → 阶段4用 scripts/verify.py 内容实测统一判定; 发现期该字段留空待测, 禁止凭MIC英文店铺页或猜测标true
- 产品形态(products) → 发现期只写品类; 用户只要特定形态时(如只做铝管、排除只做型材)再在阶段2按products字段过滤


每个 subagent 写 JSON 到 `E:\OneDrive\00.其他必要事务\制造商爬虫\<品类>\<channel>.json`，格式：
`{"channel":"","candidates":[{"name":"","website":"","address":"","products":"","source_url":"","has_english_site":bool,"confidence":"","notes":""}]}`

### 阶段2: 清洗去重
- 按**官网域名**去重(最可靠)，同域名保留信息最全的
- **域名去重后必须再做企业名归一化二级去重**: 同一家企业常有多个域名/别名(en.xxx.com 与 xxx.com、集团公司与子公司、不同渠道采到不同官网), 域名去重合并不掉, 交付表里会出现同一家企业重复占行(实测管线钢管 96 家里 天应泰×2/中原管道×2/河北神舟×3)。在域名去重后加一轮按名去重, 键=去括号别名+去公司后缀(`re.sub(r'[（(].*?[）)]','',s)` → `re.sub(r'(股份有限)?(责任)?公司|集团|有限|公司','',s)` → 去空白), 同键保留 score 最高的一条。别名差异大(简称 vs 全称)的合并不掉, 靠最后一步人工核对
- 排除：大型国企/上市公司(凤铝/坚美/华建/忠旺/中铝等按品类列黑名单; 管线钢管类另含 天津钢管/宝钢/宝武/鞍钢/衡阳/久立/友发/东宏股份/金洲 等上市钢企与管道集团)、无官网+产品笼统的贸易商、境外企业(Indonesia/印尼/PT./境外关键词)
- **黑名单还要含"卖设备不卖产品"的设备厂**: 制管机械厂(如太原锦通类)会被 B2B 渠道当管道企业误采, 按产品词与工商经营范围剔除, 别让 subagent 自标 high 就放进来
- **产品形态过滤**(用户指定特定形态时): 按products字段过滤——如只要铝管则保留含'管'且不含'仅型材/只做型材/型材为主'标注的条目
- 产物: `_clean.json`(中小私营候选) + `_verify_queue.json`(剔除MIC店铺页、名称待核实且无官网项后的待验证名单)
- **交付前核对交付表无重复企业**: 合并多渠道后域名去重不够(见上), finalize 出表后 grep 报告里企业名称列查重(同名出现>1次即有多域名未合并), 发现重复要改 aggregate 加企业名二级去重再**全链重跑**(aggregate→verify→tyc→finalize, 全量重跑会干净覆盖旧结果), 不要手工删表里的行——_clean.json 没改, 下次重跑又回来


### 阶段3: 工商验证 (天眼查 tyc_verify.py 首选, 企查查移动API备选, 爱企查CDP末选)

**首选 — 天眼查小程序接口 `tyc_verify.py` (实测命中率82%, 无登录/无浏览器门槛)**: 输入 xlsx(A列企业名, 第2行起) 或 json, 输出 `<输入stem>_tyc.json` + `_tyc.xlsx`; 请求头脚本内置(`x-auth-token` 用 `***` 占位即可), **请求间隔3.0秒勿调快**(<1s被限流返回空列表), companyCount=None 时退避重试; 自动两级匹配(全名→去括号核心词); 企业性质=tagList+注册资本币种组合推断。109家约6分钟, 长任务用 terminal(background=True, notify=True)。英文名/简称仍会 total=0, 需先转中文全称。命中率远高于企查查(约43%), 只有 tyc 持续抽不到时才切企查查。

渠道全景(官方官网/网页会话/MCP/开放API、各自凭证门槛与实测状态)见 `references/verification-channels.md`; 被问"有哪些核验方案/渠道"、或想把核验升级为无浏览器自动化时先读它。

**备选 — 企查查移动版API (tyc 抽不到时用; 无需登录, web_extract直接可读)**:

```python
# 1. 搜索接口: 返回企业列表+注册资本+成立日期+firm_id
from hermes_tools import web_extract
url = f"https://m.qcc.com/search?key={urllib.parse.quote(company)}"
content = web_extract(urls=[url], char_limit=2500)['results'][0].get('content','')
cnt  = re.search(r'搜索到\s*(\d+)\s*家', content)          # 命中家数
firm = re.search(r'\(/firm/([a-f0-9]+)\.html\)', content)  # firm_id
cap  = re.search(r'注册资本\s*\n+\s*([\d,\.]+\s*[万元美元]*)', content)
est  = re.search(r'成立日期\s*\n+\s*([\d\-]+)', content)

# 2. firm详情页: 存续状态+企业类型(区分国企/私营/外资)
url2 = f"https://m.qcc.com/firm/{firm_id}.html"
content2 = web_extract(urls=[url2], char_limit=2500)['results'][0].get('content','')
op = re.search(r'登记状态\s*\n+\s*([^\n]+)', content2)  # 在业/存续（在营、开业、在册）
ct = re.search(r'企业类型\s*\n+\s*([^\n]+)', content2)  # 国有/自然人→私营/外商港澳台→外资
```

企业性质判断: 企业类型含'国有'→国企; 含'外商/港澳台/外国法人'→外资/港澳台; 含'自然人'→私营。

**关键运行约束(踩坑)**:
- 必须走 web_extract(Keenable出口IP能过企查查风控); Python313独立进程requests直连m.qcc.com会被反爬返回空——批量验证只能在execute_code内核里跑(hermes_tools专属), 不能写成Python313后台常驻脚本
- execute_code有5分钟超时: 每批15-20家, 每处理一家立即json.dump落盘(断点续跑), 超时被杀后从落盘文件续跑
- 搜索结果HTML结构偶有差异(搜到N家但注册资本抽不到): 重试1次仍失败标"待验证", 不卡整批
- 实测命中率约43%(82家中35家拿到完整工商数据)

**末选 — 爱企查CDP验证 (tyc 与企查查都抽不到时才用, 需用户浏览器登录)**:

**前置0 — CDP调试端口**: browser_exec 通过 `http://127.0.0.1:9222/json/list` 连本地 Chrome。该端口**跨turn会断**(进程被回收/用户关闭了带端口的Chrome)，症状是 browser_exec 报 `BU_CDP_URL unreachable / WinError 10061`。恢复办法:

1. 先 `curl -s http://127.0.0.1:9222/json/version` 和 `netstat -ano | grep 9222` 确认确实无监听(空返回=真断了)
2. 让用户**完全关闭所有 Chrome 窗口**(任务管理器确认无 chrome.exe 残留)
3. 用**默认用户数据目录**启动(保住爱企查登录态):
   `terminal(command='"C:/Program Files/Google/Chrome/Application/chrome.exe" --remote-debugging-port=9222', background=True)`
4. `sleep 5` 后 curl 验证 `/json/version` 有返回
5. 再让用户在**这个** Chrome 里打开 aiqicha.baidu.com 并登录

**绝不能用独立 `--user-data-dir`**: 那样启动的 Chrome 没有用户的登录cookie，打开爱企查要重新登录，等于白干。

企查查移动API不需要任何登录/浏览器操作, 验证队列准备好后直接跑; 只有当它抽不到数据(约57%)或需要法定代表人/电话等深字段时, 才提示用户打开爱企查浏览器走CDP备选。

**CDP备选路径的平台选择**: 仅在企查查API抽不到数据时才需要用户浏览器——`curl -s http://127.0.0.1:9222/json/list` 看用户Chrome里已开哪个核验平台, 顺其自然用那个。核验机制(CDP location.href导航)对三者通用。

验证机制(踩坑后唯一可行的路)：
```python
# 1. 找到用户已登录的 aiqicha 标签页, CDP附加
import urllib.request, json
tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/list"))
aiq = [t for t in tabs if t.get('type')=='page' and 'aiqicha.baidu.com' in t.get('url','')]
attach = cdp('Target.attachToTarget', targetId=aiq[0]['id'], flatten=True)
sid = attach['sessionId']

# 2. 每家: 用 location.href 导航(不能用 CDP Page.navigate — 会触发反爬0结果)
cdp('Runtime.evaluate', expression=f"location.href='/s?q='+encodeURIComponent('{company}')+'&t=0'", session_id=sid)
import time; time.sleep(4)

# 3. 读渲染后DOM, 正则提取
body = cdp('Runtime.evaluate', expression="document.body.innerText", session_id=sid).get('result',{}).get('value','')
idx = body.find('为你找到')  # 搜不到则 idx<0
# 提取: 注册资本/开业|注销|存续/国有|私营/法定代表人/成立时间/地址/电话
```

提取正则：
- 注册资本: `注册资本[：:]\s*([\d,\.]+)\s*万`
- 存续: section[:300]内含'开业'→开业 / '注销'→注销 / '存续'→存续
- 国企: '国有'或'央企' in section[:300] → 国有, 否则私营
- 法人/成立/地址/电话同理

### 阶段4: 官网内容实测(产品/设备/语言) + 美化交付
**不要信任 subagent 自报的 has_english_site**(实测大量误标: MIC英文店铺页、纯中文站都被标true)。父进程用 skill 自带 `scripts/verify.py` 对独立官网做内容实测, 三重判定(产品/设备/语言), 一举替代旧的 curl 信号法:

```bash
# 输入: [{"name","website",...}] 数组; 配置: 品类关键词YAML(见 templates/keywords.yaml)
python scripts/verify.py --input <名单.json> --config templates/keywords.yaml --out <输出目录> --xlsx
```

- 输出: `verify_result.json`(全字段) + `verify_result.md`(🟢🟡⚪表格) + `verify_result.xlsx`
- 判定字段: has_product / has_equipment / is_manufacturer / language(英文/多语/中文/未知) + en_path
- en_status 六档: 已验证英文版 / 多语官网 / 纯中文官网 / 官网无法访问 / 无官网 / SaaS模板(MIC子域、cnal.com、1688.com、gys.cn等平台店铺页直接跳过不重试)
- 判定规则、阈值、信号表: `references/website-content-verification.md`
- 工具本体也落在 `制造商爬虫\.worktrees\website-content-verification\verify.py` 与 `pipeline/scripts/verify.py`, 技能 scripts/verify.py 与它们同源保持一致
- 排序: 已验证英文版(浅绿) → MIC子域(浅黄) → 仅中文, 组内注册资金降序
- 交付表加"英文官网状态"列(en_status), 英文版URL记入notes
- **is_manufacturer 判阴性不可全信**: 大量真实厂家官网只列产品不列设备(管材/钢管/结构件类尤甚), 设备词天然低命中——实测 73 家管线钢管候选只判出 11 家制造商。is_manufacturer=否/疑似 ≠ 不是制造商。交叉证据链: 资质渠道采到的 API 5L 会标/压力管道(A级)制造许可 + 工商经营范围含"制造/生产" → 即可认定有产能, 这类企业在交付表标"设备未在官网展示, 资质待核实", 不要直接剔除
- **设备强命中要按品类解读产能类型**: 穿孔机/轧管机/皮尔格=真无缝管产能(区别于焊管), 防腐生产线/3LPE涂覆线=涂覆配套能力; 只有产品命中而无任何设备命中 → 必须回资质证书或工商经营范围确认, 不能凭官网判死


**Excel美化模板**(openpyxl): 深蓝表头(1F4E79)+微软雅黑+细边框+冻结表头+auto_filter+颜色分组+标题合并行

### 阶段6: 多模块整合成主流水线(仓库组织)
当采集/清洗/官网验证/工商核验已各自沉淀为独立模块(git worktree 或目录)而用户要求"整合成一套工作流程"时, 建一条主流水线骨架而非就地散跑:

- 主入口放仓库根 `pipeline/`(README 总览图 + WORKFLOW 手册 + `scripts/` + `sources/`), 各阶段脚本从原 worktree 拷入 `pipeline/scripts/`, 品类关键词/黑名单/YAML 拷入 `pipeline/sources/`
- **阶段间用统一 JSON 字段契约在 `data/<品类>/` 接力**: 阶段产物文件名固定(`<channel>.json`→`_clean.json`→`verify_result.json`→`_tyc.json`), finalize 按企业名 join 三份数据。字段名跨模块保持一致(name/website/en_status/regCapital 等), 这样每阶段可独立替换实现而不动契约
- **整合前必须逐个读每个模块的 WORKFLOW.md + README.md + git log + 关键脚本**: 凭 README 标题就动手会把已剔除的功能塞回模块(information-channel 的 git log 显示已移除核验只留发现); 判断某接口'失效'前必须用**该模块自己的入口脚本**复测(tyc_batch.py 的假 token 报302004 ≠ tyc_verify.py 失效), 别急着宣布不可用
- finalize 的 join 用**规范化企业名**(去括号别名 `re.sub(r"[（(].*?[）)]","",s)`)做键, 兼容采集名与工商匹配名的差异; 工商未命中的相关列留空, 不阻塞其他列
- 整合后必须**用真实历史数据端到端验证一遍**(把某品类现成的 `_clean.json`+工商结果拷进 data/ 跑 finalize), 确认列/排序/join 都对再交付, 不要只交骨架

**交付表文件命名规则（用户明确要求）**: finalize 输出固定为 `<品类>产品制造商候选名单.xlsx` 和同名 `.md`（不是"制造商_验证结果"）——文件名由品类目录名自动生成，换品类无需改脚本

**交付前自查清单**: ①表格无重复企业(见阶段2企业名二级去重) ②官网列带超链接 ③文件名=`<品类>产品制造商候选名单` ④黑名单国企/上市已排除 ⑤注销企业在存续列标出(投标资格须排除)

**整合版输出表格列**(用户常用): 序号 | 企业名称 | 主营产品 | 是否有英文官网 | 官网 | 存续状态 | 注册资金 | 企业性质 | 成立日期 | 信息渠道。是否有英文官网由 en_status 映射(已验证英文版/多语官网→是, 纯中文→否, 平台店铺页→否(店铺页), 无法访问→待核实)

**官网列必须做成 Excel 可点击超链接**(用户明确要求, 每次交付都做): finalize 写 xlsx 时对官网单元格设 `cell.hyperlink`, 显示文本保持裸域名, 链接自动补 `https://` 前缀(值含 `://` 则不补), 字体蓝色下划线(0563C1); 值为 `—`(无官网)不加链接。

## Pitfalls (血泪教训)

- **爱企查CDP验证已不可靠**: 爱企查现在检测浏览器实例本身的--remote-debugging-port参数, 即使用户手动打开的页面也提示"请关闭调试端口再试", CDP附加+location.href导航那条路实际走不通。**工商验证默认用天眼查 tyc_verify.py(无登录无浏览器门槛, 命中率82%), 其次企查查移动API, 爱企查CDP仅理论末选**, 不要为它反复折腾调试端口。
- **企查查移动API必须走web_extract**: Keenable出口IP能过其风控; execute_code内核有hermes_tools可用, 但Python313独立进程既无hermes_tools、requests直连也被反爬返回空——批量验证只能在execute_code里分批跑(15-20家/批, 每家居即json.dump落盘断点续跑), 不能写成Python313后台常驻脚本
- **天眼查 API 失效误判的坑**: 用 tyc_batch.py 的抓包假 token(`X_AUTH_TOKEN="eyJkaX...Mjd9"`) + 0.8秒间隔会返回 `302004 请登录`(HTTP 200 但 companyCount=None), 误以为接口失效。改用 tyc_verify.py 的 `x-auth-token: "***"` 占位 + 3秒间隔即恢复。判定'失效'前先用 tyc_verify.py 的确切请求头复测, 别急着切备选方案
- **delegate_task 采集 subagent 可能整机失败却自报完成**: 症状是完成报告写'无前序数据/目录不可访问'而另几个同目录 subagent 却写盘成功。批量结果回来后先 `ls data/<品类>/` 逐个核对 JSON 实际落盘条数, **以落盘文件为准而非 subagent 自报的 candidates_count**; 失败渠道立即重派, goal 里明确'立即开始工作, 不要等待任何前序数据——这是独立任务'
- **中途调配额用 steer 不必停掉重派**: delegate_task(action='steer', subagent_id, message) 把新目标注入运行中的 subagent(下一工具结果处生效), 如用户要求'每渠道30家'
- **delegate_task 的 goal 含嵌套引号会导致 tasks JSON 解析失败**(报 Expecting ':' delimiter): goal 用简单句式避免复杂转义, 失败就用更短的目标描述重发
- **渠道数据陆续到齐时每批重跑全链**: aggregate 的域名去重跨渠道生效, verify/tyc 全量重跑会干净覆盖旧结果(按企业名 join 不受影响), 只跑新增企业会导致 finalize 的 join 缺行。新渠道到达后顺序: aggregate(全量)→verify(全量)→tyc(全量)→finalize
- **finalize 写 xlsx 报 PermissionError/Device or resource busy = 目标 xlsx 正被 Excel 打开占用**: 不要 rm -f(同样报 busy), 换临时文件名验证逻辑或让用户关掉 Excel 再重跑
- **gsxt官网直爬是死路**: 真实浏览器实测打开即返回"Environment Checking"环境检测页(加速乐反爬), 与所有开源gsxt爬虫在极验4.0后失效的事实一致; 官方一手数据只能人工浏览器或商业API, 不要再投入逆向。
- **本机 terminal curl 探测不可信**: 该主机终端流量被代理拦截(全域名 curl 写入报错), 可达性探测改用 execute_code 内核的 urllib 请求(走 Keenable 出口)或 browser_exec; 反爬行为(如环境检测页)只有真实浏览器能观察到。
- **静默批量实测是默认工作方式**: 用户要求"逐个测试所有方案"时期望不逐步确认、跑完一次性汇总成对比表; 引用的文件路径不存在时先 search_files 定位实际文件, 以最匹配者继续并在报告里说明, 不要中断询问。
- **MCP/Agent 路径需 token 且未实测**: agent.qcc.com 的 MCP 端点握手正常但无 token 返回 401(明确要求 Bearer); zhanglunet/qcc 开源封装文档声明支持 Hermes 接入; 仅在拿到 QCC_API_KEY 后作为自动化升级路径实测, 未持 token 不要宣称可用。
- **工商验证命中率约43%属正常**: 企查查搜索接口对新注册/名称有差异/被风控的企业返回空或结构异常(搜到N家但注册资本抽不到), 未命中的标"待验证"交付, 用户可对入围企业手动补查, 不要为凑全量反复重试拖垮整批
- **新标签页会被爱企查检测**: 不要用 new_tab/goto_url 开新页，必须在用户手动打开的 aiqicha 页面的 session 里用 location.href
- **搜索词**: 用完整中文公司名(含'有限公司')，去掉后缀反而匹配不到；英文名搜不到转中文名
- **ensure_real_tab 会连错标签页**(常连到about:blank或子代理遗留页)，必须用 Target.attachToTarget 显式附加到 aiqicha tab
- **MIC(中国制造网)搜索页是JS渲染**: web_extract只能读静态部分,用 browser_exec 抓 company-search 供应商列表再逐个抓详情
- **微信生态是发现渠道而非核验渠道**: 搜狗微信搜索实测可搜、无验证码, 行业公众号的"国网中标企业汇总榜"/"专精特新推荐"一次查询即可成批提取企业名(实测"绝缘子厂家 公司"→10条真实企业名单)。但它给的是第三方转载信息, 拿到企业名仍需回搜索引擎找独立官网, 不能当作企业信息的权威来源; 搜狗有 antispider 需控频。
- **反爬强平台(抖音等)不要凭"免登走不通"下不可用结论, 也不要在免登上死磕**: 直接请求搜索接口返回 status_code 2483(需登录) 或 verify_check 风控, 但这不代表渠道不可用——借"签名算法内置"的开源项目 + 登录 cookie 即可采集。接入流程、cookie 提取、风控处理见 `references/platform-scraper-integration.md`。
- **ImportYeti 已放弃并实测确认**: 搜索只接受单词(空格→422)、返回的是美国进口商(consignee)不是中国供应商、搜索25页后Cloudflare拦截、官方API需key(401)、直接访问已实测返回403。要海关数据用 UN Comtrade。
- **搭建渠道仓库类'建立信息渠道'请求时, 默认先建骨架不启动爬取**: 用户取消澄清提问时按最稳妥默认执行(可复用代码/模板/规则+空数据目录, commit), 不要因范围不清而卡住不动手。骨架落在 `制造商爬虫\.worktrees\information-channel\`(git worktree, 分支同名; 该仓库无user identity, 首次commit前先 `git config user.name "Karl HE" && git config user.email karl.he@cgcv-valve.com.cn`)。品类选定后再按阶段1开跑。
- **展会官网大量不可达(000)**: 直接用Bing搜'XX展 展商名录'提取企业名
- **排除大型要按品类定制黑名单**: 铝=凤铝/坚美/华建/忠旺,阀门=需另列,别一刀切
- **爱企查数据偶尔抽不全(?万/?状态)**: 页面加载慢,可对个别重试或标记待人工复核,不要卡住整批
- **不要信任 subagent 自报的 has_english_site**: 实测把MIC英文店铺页和纯中文官网都标了true。汇总时必须由父进程重新验证——用 `scripts/verify.py` 做内容实测(含语言入口实测), 用 en_status 覆盖原始标记; 单纯的 HTML 字符串信号('english' in html / '/en' / lang="en")会把 SaaS 模板站注入的英文语言包误判成英文站。
- **hreflang="en"/lang="en" 不等于有英文站**: yybcdn 类 SaaS 模板站(cnal.com/1688子页等)会注入英文语言包 JS(`var adviceLanguages='en'`), 信号全中但全站无 EN 入口、内容纯中文——必须对 EN 入口 URL 做内容实测, 只看 HTML 信号必误判。
- **单一 latin_ratio>0.6 阈值会漏判混合站**: 如 en.aluhf.com 主文中文但导航/产品名全英文, 英文占比低却被判中文。补充判定: 含CJK且英文词数(≥3字母)≥200且命中英文内容词探针(product/about us/certificate/aluminum/extrusion/manufacturer/factory/equipment)→认英文。
- **语言切换链接本身是线索**: 解析全部 `<a>` 的 label→href(不只匹配 href="/en" 字面量); 导航出现"简体中文→cn.xxx.com"说明当前站即英文版, 反过来"English→/en/"入口 404 则无英文站。
- **设备关键词必须与规格数字共现才算强命中**: "引进德国先进设备/自动化生产线"是营销话术; 要求设备词 200 字符窗口内出现 `\d+(台|条|套|吨|T|MN|mm)` 才记 strong。
- **产品形态负向词防误判**: 品类配置 product_forms.negative(如铝型材/门窗型材)只命中而产品词未命中→has_product=无; 两者都命中→强降弱。
- **openpyxl 的 Border 用关键字参数不用位置参数**: 旧写法 `Border(*[Side(...)]*4)` 在新版 openpyxl 类型检查报 ArgumentType 错(diagonalUp/diagonalDown/outline 位置不匹配), 运行时虽不炸但应写 `Border(left=Side(...),right=Side(...),top=Side(...),bottom=Side(...))`。`ws.active`/`ws.cell` 的 Pyright "None" 告警是可选返回值误报, 运行时正常, 不用管
- **天眼查小程序 API 用 tyc_verify.py 的正确配置实测可用(2026-10)**: 关键在 `x-auth-token` 用 `***` 占位(不是抓来的假 token) + **请求间隔 3.0 秒** + 命中逻辑里 companyCount=None 时退避重试。实测 `山东汇丰铝业` 返回完整数据(600万人民币/存续/私营), 前3家 3/3 全命中。**这是当前最可靠的工商核验路径**(无需登录/无浏览器门槛), 优先于企查查移动API(命中率仅43%)。工具本体 `scripts/tyc_verify.py`(技能自带, 与制造商爬虫/pipeline/scripts/ 同源), 输出文件名=输入stem+`_tyc`(所以输入名单要命名为`<品类>.json`才能让 finalize 找到`<品类>_tyc.json`)
- **YAML 关键词是 list-of-lists**: product_keywords/equipment_keywords 每组内多词, 匹配前必须先 flatten, 否则对 list 调 .lower() 报 AttributeError。
- **PyYAML 不在 hermes venv**: verify.py 用 `C:\Users\gogoo\AppData\Local\Programs\Python\Python313\python.exe` 跑(hermes venv 的 python 无 yaml), PYTHONPATH 清空。
- **MIC子域名(en.made-in-china.com)不是独立官网**: 是平台店铺页, 不能当官网交付; 必须找企业独立域名, 找不到的标"待核实"并在爱企查验证前剔除。
- **英文公司名必须先转中文全称**: 爱企查验证只认中文名; 英文/拼音名直接搜会0结果。解析途径: 官网About、百度搜索英文名+地名、MIC详情页中文标注。
- **发现/核验/英文站/产品形态/海关各自独立成模块**: 渠道清单(CHANNELS.md)只列发现渠道与发现期采集要求(中文名/独立官网/排除境外); 英文站验证归阶段4 verify.py, 产品形态过滤归阶段2, 工商核验归阶段3, 海关背景数据是独立模块。被要求增删'通用采集要求'或渠道类别时按此边界拆分, 不要把别的模块的要求塞进发现清单, 反之亦然。
- **write_file 拒覆盖曾分页读取过的文件**: 本会话以 offset/limit 读过某文件后, 即使随后整文件重读, write_file 仍报 stale_write_blocked; 小改就用 patch(不受此限), 要整体替换先 terminal rm 再 write_file——同一调用重试不会生效, 别在它上面循环。
- **反爬平台的采集必须复用开源项目自带的签名实现, 不要手搓端点**: 手写 curl_cffi 请求抖音搜索接口即使带有效登录 cookie 也返回空(status_code 0 + search_nil_info.verify_check)或 2483 需登录——平台要求 a_bogus/X-Bogus 签名。项目自带的接口类(如 DouK-Downloader 的 `src/interface/search.py` Search)已内置签名算法, 首次调用即返回真实数据。选项目优先挑"加密参数算法内置/仍在维护"的仓库。
- **OneDrive 路径下 curl_cffi 读不到 certifi 证书**(报 curl (77) error adding trust anchors): 证书文件存在但 libcurl 无法从同步目录加载 CAfile。把 `.venv/Lib/site-packages/certifi/cacert.pem` 复制到本地 scratch, 用 `SSL_CERT_FILE=<本地路径>` 环境变量启动; 设 SSL_CERT_FILE 指向 OneDrive 内路径无效。
- **Chrome v130+ 起 cookie 库启用 appbound encryption, 非管理员进程无法解密**: 直读 Cookies 库(被运行中的 Chrome 锁文件)、rookiepy、VSS 卷影复制全部失败。正确路径是 `browser_exec(local=True)` 开真实浏览器让用户登录, 再 `cdp('Network.getAllCookies')` 读取——`document.cookie` 拿不到 HttpOnly 的 sessionid。
- **本地 Chrome 的 CDP WebSocket 拒绝脚本 origin**(handshake 403, 提示需 --remote-allow-origins): 带 Origin/chrome:// 头都过不了白名单。重启带该参数的 Chrome 会丢用户已开标签页与登录态, 属不可逆操作须先问用户; 读 cookie 走 browser_exec 的 CDP 封装而不是自己建 websocket。
- **调用大型开源项目的 API 类前先按它的真实签名构造依赖**: 典型如 Parameter(settings, cookie_object, logger=BaseLogger类而非实例, console=ColorfulConsole(), **settings.read(), recorder=None)——cookie 由 settings.read() 提供, 显式再传会报 multiple values; 用 logging.Logger 实例会报 not callable。构造参数逐个报错时按 traceback 逐项对齐, 不要猜。
- **平台搜索结果可能被包成嵌套 list**: 同一接口 `run(single_page=True)` 有时返回 `[...]` 有时 `[[...]]`, 解析前先 `if page and isinstance(page[0], list): page = page[0]`; 项目自带的分页 batch 模式对部分 channel 返回空、offset 翻页需首次响应里的 search_id——拿不到 search_id 时用 single_page 逐页手动翻, 并设 seen 集合去重。
- **平台账号级搜索风控会误判为代码问题**: 首次请求成功、连续测试后返回空但不报错(底层 search_nil_type=verify_check), cookie 与登录态均正常。冷却 60-120s 不恢复, 需数小时或降低频率。发现"首次可用→复测全空"时先按风控处理, 停止重复请求(会加重), 不要在参数上反复试。
## References

- `references/discovery-channels.md` — 厂商发现渠道全景(发现模块范围, 实测可达性+坑)
- `references/verification-channels.md` — 工商核验渠道全景(官方/网页/MCP/开放API、凭证门槛、实测状态、开源项目结论、无凭证MCP探测法)
- `references/website-content-verification.md` — 官网内容实测(产品/设备/语言)判定规则、阈值与信号表
- `scripts/aggregate.py` — 清洗去重(域名+企业名二级去重, 含黑名单/形态过滤)
- `scripts/verify.py` — 官网内容验证器(输入名单+品类关键词YAML→JSON/MD/XLSX)
- `scripts/tyc_verify.py` — 工商核验器(天眼查, 输入名单json/xlsx→_tyc.json+_tyc.xlsx, 3秒间隔)
- `scripts/qcc_verify.py` — 工商核验备选(企查查移动API, execute_code内核分批跑,断点续跑)
- `scripts/finalize.py` — 汇总+美化Excel(官网列超链接, 输出`<品类>产品制造商候选名单`)
- `templates/keywords.yaml` — 品类关键词配置模板(铝管已填示例)

## 交付物惯例

- **工作根目录**: `E:\OneDrive\00.其他必要事务\制造商爬虫\`（所有代码/中间数据/成果物都在此，不再用 scratch）
- 每个品类建子目录: `<NN>.<品类>\`（如 `01.铝管铝型材\`）
- **渠道仓库(git worktree)**: `制造商爬虫\.worktrees\information-channel\` — 放可复用渠道骨架(CHANNELS.md发现渠道清单/WORKFLOW.md/templates/scripts), 用户要求"建立信息渠道"时默认先在此建骨架提交, 不启动爬取
- 可复用脚本(skill自带, 与制造商爬虫/pipeline/scripts/ 同源, 端到端验证过): `scripts/aggregate.py`(清洗去重, 含域名+企业名二级去重) + `scripts/verify.py`(官网内容验证, 需PyYAML, 用Python313跑) + `scripts/tyc_verify.py`(工商核验首选, 天眼查, 后台跑, 3秒间隔) / `scripts/qcc_verify.py`(备选, execute_code内核分批跑,断点续跑) + `scripts/finalize.py`(汇总+美化Excel, 官网列带超链接, 输出`<品类>产品制造商候选名单.xlsx/.md`)，从 skill 目录调用，产物写品类子目录
- 美化 Excel: `<品类>产品制造商候选名单.xlsx`
- Markdown报告: `<品类>产品制造商候选名单.md`(🟢🟡⚪图例分档)
- 字段: 企业名称/产品类别/注册资金/存续状态/企业性质/英文官网状态/官网/地址/联系人(法人)/电话/信息渠道
