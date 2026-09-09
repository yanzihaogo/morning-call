import os
import requests
import json
import re
import time
import smtplib
import sys
import unicodedata
import html as html_lib
import concurrent.futures
from google import genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid
from datetime import datetime, timedelta, timezone

def log(message):
    bj_time = datetime.now(timezone(timedelta(hours=8))).strftime('%H:%M:%S')
    print(f"[{bj_time}] [🚀 MoE 双核系统] {message}")
    sys.stdout.flush()

# ==========================================
# 1. 统一配置中心 (Coze + Gemini 双擎)
# ==========================================
coze_token = os.getenv('COZE_API_TOKEN', '').strip()
coze_bot_id = os.getenv('COZE_BOT_ID', '').strip()
gemini_api_key = os.getenv('GOOGLE_API_KEY', '').strip()

smtp_server = os.getenv('SMTP_SERVER', '').strip()
smtp_port = int(os.getenv('SMTP_PORT', '465'))
sender_email = os.getenv('SENDER_EMAIL', '').strip()
sender_password = os.getenv('SENDER_PASSWORD', '').strip()
receiver_email = os.getenv('RECEIVER_EMAIL', '779825335@qq.com').strip()
cc_email = os.getenv('CC_EMAIL', '15757699818@163.com').strip()

# 可选：设置一张 HTTPS 顶部横幅图；未设置时使用兼容性更好的渐变色标题区。
hero_image_url = os.getenv('EMAIL_HERO_IMAGE_URL', '').strip()

# 模型名改为可配置，避免代码内写死不存在或已下线的版本。
gemini_model = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash').strip()
gemini_fallback_model = os.getenv('GEMINI_FALLBACK_MODEL', '').strip()

REQUEST_TIMEOUT = (15, 60)
ALLOWED_TREND_COLORS = {'#ef4444', '#10b981', '#f97316'}
EXPECTED_STOCKS = {
    '多氟多': {'name': '多氟多', 'ticker': '002407.SZ'},
    '华虹宏力': {'name': '华虹公司', 'ticker': '688347.SH'},
    '华虹公司': {'name': '华虹公司', 'ticker': '688347.SH'},
    '华虹半导体': {'name': '华虹公司', 'ticker': '688347.SH'},
    '中信证券': {'name': '中信证券', 'ticker': '600030.SH'},
}

tz_bj = timezone(timedelta(hours=8))
now_bj = datetime.now(tz_bj)
today_str = now_bj.strftime('%Y年%m月%d日')

gemini_client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None

# ==========================================
# 2. 账本系统 (防重复记录)
# ==========================================
HISTORY_FILE = os.getenv('HISTORY_FILE', 'news_history.txt').strip()
def get_past_news():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def save_new_history(domestic_data):
    if not domestic_data: return
    new_titles = [item.get('title') for item in domestic_data.get('sector_news', []) if item.get('title')]
    if not new_titles: return
    
    lines = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
    lines.extend(new_titles)
    lines = lines[-100:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        for l in lines: f.write(l + "\n")

past_news_list = get_past_news()


def extract_json(text):
    """尽量从模型返回内容中提取 JSON，但绝不用字符串猜测填补数据。"""
    if not text:
        raise ValueError('模型返回为空')
    normalized = unicodedata.normalize('NFKC', str(text)).strip()
    normalized = re.sub(r'^```(?:json)?\s*|\s*```$', '', normalized, flags=re.I | re.S).strip()
    start, end = normalized.find('{'), normalized.rfind('}')
    if start < 0 or end <= start:
        raise ValueError('模型返回中未找到完整 JSON 对象')
    return json.loads(normalized[start:end + 1])


def clean_string(value, max_length=2000):
    """限制模型字段的类型和长度，避免异常内容撑爆邮件。"""
    if value is None:
        return ''
    return str(value).strip()[:max_length]


def clean_string_list(value, limit=3, item_length=300):
    if not isinstance(value, list):
        return []
    return [clean_string(item, item_length) for item in value[:limit] if clean_string(item, item_length)]


def normalize_domestic_data(data):
    """只允许固定三只 A 股进入邮件，并为每条信息保留数据可验证状态。"""
    if not isinstance(data, dict):
        return {}

    sector_news = []
    for item in data.get('sector_news', [])[:4]:
        if not isinstance(item, dict):
            continue
        title = clean_string(item.get('title'), 120)
        summary = clean_string(item.get('summary'), 800)
        if title and summary:
            sector_news.append({'title': title, 'summary': summary})

    normalized_by_ticker = {}
    for stock in data.get('focus_stocks', []):
        if not isinstance(stock, dict):
            continue
        raw_name = clean_string(stock.get('name'), 30)
        expected = next((v for alias, v in EXPECTED_STOCKS.items() if alias in raw_name), None)
        if not expected:
            continue
        color = clean_string(stock.get('valuation_color'), 10).lower()
        if color not in ALLOWED_TREND_COLORS:
            color = '#f97316'
        ticker = expected['ticker']
        normalized_by_ticker[ticker] = {
            'name': expected['name'],
            'ticker': ticker,
            'trend_signal': clean_string(stock.get('trend_signal'), 40) or '信息待核验',
            'price_info': clean_string(stock.get('price_info'), 350) or '未取得可验证行情，不展示具体价位',
            'key_levels': clean_string(stock.get('key_levels'), 600),
            'highlights': clean_string_list(stock.get('highlights'), 3, 260),
            'risks': clean_string_list(stock.get('risks'), 3, 260),
            'valuation_color': color,
            'verification_status': clean_string(stock.get('verification_status'), 30) or '待核验',
            'data_as_of': clean_string(stock.get('data_as_of'), 50),
            'source': clean_string(stock.get('source'), 180),
            'search_keyword': clean_string(stock.get('search_keyword'), 180),
        }

    ordered_stocks = [
        normalized_by_ticker[ticker]
        for ticker in ('002407.SZ', '688347.SH', '600030.SH')
        if ticker in normalized_by_ticker
    ]
    return {'sector_news': sector_news, 'focus_stocks': ordered_stocks}


def normalize_gemini_data(data):
    if not isinstance(data, dict):
        return {}
    result = dict(data)
    result['global_news_flash'] = [x for x in data.get('global_news_flash', [])[:6] if isinstance(x, dict)]
    result['medical_news'] = [x for x in data.get('medical_news', [])[:2] if isinstance(x, dict)]
    if not isinstance(data.get('science_concept'), dict):
        result['science_concept'] = {}
    result['romantic_quote'] = clean_string(data.get('romantic_quote'), 120)
    return result


def e(value):
    """所有 AI 内容在写入 HTML 前转义，避免破坏排版或注入标签。"""
    return html_lib.escape(clean_string(value), quote=True)


def safe_url(value):
    url = clean_string(value, 500)
    return html_lib.escape(url, quote=True) if re.match(r'^https://[^\s]+$', url, flags=re.I) else ''

# ==========================================
# 3. 双核 Prompt 指令集
# ==========================================
COZE_PROMPT = f"""
今天是 {today_str}。请执行 A 股重点行业与三大核心标的的精准深度研判。
🚨【历史已报过滤】：{past_news_list}

【执行要求】：
1. 🏭【行业精要】（2-3条）：聚焦国内半导体晶圆制造、新能源新材料、资本市场改革与大金融政策传导。
2. 🎯【核心标的追踪】：严格仅追踪以下三只 A 股，名称和代码不可混淆：
   【多氟多 002407.SZ】、【华虹公司 688347.SH】、【中信证券 600030.SH】。
   - 【标的1：多氟多】：深入分析六氟磷酸锂价格周期、电子级氟化氢/氢氟酸产能扩张、储能及钠电新材料业务兑现度与量价博弈。
   - 【标的2：华虹公司 688347.SH】：深入分析特色工艺晶圆代工产能利用率、功率器件/MCU/CIS汽车电子需求、12英寸晶圆厂扩产进度与PB估值修复空间。不得混用港股华虹半导体 01347.HK 的价格或估值。
   - 【标的3：中信证券】：深入分析全市场成交量中枢、券商并购重组预期、资本市场逆周期调节政策弹性、机构业务与财富管理估值中枢。
   - 只有在来源、日期和证券代码均可核验时，才允许输出具体价格、涨跌幅、PE/PB或技术区间。
   - 如果无法取得可验证行情，必须明确写“未取得可验证行情”，只做不含具体数字的定性分析；严禁猜测、补全或把其他证券的数据移植过来。
   - 每只股票必须给出数据截止时间、信息来源或精确搜索关键词，并标记“已核验/部分核验/待核验”。
   - 采用[投资亮点]与[风险因素]双边对抗评估模式。
   - 输出趋势颜色：看多/低位输出 #ef4444，看空/高位输出 #10b981，震荡输出 #f97316。

🚨【强制以纯 JSON 格式返回】：
{{
    "sector_news": [{{ "title": "行业动态标题", "summary": "详尽逻辑摘要" }}],
    "focus_stocks": [
        {{ 
            "name": "多氟多", 
            "ticker": "002407.SZ",
            "trend_signal": "极简趋势状态(如: 触底反弹 / 估值筑底 / 震荡蓄势)", 
            "price_info": "仅写可核验的估值中枢与关键区间；不可核验时写未取得可验证行情", 
            "key_levels": "盘面博弈与筹码结构逻辑分析", 
            "highlights": ["亮点1", "亮点2"], 
            "risks": ["风险1", "风险2"], 
            "valuation_color": "必须为 #ef4444 或 #10b981 或 #f97316",
            "verification_status": "已核验/部分核验/待核验",
            "data_as_of": "数据截止日期时间",
            "source": "来源名称与页面标题；无可靠来源则留空",
            "search_keyword": "用于复核的精确搜索关键词"
        }},
        {{ 
            "name": "华虹公司", 
            "ticker": "688347.SH",
            "trend_signal": "极简趋势状态(如: 产能饱满 / 周期回暖 / 估值修复)", 
            "price_info": "估值中枢与关键区间(如: 核心支撑区间 / PB估值分位)", 
            "key_levels": "盘面博弈与筹码结构逻辑分析", 
            "highlights": ["亮点1", "亮点2"], 
            "risks": ["风险1", "风险2"], 
            "valuation_color": "必须为 #ef4444 或 #10b981 或 #f97316",
            "verification_status": "已核验/部分核验/待核验",
            "data_as_of": "数据截止日期时间",
            "source": "来源名称与页面标题；无可靠来源则留空",
            "search_keyword": "用于复核的精确搜索关键词"
        }},
        {{ 
            "name": "中信证券", 
            "ticker": "600030.SH",
            "trend_signal": "极简趋势状态(如: 头部溢价 / 政策共振 / 高位震荡)", 
            "price_info": "估值中枢与关键区间(如: PB估值中枢 / 核心平台支撑)", 
            "key_levels": "盘面博弈与筹码结构逻辑分析", 
            "highlights": ["亮点1", "亮点2"], 
            "risks": ["风险1", "风险2"], 
            "valuation_color": "必须为 #ef4444 或 #10b981 或 #f97316",
            "verification_status": "已核验/部分核验/待核验",
            "data_as_of": "数据截止日期时间",
            "source": "来源名称与页面标题；无可靠来源则留空",
            "search_keyword": "用于复核的精确搜索关键词"
        }}
    ]
}}
"""

GEMINI_PROMPT = f"""
今天是 {today_str}。请执行全球前沿探索、科学趣味发现（Fun Facts）与学术深读。
🚨【核心指令】：
1. 全局抓取 4-6 条外盘宏观或前沿科技快讯。只有确认真实存在时才提供 URL；否则 URL 留空并提供精确搜索关键词。不得虚构机构、时间和数字。
2. 精读 1-2 篇可核验的医学文献，优先提供 DOI 或 PMID；无法核验论文身份时不要输出该条。标题必须是论文项目名称，并在所有专有名词和药物后用括号附上英语原文。
3. 💡【Fun Facts 科学趣味发现】：每天随机挑选 1 个科学核心基础名词/概念。
   - 【专业底色】：用 1-2 句话给出清晰严谨的本质学术解释；
   - 【运作场景】：附带一个它在人体生理/病理、前沿实验室或现实系统中的运作机制；
   - 【趣味发现故事】：讲述它是“如何被意外发现的”科学轶事、科学家的高光顿悟时刻、奇妙事故，或者一个极具启发性、反直觉的趣味冷知识。要求文字生动有趣、引人入胜，让晨间阅读充满惊喜；
   - 【学科概率】：70% 概率为生物学、医学或先进材料学；30% 概率跨界至天文学、认知心理学、理论物理、计算机科学或经济学。
4. 严禁使用任何花体字或特殊 Unicode 数学字符。

🚨【强制以纯 JSON 格式返回】：
{{
    "global_news_flash": [
        {{
            "sector_tag": "板块分类",
            "time_location": "时间+地点",
            "entity": "发布机构(严禁模糊)",
            "summary": "硬核内容摘要",
            "published_at": "来源发布日期",
            "source_url": "真实来源URL；无法确认时留空",
            "search_keyword": "验证该新闻的精确搜索关键词",
            "verification_status": "已核验/部分核验"
        }}
    ],
    "science_concept": {{
        "term": "科学核心基础名词 (English Name)",
        "field": "所属学科领域 (如: 结构生物学 / 凝聚态物理 / 认知神经科学 / 宏观经济学)",
        "definition": "1-2句话清晰严密的本质学术解释",
        "scenario": "在人体内或科研/现实系统中的具体运作/应用场景",
        "discovery_or_fun_fact": "发现背后的趣味轶事、尤里卡顿悟瞬间或反直觉趣闻（100字左右，生动活泼）"
    }},
    "medical_news": [
        {{
            "project_title": "研究项目或论文名称 (English Title)",
            "journal_and_time": "期刊名与发表时间",
            "doi_or_pmid": "DOI或PMID；没有则留空",
            "source_url": "论文或期刊真实URL；无法确认时留空",
            "drug_name": "靶向药物通用名 (English Name)",
            "background": "痛点(专有名词需带英文)",
            "method_breakthrough": "核心技术与突破数据(带英文原文)",
            "clinical_value": "临床价值"
        }}
    ],
    "romantic_quote": "写给女朋友的早安暖心短句或浪漫情话（50字以内。不限制任何主题，风格自由、清新、诗意、温柔或风趣皆可，重点是读来让人眼前一亮、晨起拥有明媚好心情）"
}}
"""

# ==========================================
# 4. 双核调度函数
# ==========================================
def fetch_coze_data(max_attempts=3):
    if not coze_token or not coze_bot_id:
        log("⚠️ 未检测到 COZE_API_TOKEN 或 COZE_BOT_ID，跳过国内数据拉取。请检查 GitHub Secrets 配置！")
        return None

    headers = {'Authorization': f'Bearer {coze_token}', 'Content-Type': 'application/json'}
    payload = {
        "bot_id": coze_bot_id, "user_id": "quant_master", 
        "additional_messages": [{"role": "user", "content": COZE_PROMPT, "content_type": "text"}]
    }

    for attempt in range(1, max_attempts + 1):
        log(f"🇨🇳 启动国内主力引擎 Coze (尝试 {attempt}/{max_attempts})...")
        try:
            response = requests.post(
                'https://api.coze.cn/v3/chat', headers=headers, json=payload,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            res = response.json()
            if res.get('code') != 0:
                raise RuntimeError(f"Coze 发起对话失败，code={res.get('code')}, msg={res.get('msg', '')}")

            chat_id = res.get('data', {}).get('id')
            conversation_id = res.get('data', {}).get('conversation_id')
            if not chat_id or not conversation_id:
                raise ValueError('Coze 返回缺少 chat_id 或 conversation_id')

            # 单次最多等待约 120 秒，避免多次重试拖垮 GitHub Actions。
            for _ in range(24):
                retrieve = requests.get(
                    'https://api.coze.cn/v3/chat/retrieve',
                    headers=headers,
                    params={'chat_id': chat_id, 'conversation_id': conversation_id},
                    timeout=REQUEST_TIMEOUT,
                )
                retrieve.raise_for_status()
                status = retrieve.json().get('data', {}).get('status')

                if status == 'completed':
                    messages = requests.get(
                        'https://api.coze.cn/v3/chat/message/list',
                        headers=headers,
                        params={'chat_id': chat_id, 'conversation_id': conversation_id},
                        timeout=REQUEST_TIMEOUT,
                    )
                    messages.raise_for_status()
                    content = next(
                        (m.get('content') for m in messages.json().get('data', []) if m.get('type') == 'answer'),
                        ''
                    )
                    data = normalize_domestic_data(extract_json(content))
                    if not data.get('focus_stocks') and not data.get('sector_news'):
                        raise ValueError('Coze JSON 通过解析但没有可用栏目')
                    return data
                if status in {'failed', 'canceled'}:
                    raise RuntimeError(f'Coze 状态异常终止: {status}')
                time.sleep(5)

            raise TimeoutError('Coze 请求超过 120 秒')
        except Exception as exc:
            log(f"❌ Coze 第 {attempt} 次失败: {str(exc)[:500]}")
            if attempt < max_attempts:
                time.sleep(min(5 * attempt, 15))
    return None

def fetch_gemini_data():
    if not gemini_client:
        log("⚠️ 未检测到 GOOGLE_API_KEY，跳过国际数据拉取。")
        return None

    # 默认只使用明确配置的模型；可通过 GEMINI_FALLBACK_MODEL 提供一个备用版本。
    model_candidates = list(dict.fromkeys([m for m in [gemini_model, gemini_fallback_model] if m]))
    for model_id in model_candidates:
        for attempt in range(1, 3):
            log(f"🌍 正在激活国际引擎 {model_id} (尝试 {attempt}/2)...")
            try:
                chat = gemini_client.chats.create(
                    model=model_id,
                    config={"response_mime_type": "application/json"}
                )
                response = chat.send_message(GEMINI_PROMPT)
                data = normalize_gemini_data(extract_json(response.text))
                if not any([data.get('global_news_flash'), data.get('medical_news'), data.get('science_concept')]):
                    raise ValueError('Gemini JSON 中没有可用栏目')
                return data
            except Exception as exc:
                err_msg = str(exc)
                log(f"❌ Gemini {model_id} 第 {attempt} 次失败: {err_msg[:500]}")
                if attempt < 2:
                    time.sleep(15 if ('503' in err_msg or '429' in err_msg) else 5)
    return None

# ==========================================
# 5. HTML 渲染与发送
# ==========================================
def format_html(domestic_data, gemini_data):
    domestic_data = domestic_data or {}
    gemini_data = gemini_data or {}
    valid_hero = safe_url(hero_image_url)
    hero_html = (
        f'<img src="{valid_hero}" width="720" alt="每日晨报" '
        'style="display:block;width:100%;max-width:720px;height:auto;border:0;">'
        if valid_hero else ''
    )
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#f2f4f8;color:#334155;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',Arial,sans-serif;">
<div style="display:none;max-height:0;overflow:hidden;color:#f2f4f8;">{e(today_str)} 的市场、科技、医学与一封温柔早安。</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f2f4f8;">
<tr><td align="center" style="padding:22px 10px;">
<table role="presentation" width="720" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:720px;background-color:#ffffff;border:1px solid #e7eaf0;">
<tr><td>{hero_html}</td></tr>
<tr><td align="center" style="padding:34px 24px;background-color:#4338ca;background:linear-gradient(135deg,#4338ca 0%,#7c3aed 55%,#db2777 100%);color:#ffffff;">
<div style="font-size:12px;letter-spacing:2px;opacity:.88;">MORNING INTELLIGENCE LETTER</div>
<div style="font-size:26px;font-weight:700;line-height:1.35;margin-top:8px;">早安，今天也一起看见更大的世界</div>
<div style="font-size:13px;margin-top:9px;opacity:.9;">{e(today_str)} · 市场 × 科技 × 医学 × 日常浪漫</div>
</td></tr>
<tr><td style="padding:18px 24px;background-color:#fff7fb;border-bottom:1px solid #f5d7e6;font-size:12px;line-height:1.7;color:#9f335f;">
数据说明：具体价格与估值只有在证券代码、来源和日期均可核验时才展示；“待核验”内容不应作为交易依据。
</td></tr>
<tr><td style="padding:10px 24px 28px 24px;">
"""

    if gemini_data.get('global_news_flash'):
        html += '<div style="font-size:18px;font-weight:700;color:#25316d;margin:22px 0 12px;">🌍 全球前沿速览</div>'
        for news in gemini_data.get('global_news_flash', []):
            url = safe_url(news.get('source_url'))
            source_line = f'<a href="{url}" style="color:#2563eb;text-decoration:none;">查看来源</a>' if url else f'搜索：{e(news.get("search_keyword"))}'
            html += f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:10px;background-color:#f8fafc;border:1px solid #e5eaf2;">
<tr><td style="padding:14px 16px;font-size:13px;line-height:1.7;color:#334155;">
<span style="font-size:11px;color:#4338ca;background-color:#ede9fe;padding:3px 7px;">{e(news.get('sector_tag'))}</span>
<span style="color:#94a3b8;">　{e(news.get('time_location'))}</span><br>
<b style="color:#1e3a8a;">{e(news.get('entity'))}</b>　{e(news.get('summary'))}
<div style="margin-top:7px;font-size:11px;color:#64748b;">{e(news.get('published_at'))} · {e(news.get('verification_status'))} · {source_line}</div>
</td></tr></table>"""

    concept = gemini_data.get('science_concept')
    if concept:
        html += f"""
<div style="font-size:18px;font-weight:700;color:#5b217d;margin:24px 0 12px;">💡 今日科学趣闻</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#faf5ff;border:1px solid #ead7fa;">
<tr><td style="padding:17px 18px;line-height:1.7;color:#4c1d65;">
<div style="font-size:16px;font-weight:700;">{e(concept.get('term'))}</div>
<div style="font-size:11px;color:#7e22ce;margin-bottom:9px;">{e(concept.get('field'))}</div>
<div style="font-size:13px;"><b>学术释义：</b>{e(concept.get('definition'))}</div>
<div style="font-size:13px;margin-top:8px;padding:9px 11px;background-color:#ffffff;border-left:3px solid #8b5cf6;"><b>如何运作：</b>{e(concept.get('scenario'))}</div>
<div style="font-size:13px;margin-top:8px;padding:9px 11px;background-color:#fdf2f8;border-left:3px solid #db2777;"><b>有趣发现：</b>{e(concept.get('discovery_or_fun_fact'))}</div>
</td></tr></table>"""

    if domestic_data.get('sector_news'):
        html += '<div style="font-size:18px;font-weight:700;color:#334155;margin:24px 0 12px;">🏭 国内行业脉络</div>'
        for item in domestic_data.get('sector_news', []):
            html += f"""
<div style="padding:0 2px 13px 2px;font-size:13px;line-height:1.7;color:#475569;">
<b style="font-size:14px;color:#1f2937;">▪ {e(item.get('title'))}</b><br>{e(item.get('summary'))}
</div>"""

    if gemini_data.get('medical_news'):
        html += '<div style="font-size:18px;font-weight:700;color:#06604a;margin:24px 0 12px;">🧬 医学前沿精读</div>'
        for med in gemini_data.get('medical_news', []):
            url = safe_url(med.get('source_url'))
            paper_link = f'<a href="{url}" style="color:#047857;text-decoration:none;">论文来源</a>' if url else '来源链接未核验'
            html += f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:12px;background-color:#f0fdf7;border:1px solid #ccefe0;">
<tr><td style="padding:16px 17px;font-size:13px;line-height:1.7;color:#14532d;">
<div style="font-size:15px;font-weight:700;color:#065f46;">🔬 {e(med.get('project_title'))}</div>
<div style="font-size:11px;color:#059669;margin:4px 0 9px;">{e(med.get('journal_and_time'))} · {e(med.get('doi_or_pmid'))} · {paper_link}</div>
<b>研究背景：</b>{e(med.get('background'))}<br>
<b>研究对象/药物：</b>{e(med.get('drug_name'))}<br>
<b>方法突破：</b>{e(med.get('method_breakthrough'))}<br>
<b>转化价值：</b>{e(med.get('clinical_value'))}
</td></tr></table>"""

    if domestic_data.get('focus_stocks'):
        html += '<div style="font-size:18px;font-weight:700;color:#25316d;margin:24px 0 5px;">📈 三只核心 A 股追踪</div>'
        html += '<div style="font-size:11px;color:#94a3b8;margin-bottom:12px;">固定证券代码，最多三只；红色偏强、绿色偏弱、橙色震荡。</div>'
        color_background = {'#ef4444': '#fff1f2', '#10b981': '#ecfdf5', '#f97316': '#fff7ed'}
        for stock in domestic_data.get('focus_stocks', []):
            v_color = stock.get('valuation_color', '#f97316')
            v_bg = color_background.get(v_color, '#fff7ed')
            highlights = ''.join(f'<div>• {e(item)}</div>' for item in stock.get('highlights', [])) or '暂无已核验亮点'
            risks = ''.join(f'<div>• {e(item)}</div>' for item in stock.get('risks', [])) or '暂无已核验风险'
            evidence = ' · '.join(filter(None, [e(stock.get('verification_status')), e(stock.get('data_as_of')), e(stock.get('source'))]))
            keyword = e(stock.get('search_keyword'))
            html += f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:14px;background-color:#fbfcfe;border:1px solid #e2e8f0;">
<tr><td style="padding:16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td style="font-size:16px;font-weight:700;color:#0f172a;">{e(stock.get('name'))} <span style="font-size:11px;color:#64748b;">{e(stock.get('ticker'))}</span></td>
<td align="right"><span style="font-size:11px;font-weight:700;color:{v_color};background-color:{v_bg};padding:4px 8px;">{e(stock.get('trend_signal'))}</span></td>
</tr></table>
<div style="font-size:11px;color:#64748b;margin:8px 0;">核验记录：{evidence or '待核验'}{(' · 搜索：' + keyword) if keyword else ''}</div>
<div style="font-size:13px;line-height:1.65;color:#075985;background-color:#f0f9ff;border-left:3px solid #0284c7;padding:8px 10px;"><b>估值/价格：</b>{e(stock.get('price_info'))}</div>
<div style="font-size:13px;line-height:1.65;color:#475569;margin:9px 0 12px;"><b>盘面与逻辑：</b>{e(stock.get('key_levels'))}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td width="49%" valign="top" style="font-size:12px;line-height:1.65;color:#7f1d1d;background-color:#fff1f2;border-left:3px solid #ef4444;padding:10px;"><b>投资亮点</b><br>{highlights}</td>
<td width="2%"></td>
<td width="49%" valign="top" style="font-size:12px;line-height:1.65;color:#14532d;background-color:#ecfdf5;border-left:3px solid #10b981;padding:10px;"><b>风险因素</b><br>{risks}</td>
</tr></table>
</td></tr></table>"""

    if gemini_data.get('romantic_quote'):
        html += f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:26px;background-color:#fdf2f8;background:linear-gradient(135deg,#fdf2f8,#fce7f3);border:1px solid #f8cfe0;">
<tr><td align="center" style="padding:24px 18px;color:#be185d;font-size:15px;font-weight:700;line-height:1.8;">🌸 {e(gemini_data.get('romantic_quote'))} 💖</td></tr>
</table>"""

    html += f"""
<div style="font-size:10px;line-height:1.6;color:#94a3b8;margin-top:20px;padding-top:12px;border-top:1px solid #edf0f4;">
免责声明：本邮件为自动整理的信息摘要，不构成投资、诊疗或其他专业建议。请以交易所、上市公司、期刊及医疗机构的正式信息为准。
</div>
</td></tr>
<tr><td align="center" style="padding:18px;background-color:#fafafa;color:#a1a1aa;font-size:10px;">© {now_bj.year} Morning Letter · Coze × Gemini</td></tr>
</table></td></tr></table></body></html>"""
    return html

def send_email(html_body):
    missing = [name for name, value in {
        'SMTP_SERVER': smtp_server,
        'SENDER_EMAIL': sender_email,
        'SENDER_PASSWORD': sender_password,
        'RECEIVER_EMAIL': receiver_email,
    }.items() if not value]
    if missing:
        log(f"❌ 邮件配置缺失: {', '.join(missing)}")
        return False

    log("📧 正在打包发送每日晨报...")
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"✨ {today_str} A股量化透视 × 全球学术前沿 🎀"
    msg['From'] = sender_email
    msg['To'] = receiver_email
    if cc_email:
        msg['Cc'] = cc_email
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid()
    plain_body = f"{today_str} 每日晨报已生成。请使用支持 HTML 的邮件客户端阅读完整内容。"
    msg.attach(MIMEText(plain_body, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    recipients = [receiver_email] + ([cc_email] if cc_email else [])
    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipients, msg.as_string())
        log("🎉 每日晨报已成功投递！")
        return True
    except Exception as exc:
        log(f"❌ 邮件模块报错: {str(exc)[:500]}")
        return False

def main():
    log("🎬 启动 Coze + Gemini 混合专家模型调度枢纽...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_domestic = executor.submit(fetch_coze_data)
        future_gemini = executor.submit(fetch_gemini_data)
        
        domestic_data = future_domestic.result()
        gemini_data = future_gemini.result()
        
    if not domestic_data and not gemini_data:
        log("❌ 国内与国际引擎均响应失败，任务终止。")
        sys.exit(1)
        
    if not domestic_data: log("⚠️ Coze A 股数据拉取失败，本期将仅包含全球新闻与医学解析。")
    if not gemini_data: log("⚠️ Gemini 国际数据拉取失败，本期将仅包含 A 股信息。")

    sent = send_email(format_html(domestic_data, gemini_data))
    if not sent:
        # 让 GitHub Actions 正确标红，避免“日志显示成功但女朋友没有收到”。
        sys.exit(1)

    # 只有实际投递成功后才写入去重账本。
    save_new_history(domestic_data)

if __name__ == '__main__':
    main()
