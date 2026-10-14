# 端到端操作手册

## 阶段 1：4 渠道并行爬取候选池

用 delegate_task 并行 spawn 4 个 subagent（每个产 ≥30 家，JSON 统一格式），渠道见 `CHANNELS.md`。

每个 subagent 写 JSON 到 `data/<品类>/<channel>.json`：

```json
{
  "channel": "",
  "candidates": [
    {
      "name": "中文公司全称（爱企查验证依赖它）",
      "website": "独立官网（非MIC子域）",
      "address": "",
      "products": "写清产品形态（铝管 vs 型材）",
      "source_url": "",
      "has_english_site": false,
      "confidence": "",
      "notes": "英文名/渠道备注放这里"
    }
  ]
}
```

必守规则见 `CHANNELS.md`「通用采集要求」。

## 阶段 2：清洗去重

```bash
BIG_BLACKLIST="凤铝|坚美|忠旺" python scripts/aggregate.py "data/<品类>"
```

- 按官网域名去重（最可靠），同域名保留信息最全的
- 排除：无官网+产品笼统的贸易商、黑名单大型企业、境外企业
- 产品形态过滤（用户指定形态时）：按 products 字段过滤
- 产物：`_clean.json` + 剔除 MIC 店铺页/名称待核实项后的待验证名单

## 阶段 3：爱企查逐个验证（核心技术）

### 前置 0 — CDP 调试端口

browser_exec 通过 `http://127.0.0.1:9222/json/list` 连本地 Chrome。该端口**跨 turn 会断**（症状：`BU_CDP_URL unreachable / WinError 10061`）。恢复：

1. `curl -s http://127.0.0.1:9222/json/version` 和 `netstat -ano | grep 9222` 确认真断了（空返回=断）
2. 让用户**完全关闭所有 Chrome**（任务管理器确认无 chrome.exe 残留）
3. 用**默认用户数据目录**启动（保住登录态）：
   `terminal(command='"C:/Program Files/Google/Chrome/Application/chrome.exe" --remote-debugging-port=9222', background=True)`
4. `sleep 5` 后 curl 验证 `/json/version` 有返回
5. 再让用户在**这个** Chrome 里打开 aiqicha.baidu.com 并登录

> **绝不能用独立 `--user-data-dir`**：那样启动的 Chrome 无登录 cookie，打开爱企查要重登，白干。

### 前置 1

用户必须在 Chrome 手动打开 aiqicha.baidu.com 并登录，验证队列准备好后提示用户这一步。

### 验证机制（唯一可行路径）

```python
import urllib.request, json, time
tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/list"))
aiq = [t for t in tabs if t.get('type')=='page' and 'aiqicha.baidu.com' in t.get('url','')]
attach = cdp('Target.attachToTarget', targetId=aiq[0]['id'], flatten=True)
sid = attach['sessionId']

for company in companies:
    # 每家: 用 location.href 导航（不能用 CDP Page.navigate — 触发反爬0结果）
    cdp('Runtime.evaluate', expression=f"location.href='/s?q='+encodeURIComponent('{company}')+'&t=0'", session_id=sid)
    time.sleep(4)
    body = cdp('Runtime.evaluate', expression="document.body.innerText", session_id=sid).get('result',{}).get('value','')
    idx = body.find('为你找到')   # 搜不到则 idx<0
    # 提取: 注册资本 / 开业|注销|存续 / 国有|私营 / 法人 / 成立时间 / 地址 / 电话
```

提取正则：

- 注册资本：`注册资本[：:]\s*([\d,\.]+)\s*万`
- 存续：section[:300] 含'开业'→开业 / '注销'→注销 / '存续'→存续
- 国企：'国有'或'央企' in section[:300] → 国有，否则私营
- 法人/成立/地址/电话同理

## 阶段 4：英文官网实际验证 + 美化交付

**不要信任 subagent 自报的 has_english_site**（实测大量误标）。父进程汇总时用 curl 独立域名重新验证：

```python
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
for v in candidates:
    url = v.get('website','')
    if 'made-in-china.com' in url:
        v['en_status'] = 'MIC英文店铺页'          # 降级，不算独立英文官网
    else:
        try:
            html = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'}), timeout=8, context=ctx).read(3000).decode('utf-8','ignore').lower()
            v['en_status'] = '已验证英文版' if ('english' in html or '/en' in html or 'lang="en"' in html) else '纯中文官网'
        except Exception:
            v['en_status'] = '官网无法访问'
    v['has_english_site'] = (v['en_status'] == '已验证英文版')   # 以验证结果覆盖原始标记
```

en_status 五档：已验证英文版 / MIC英文店铺页 / 纯中文官网 / 官网无法访问 / 未验证。
排序：已验证英文版（浅绿）→ MIC子域（浅黄）→ 仅中文，组内注册资金降序。

## 交付物

```bash
python scripts/finalize.py "data/<品类>"
```

- `制造商_验证结果.xlsx`（美化：深蓝表头+微软雅黑+冻结+auto_filter+颜色分组）
- `制造商_报告.md`（🟢🟡⚪ 图例分档，模板见 `templates/report.md`）
