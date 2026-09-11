import concurrent.futures
import html as html_lib
import json
import os
import re
import smtplib
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

import requests

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


# ==========================================
# 1. 配置中心
# ==========================================
def log(message):
    bj_time = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S")
    print(f"[{bj_time}] [每日晨报] {message}")
    sys.stdout.flush()


coze_token = os.getenv("COZE_API_TOKEN", "").strip()
coze_bot_id = os.getenv("COZE_BOT_ID", "").strip()
gemini_api_key = os.getenv("GOOGLE_API_KEY", "").strip()

smtp_server = os.getenv("SMTP_SERVER", "").strip()
smtp_port = int(os.getenv("SMTP_PORT", "465"))
sender_email = os.getenv("SENDER_EMAIL", "").strip()
sender_password = os.getenv("SENDER_PASSWORD", "").strip()
receiver_email = os.getenv("RECEIVER_EMAIL", "779825335@qq.com").strip()
cc_email = os.getenv("CC_EMAIL", "15757699818@163.com").strip()

hero_image_url = os.getenv("EMAIL_HERO_IMAGE_URL", "").strip()
gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
gemini_fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "").strip()

REQUEST_TIMEOUT = (15, 60)
HISTORY_FILE = os.getenv("HISTORY_FILE", "daily_report_history.json").strip()
HISTORY_MAX_ITEMS = 180

EXPECTED_STOCKS = {
    "多氟多": {"name": "多氟多", "ticker": "002407.SZ"},
    "华虹宏力": {"name": "华虹公司", "ticker": "688347.SH"},
    "华虹公司": {"name": "华虹公司", "ticker": "688347.SH"},
    "华虹半导体": {"name": "华虹公司", "ticker": "688347.SH"},
    "中信证券": {"name": "中信证券", "ticker": "600030.SH"},
}

HISTORY_CATEGORIES = (
    "major_news",
    "sector_news",
    "papers",
    "fun_facts",
    "medical_pearls",
    "stock_changes",
)

tz_bj = timezone(timedelta(hours=8))
now_bj = datetime.now(tz_bj)
today_str = now_bj.strftime("%Y年%m月%d日")
today_iso = now_bj.strftime("%Y-%m-%d")

gemini_client = (
    genai.Client(api_key=gemini_api_key)
    if gemini_api_key and genai is not None
    else None
)


# ==========================================
# 2. 历史记录与基础清洗
# ==========================================
def _blank_history():
    return {category: [] for category in HISTORY_CATEGORIES}


def load_history():
    history = _blank_history()
    if not os.path.exists(HISTORY_FILE):
        return history

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            loaded = json.load(file)
        if isinstance(loaded, dict):
            for category in HISTORY_CATEGORIES:
                rows = loaded.get(category, [])
                if isinstance(rows, list):
                    history[category] = [row for row in rows if isinstance(row, dict)]
            return history
    except (json.JSONDecodeError, OSError):
        pass

    # 兼容旧版逐行 news_history.txt。
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            history["sector_news"] = [
                {"date": "legacy", "key": line.strip(), "title": line.strip()}
                for line in file
                if line.strip()
            ][-HISTORY_MAX_ITEMS:]
    except OSError:
        return _blank_history()
    return history


history_data = load_history()


def clean_string(value, max_length=2000):
    if value is None:
        return ""
    return str(value).strip()[:max_length]


def clean_string_list(value, limit=3, item_length=300):
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:limit]:
        cleaned = clean_string(item, item_length)
        if cleaned:
            result.append(cleaned)
    return result


def normalize_key(value):
    value = unicodedata.normalize("NFKC", clean_string(value, 300)).lower()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value)


def history_titles(category, limit=30):
    rows = history_data.get(category, [])[-limit:]
    titles = [clean_string(row.get("title"), 160) for row in rows]
    return [title for title in titles if title]


def history_text(category, limit=30):
    titles = history_titles(category, limit)
    return "；".join(titles) if titles else "无"


def append_history(category, title):
    title = clean_string(title, 180)
    key = normalize_key(title)
    if not title or not key:
        return
    rows = history_data.setdefault(category, [])
    rows[:] = [row for row in rows if normalize_key(row.get("title")) != key]
    rows.append({"date": today_iso, "key": key, "title": title})
    del rows[:-HISTORY_MAX_ITEMS]


def save_report_history(domestic_data, gemini_data):
    domestic_data = domestic_data or {}
    gemini_data = gemini_data or {}

    for item in gemini_data.get("today_events", []):
        append_history("major_news", item.get("title"))
    for item in gemini_data.get("focus_sector_news", []):
        append_history("sector_news", item.get("title"))
    for item in gemini_data.get("academic_papers", []):
        append_history("papers", item.get("project_title"))

    concept = gemini_data.get("science_concept") or {}
    append_history("fun_facts", concept.get("term"))

    pearl = gemini_data.get("medical_pearl") or {}
    append_history("medical_pearls", pearl.get("question"))

    for stock in domestic_data.get("focus_stocks", []):
        change = stock.get("change_since_yesterday")
        if change and "暂无值得特别关注" not in change:
            append_history("stock_changes", f"{stock.get('name')}：{change}")

    temp_path = f"{HISTORY_FILE}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(history_data, file, ensure_ascii=False, indent=2)
        os.replace(temp_path, HISTORY_FILE)
    except OSError as exc:
        log(f"历史记录保存失败：{str(exc)[:300]}")


def extract_json(text):
    """从模型返回内容中提取 JSON，不用猜测填补缺失数据。"""
    if not text:
        raise ValueError("模型返回为空")
    normalized = unicodedata.normalize("NFKC", str(text)).strip()
    normalized = re.sub(
        r"^```(?:json)?\s*|\s*```$", "", normalized, flags=re.I | re.S
    ).strip()
    start, end = normalized.find("{"), normalized.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("模型返回中未找到完整 JSON 对象")
    return json.loads(normalized[start : end + 1])


def safe_url(value):
    url = clean_string(value, 800)
    if not re.match(r"^https://[^\s]+$", url, flags=re.I):
        return ""
    return html_lib.escape(url, quote=True)


def has_reliable_source(item):
    return bool(safe_url(item.get("source_url")))


def e(value):
    return html_lib.escape(clean_string(value), quote=True)


def source_html(item, label="原始来源"):
    url = safe_url(item.get("source_url"))
    title = e(item.get("source_title"))
    published = e(item.get("published_at"))
    parts = [part for part in (published, title) if part]
    prefix = " · ".join(parts)
    if url:
        link = f'<a href="{url}" style="color:#2563eb;text-decoration:none;">{e(label)}</a>'
        return f"{prefix} · {link}" if prefix else link
    return prefix


def _bounded_dict(value):
    return value if isinstance(value, dict) else {}


def _bounded_list(value, limit):
    if not isinstance(value, list):
        return []
    return [item for item in value[:limit] if isinstance(item, dict)]


# ==========================================
# 3. 模型输出标准化
# ==========================================
def normalize_domestic_data(data):
    if not isinstance(data, dict):
        return {}

    normalized_by_ticker = {}
    for stock in _bounded_list(data.get("focus_stocks"), 6):
        raw_name = clean_string(stock.get("name"), 30)
        raw_ticker = clean_string(stock.get("ticker"), 20).upper()
        expected = next(
            (value for alias, value in EXPECTED_STOCKS.items() if alias in raw_name),
            None,
        )
        if not expected or (raw_ticker and raw_ticker != expected["ticker"]):
            continue

        change = clean_string(stock.get("change_since_yesterday"), 600)
        if not change:
            change = "暂无值得特别关注的新变化。"

        source_url = clean_string(stock.get("source_url"), 800)
        no_change = "暂无值得特别关注" in change
        if not no_change and not safe_url(source_url):
            change = "暂无值得特别关注的新变化。"
            no_change = True

        normalized_by_ticker[expected["ticker"]] = {
            "name": expected["name"],
            "ticker": expected["ticker"],
            "change_since_yesterday": change,
            "why_it_matters": "" if no_change else clean_string(stock.get("why_it_matters"), 600),
            "what_to_watch": [] if no_change else clean_string_list(stock.get("what_to_watch"), 3, 260),
            "verification_status": clean_string(
                stock.get("verification_status"), 30
            ) or "待核验",
            "published_at": clean_string(stock.get("published_at"), 50),
            "source_title": clean_string(stock.get("source_title"), 180),
            "source_url": "" if no_change else source_url,
        }

    focus_stocks = []
    for ticker in ("002407.SZ", "688347.SH", "600030.SH"):
        if ticker in normalized_by_ticker:
            focus_stocks.append(normalized_by_ticker[ticker])
        else:
            expected = next(v for v in EXPECTED_STOCKS.values() if v["ticker"] == ticker)
            focus_stocks.append(
                {
                    "name": expected["name"],
                    "ticker": ticker,
                    "change_since_yesterday": "暂无值得特别关注的新变化。",
                    "why_it_matters": "",
                    "what_to_watch": [],
                    "verification_status": "未发现可核验新增信息",
                    "published_at": "",
                    "source_title": "",
                    "source_url": "",
                }
            )
    return {"focus_stocks": focus_stocks}


def normalize_news_items(value, limit):
    result = []
    for item in _bounded_list(value, 100):
        normalized = {
            "title": clean_string(item.get("title"), 160),
            "category": clean_string(item.get("category"), 40),
            "summary": clean_string(item.get("summary"), 900),
            "why_important": clean_string(item.get("why_important"), 600),
            "market_impact": clean_string(item.get("market_impact"), 600),
            "published_at": clean_string(item.get("published_at"), 50),
            "source_title": clean_string(item.get("source_title"), 180),
            "source_url": clean_string(item.get("source_url"), 800),
        }
        if normalized["title"] and normalized["summary"] and has_reliable_source(normalized):
            result.append(normalized)
            if len(result) >= limit:
                break
    return result


def normalize_papers(value):
    result = []
    for item in _bounded_list(value, 2):
        normalized = {
            "paper_type": clean_string(item.get("paper_type"), 40),
            "project_title": clean_string(item.get("project_title"), 260),
            "journal_and_time": clean_string(item.get("journal_and_time"), 180),
            "doi_or_pmid": clean_string(item.get("doi_or_pmid"), 100),
            "source_title": clean_string(item.get("source_title"), 180),
            "source_url": clean_string(item.get("source_url"), 800),
            "background": clean_string(item.get("background"), 900),
            "method_and_findings": clean_string(item.get("method_and_findings"), 1200),
            "significance": clean_string(item.get("significance"), 800),
            "drug_or_intervention": clean_string(item.get("drug_or_intervention"), 400),
            "research_inspiration": clean_string(item.get("research_inspiration"), 900),
        }
        has_identity = normalized["doi_or_pmid"] or has_reliable_source(normalized)
        if normalized["project_title"] and has_identity:
            result.append(normalized)
    return result


def normalize_gemini_data(data):
    if not isinstance(data, dict):
        return {}

    market = _bounded_dict(data.get("market_snapshot"))
    normalized_market = {
        "a_share_session": clean_string(market.get("a_share_session"), 80),
        "a_share_summary": clean_string(market.get("a_share_summary"), 1000),
        "overnight_markets": clean_string(market.get("overnight_markets"), 800),
        "risk_appetite": clean_string(market.get("risk_appetite"), 500),
        "market_worry": clean_string(market.get("market_worry"), 500),
        "published_at": clean_string(market.get("published_at"), 50),
        "source_title": clean_string(market.get("source_title"), 180),
        "source_url": clean_string(market.get("source_url"), 800),
    }
    if not has_reliable_source(normalized_market):
        normalized_market = {}

    science = _bounded_dict(data.get("science_concept"))
    normalized_science = {
        "term": clean_string(science.get("term"), 120),
        "content_type": clean_string(science.get("content_type"), 50),
        "field": clean_string(science.get("field"), 80),
        "definition": clean_string(science.get("definition"), 700),
        "scenario": clean_string(science.get("scenario"), 700),
        "discovery_or_fun_fact": clean_string(
            science.get("discovery_or_fun_fact"), 900
        ),
        "source_title": clean_string(science.get("source_title"), 180),
        "source_url": clean_string(science.get("source_url"), 800),
    }
    if not has_reliable_source(normalized_science):
        normalized_science = {}

    pearl = _bounded_dict(data.get("medical_pearl"))
    normalized_pearl = {
        "category": clean_string(pearl.get("category"), 40),
        "question": clean_string(pearl.get("question"), 220),
        "case_or_context": clean_string(pearl.get("case_or_context"), 700),
        "what_is_happening": clean_string(pearl.get("what_is_happening"), 900),
        "clinical_thinking": clean_string(pearl.get("clinical_thinking"), 1200),
        "key_takeaway": clean_string(pearl.get("key_takeaway"), 700),
        "guideline_and_year": clean_string(pearl.get("guideline_and_year"), 180),
        "source_title": clean_string(pearl.get("source_title"), 180),
        "source_url": clean_string(pearl.get("source_url"), 800),
    }
    if not has_reliable_source(normalized_pearl):
        normalized_pearl = {}

    return {
        "market_snapshot": normalized_market,
        "today_events": normalize_news_items(data.get("today_events"), 3),
        "focus_sector_news": normalize_news_items(data.get("focus_sector_news"), 4),
        "academic_papers": normalize_papers(data.get("academic_papers")),
        "science_concept": normalized_science,
        "medical_pearl": normalized_pearl,
        "romantic_quote": clean_string(data.get("romantic_quote"), 120),
    }


# ==========================================
# 4. 提示词
# ==========================================
STOCK_OUTPUT_EXAMPLE = {
    "focus_stocks": [
        {
            "name": "多氟多",
            "ticker": "002407.SZ",
            "change_since_yesterday": "只写相较上一期新增且可核验的变化；没有则写暂无值得特别关注的新变化。",
            "why_it_matters": "变化对公司或投资判断的实际意义；无变化时留空",
            "what_to_watch": ["接下来值得观察的触发因素"],
            "verification_status": "已核验/部分核验/未发现可核验新增信息",
            "published_at": "来源日期",
            "source_title": "来源名称与页面标题",
            "source_url": "真实 HTTPS 原始链接；没有可靠链接则留空",
        }
    ]
}

COZE_PROMPT = f"""
今天是 {today_str}。只追踪以下三只固定 A 股：
多氟多 002407.SZ、华虹公司 688347.SH、中信证券 600030.SH。

目标不是重复长期投资逻辑，而是回答“和上一期相比，有什么新增变化”。
近期已经报道的变化：{history_text('stock_changes', 30)}

要求：
1. 只写公告、监管文件、公司正式披露或可靠主流财经媒体已经证实的新增变化。
2. 没有重要变化时直接写“暂无值得特别关注的新变化。”，不要凑内容。
3. 删除价格、涨跌幅、PE/PB、支撑位、压力位、技术指标和筹码区间。
4. 不得把港股华虹半导体 01347.HK 的行情或估值写入华虹公司 688347.SH。
5. 有新增事实时必须提供发布日期、来源标题和真实 HTTPS 链接；无法核验则不要写成事实。
6. 严格返回一个 JSON 对象，不要使用 Markdown。

输出结构示例：
{json.dumps(STOCK_OUTPUT_EXAMPLE, ensure_ascii=False, indent=2)}
"""


REPORT_OUTPUT_EXAMPLE = {
    "market_snapshot": {
        "a_share_session": "最近一个已结束的 A 股交易日及日期",
        "a_share_summary": "指数、成交额、涨跌家数、涨跌停、强弱板块和赚钱效应的短概览",
        "overnight_markets": "隔夜美股与其他重要海外市场的短概览",
        "risk_appetite": "今日开盘前风险偏好判断及理由",
        "market_worry": "市场当前最担心的一件事",
        "published_at": "来源日期",
        "source_title": "主要来源标题",
        "source_url": "真实 HTTPS 链接",
    },
    "today_events": [
        {
            "title": "全球真正重要的大事",
            "category": "央行/宏观/地缘/能源/贸易",
            "summary": "发生了什么",
            "why_important": "为什么重要",
            "market_impact": "对利率、汇率、油价或风险偏好的潜在影响",
            "published_at": "来源日期",
            "source_title": "原始来源或权威媒体标题",
            "source_url": "真实 HTTPS 链接",
        }
    ],
    "focus_sector_news": [
        {
            "title": "重点板块新增信息",
            "category": "AI与半导体/新能源与储能材料/券商与资本市场/创新药与脑机接口",
            "summary": "只写与指定投资方向直接相关的重要变化",
            "why_important": "为何值得跟踪",
            "market_impact": "对产业或投资判断的影响",
            "published_at": "来源日期",
            "source_title": "可靠来源标题",
            "source_url": "真实 HTTPS 链接",
        }
    ],
    "academic_papers": [
        {
            "paper_type": "general_frontier 或 personal_research",
            "project_title": "真实论文英文标题及中文释义",
            "journal_and_time": "期刊与发表日期",
            "doi_or_pmid": "DOI 或 PMID",
            "source_title": "期刊或 PubMed 页面标题",
            "source_url": "真实 HTTPS 链接",
            "background": "研究要解决的问题",
            "method_and_findings": "研究方法、关键结果与重要数字",
            "significance": "为什么值得关注",
            "drug_or_intervention": "仅当论文确实涉及药物或干预时写具体名称，否则留空",
            "research_inspiration": "仅 personal_research 必填：对抗肿瘤与骨修复材料研究的潜在启发",
        }
    ],
    "science_concept": {
        "term": "概念中英文名",
        "content_type": "分子/现象/定律/实验方法/统计概念/计算机思想/经济学概念",
        "field": "所属领域",
        "definition": "简单但准确的解释",
        "scenario": "一个真实运作场景",
        "discovery_or_fun_fact": "有可靠资料支持的发现背景、历史故事或反直觉事实",
        "source_title": "可靠来源标题",
        "source_url": "真实 HTTPS 链接",
    },
    "medical_pearl": {
        "category": "口腔颌面/医美/营养学/基础医学",
        "question": "用一个临床问题作为标题",
        "case_or_context": "可选的简短病例或场景",
        "what_is_happening": "这是什么或发生了什么",
        "clinical_thinking": "临床上怎么想",
        "key_takeaway": "最容易忽略或最值得记住的一点",
        "guideline_and_year": "涉及剂量、流程、禁忌证时注明指南与年份，否则留空",
        "source_title": "可靠来源或指南标题",
        "source_url": "真实 HTTPS 链接",
    },
    "romantic_quote": "50字以内的早安短句",
}

pearl_categories = ("口腔颌面", "医美", "营养学", "基础医学")
pearl_category = pearl_categories[now_bj.toordinal() % len(pearl_categories)]
fun_fact_domain = (
    "生物学、医学或材料科学"
    if now_bj.toordinal() % 10 < 7
    else "物理、天文、计算机、AI、心理学或经济学"
)

GEMINI_PROMPT = f"""
今天是 {today_str}。请先使用 Google Search 检索并核验，再制作一份中文晨报数据。
最终只返回一个 JSON 对象，不要输出 Markdown、引用脚注或 JSON 之外的解释。

一、市场概览
读取最近一个已经结束的 A 股交易日。用一个短段落说明：上证、深证、创业板等主要指数表现、全市场成交额、上涨/下跌家数、涨停/跌停数量、主要强弱板块和赚钱效应。再用一个短段落概括隔夜美股和重要海外市场，最后判断今日开盘前风险偏好，并写出“市场当前最担心的一件事”。
数字必须来自同一交易日的可靠财经来源；若无法核验某项数字，就省略该数字，不得估算。

二、今日大事，最多 3 条
只选主流媒体头条级、主要央行或政府高层表态、G20/G7/OPEC+、重大经济数据、关税制裁、战争局势等可能影响利率、汇率、油价、贸易或全球风险偏好的事件。
近期已报：{history_text('major_news', 30)}
没有足够重要的新事件就少写。

三、重点板块，最多 4 条
只跟踪 AI/半导体产业链、新能源/储能材料、券商/资本市场、创新药/脑机接口。没有重要新闻的方向可以不写，不要为了凑数量加入泛科技新闻。
近期已报：{history_text('sector_news', 40)}

四、每日学术文献，固定 2 篇
第一篇 paper_type=general_frontier：选择整个医学和生命科学领域近期真正值得关注的进展，可来自肿瘤、免疫、基因编辑、细胞治疗、代谢、神经科学、再生医学或新型诊疗技术。
第二篇 paper_type=personal_research：选择与口腔医学、口腔颌面外科、头颈/口腔肿瘤、临床研究、生物信息学、抗肿瘤与骨修复材料相关的论文。可关注骨再生、生物材料、组织工程、药物递送、肿瘤微环境、免疫调控、单细胞、空间组学和生信方法，并回答“这篇文章对我的研究有什么潜在启发”。
不要优先搜索药物论文。只有论文确实涉及药物或干预时，才填写 drug_or_intervention，并写具体通用名；其他论文留空。
每篇必须有可验证的论文标题，并提供 DOI、PMID 或期刊原始链接。近期已报：{history_text('papers', 50)}

五、Fun Facts
今天从“{fun_fact_domain}”中选择一个条目。它可以是分子、科学现象、定律、实验方法、统计概念、计算机思想或经济学概念。写简单解释、实际运作场景和可靠的发现背景/历史故事。60 期内不要重复这些概念：{history_text('fun_facts', 60)}

六、Medical Pearl
今天轮换到“{pearl_category}”。一次只解决一个几分钟能读完的临床小问题，用问题带出知识，回答：发生了什么、临床上怎么想、最容易忽略或最值得记住什么。可用病例题、急诊决策、治疗方案、手术技术、医美技术、营养指标或基础机制。若涉及指南、剂量、急救流程或禁忌证，必须给出可靠来源和指南年份。近期已讲：{history_text('medical_pearls', 60)}

七、来源和可靠性
1. 今日大事和重点板块的每条内容都必须有真实可打开的 HTTPS 原始来源或权威媒体链接，否则不要输出该条。
2. “全球首次”“世界纪录”“提升 XX%”“XX Wh/kg”等具体表述必须能在链接中核验，否则删除。
3. 区分事实、机构观点和你的推断，不得把推断写成事实。
4. 不要编造来源、论文、DOI、PMID、日期或数字。

八、早安短句
写一句 50 字以内、自然、不重复套话的温柔早安短句。

输出结构：
{json.dumps(REPORT_OUTPUT_EXAMPLE, ensure_ascii=False, indent=2)}
"""


# ==========================================
# 5. 双引擎调用
# ==========================================
def fetch_coze_data(max_attempts=3):
    if not coze_token or not coze_bot_id:
        log("未检测到 Coze 配置，固定股票栏目将显示无可核验新增信息。")
        return normalize_domestic_data({})

    headers = {
        "Authorization": f"Bearer {coze_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "bot_id": coze_bot_id,
        "user_id": "quant_master",
        "additional_messages": [
            {"role": "user", "content": COZE_PROMPT, "content_type": "text"}
        ],
    }

    for attempt in range(1, max_attempts + 1):
        log(f"正在更新三只固定股票（{attempt}/{max_attempts}）")
        try:
            response = requests.post(
                "https://api.coze.cn/v3/chat",
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()
            if result.get("code") != 0:
                raise RuntimeError(
                    f"Coze 发起失败：{result.get('code')} {result.get('msg', '')}"
                )

            chat_id = result.get("data", {}).get("id")
            conversation_id = result.get("data", {}).get("conversation_id")
            if not chat_id or not conversation_id:
                raise ValueError("Coze 返回缺少会话标识")

            for _ in range(24):
                retrieve = requests.get(
                    "https://api.coze.cn/v3/chat/retrieve",
                    headers=headers,
                    params={"chat_id": chat_id, "conversation_id": conversation_id},
                    timeout=REQUEST_TIMEOUT,
                )
                retrieve.raise_for_status()
                status = retrieve.json().get("data", {}).get("status")

                if status == "completed":
                    messages = requests.get(
                        "https://api.coze.cn/v3/chat/message/list",
                        headers=headers,
                        params={
                            "chat_id": chat_id,
                            "conversation_id": conversation_id,
                        },
                        timeout=REQUEST_TIMEOUT,
                    )
                    messages.raise_for_status()
                    content = next(
                        (
                            message.get("content")
                            for message in messages.json().get("data", [])
                            if message.get("type") == "answer"
                        ),
                        "",
                    )
                    return normalize_domestic_data(extract_json(content))

                if status in {"failed", "canceled"}:
                    raise RuntimeError(f"Coze 状态异常：{status}")
                time.sleep(5)

            raise TimeoutError("Coze 请求超过 120 秒")
        except Exception as exc:
            log(f"Coze 第 {attempt} 次失败：{str(exc)[:400]}")
            if attempt < max_attempts:
                time.sleep(min(5 * attempt, 15))

    return normalize_domestic_data({})


def fetch_gemini_data():
    if gemini_client is None or types is None:
        log("未检测到可用的 Google GenAI SDK 或 GOOGLE_API_KEY。")
        return None

    # 关键修订：启用 Google Search grounding。旧版代码只有 JSON 模式，没有真实检索。
    search_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(tools=[search_tool])
    model_candidates = list(
        dict.fromkeys(
            model
            for model in (gemini_model, gemini_fallback_model)
            if model
        )
    )

    for model_id in model_candidates:
        for attempt in range(1, 3):
            log(f"正在检索市场、科研与医学信息：{model_id}（{attempt}/2）")
            try:
                response = gemini_client.models.generate_content(
                    model=model_id,
                    contents=GEMINI_PROMPT,
                    config=config,
                )
                candidates = getattr(response, "candidates", None) or []
                grounding = (
                    getattr(candidates[0], "grounding_metadata", None)
                    if candidates
                    else None
                )
                grounding_queries = (
                    getattr(grounding, "web_search_queries", None)
                    if grounding is not None
                    else None
                )
                grounding_chunks = (
                    getattr(grounding, "grounding_chunks", None)
                    if grounding is not None
                    else None
                )
                if not grounding_queries and not grounding_chunks:
                    raise ValueError("本次响应没有 Google Search grounding 记录")
                data = normalize_gemini_data(extract_json(response.text))
                if not any(
                    (
                        data.get("today_events"),
                        data.get("focus_sector_news"),
                        data.get("academic_papers"),
                        data.get("medical_pearl", {}).get("question"),
                    )
                ):
                    raise ValueError("Gemini 返回 JSON，但没有可用栏目")
                return data
            except Exception as exc:
                message = str(exc)
                log(f"Gemini {model_id} 第 {attempt} 次失败：{message[:400]}")
                if attempt < 2:
                    time.sleep(15 if ("503" in message or "429" in message) else 5)
    return None


# ==========================================
# 6. 邮件 HTML
# ==========================================
def format_html(domestic_data, gemini_data):
    domestic_data = domestic_data or normalize_domestic_data({})
    gemini_data = gemini_data or {}
    valid_hero = safe_url(hero_image_url)
    hero_html = (
        f'<img src="{valid_hero}" width="720" alt="每日晨报" '
        'style="display:block;width:100%;max-width:720px;height:auto;border:0;">'
        if valid_hero
        else ""
    )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#f2f4f8;color:#334155;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',Arial,sans-serif;">
<div style="display:none;max-height:0;overflow:hidden;color:#f2f4f8;">{e(today_str)} 的市场、重点行业、科研与医学晨报。</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f2f4f8;">
<tr><td align="center" style="padding:22px 10px;">
<table role="presentation" width="720" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:720px;background-color:#ffffff;border:1px solid #e7eaf0;">
<tr><td>{hero_html}</td></tr>
<tr><td align="center" style="padding:32px 24px;background-color:#4338ca;background:linear-gradient(135deg,#4338ca 0%,#7c3aed 55%,#db2777 100%);color:#ffffff;">
<div style="font-size:12px;letter-spacing:2px;">MORNING INTELLIGENCE LETTER</div>
<div style="font-size:26px;font-weight:700;line-height:1.35;margin-top:8px;">今日市场与医学晨报</div>
<div style="font-size:13px;margin-top:9px;">{e(today_str)} · 市场 · 投资 · 科研 · 临床</div>
</td></tr>
<tr><td style="padding:10px 24px 28px 24px;">
"""

    market = gemini_data.get("market_snapshot") or {}
    if any(
        market.get(key)
        for key in ("a_share_summary", "overnight_markets", "risk_appetite")
    ):
        source = source_html(market)
        html += f"""
<div style="font-size:18px;font-weight:700;color:#1e3a8a;margin:22px 0 12px;">📊 市场现在处于什么状态</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;border:1px solid #dbe4f0;">
<tr><td style="padding:16px 17px;font-size:13px;line-height:1.75;color:#334155;">
<div style="font-size:11px;color:#64748b;margin-bottom:7px;">{e(market.get('a_share_session'))}</div>
<b>A 股复盘：</b>{e(market.get('a_share_summary'))}<br><br>
<b>隔夜市场：</b>{e(market.get('overnight_markets'))}<br><br>
<b>开盘前风险偏好：</b>{e(market.get('risk_appetite'))}
<div style="margin-top:10px;padding:9px 11px;background-color:#fff7ed;border-left:3px solid #f97316;"><b>市场在担心什么：</b>{e(market.get('market_worry'))}</div>
<div style="font-size:11px;color:#64748b;margin-top:9px;">{source}</div>
</td></tr></table>"""

    events = gemini_data.get("today_events", [])
    if events:
        html += '<div style="font-size:18px;font-weight:700;color:#7c2d12;margin:24px 0 12px;">🌍 今日大事</div>'
        for index, item in enumerate(events, 1):
            html += f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:11px;background-color:#fffaf5;border:1px solid #fed7aa;">
<tr><td style="padding:15px 16px;font-size:13px;line-height:1.7;color:#44403c;">
<div style="font-size:15px;font-weight:700;color:#9a3412;">{index}. {e(item.get('title'))}</div>
<div style="margin-top:7px;">{e(item.get('summary'))}</div>
<div style="margin-top:8px;"><b>为什么重要：</b>{e(item.get('why_important'))}</div>
<div style="margin-top:5px;"><b>市场影响：</b>{e(item.get('market_impact'))}</div>
<div style="font-size:11px;color:#78716c;margin-top:8px;">{source_html(item)}</div>
</td></tr></table>"""

    sector_news = gemini_data.get("focus_sector_news", [])
    if sector_news:
        html += '<div style="font-size:18px;font-weight:700;color:#25316d;margin:24px 0 12px;">🧭 重点行业要闻</div>'
        for item in sector_news:
            html += f"""
<div style="padding:0 2px 14px;font-size:13px;line-height:1.72;color:#475569;">
<span style="font-size:11px;color:#4338ca;background-color:#ede9fe;padding:3px 7px;">{e(item.get('category'))}</span><br>
<b style="display:inline-block;margin-top:7px;font-size:14px;color:#1f2937;">{e(item.get('title'))}</b><br>
{e(item.get('summary'))}
<div style="margin-top:5px;"><b>值得关注：</b>{e(item.get('why_important'))}</div>
<div style="font-size:11px;color:#64748b;margin-top:6px;">{source_html(item)}</div>
</div>"""

    stocks = domestic_data.get("focus_stocks", [])
    if stocks:
        html += '<div style="font-size:18px;font-weight:700;color:#25316d;margin:24px 0 5px;">📈 三只固定股票的新变化</div>'
        html += '<div style="font-size:11px;color:#94a3b8;margin-bottom:12px;">只写相较上一期的新增信息，不重复长期逻辑，不展示无法稳定核验的行情数字。</div>'
        for stock in stocks:
            watch = "".join(
                f"<div>• {e(item)}</div>" for item in stock.get("what_to_watch", [])
            )
            source = source_html(stock)
            html += f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:12px;background-color:#fbfcfe;border:1px solid #e2e8f0;">
<tr><td style="padding:15px 16px;font-size:13px;line-height:1.7;color:#475569;">
<div style="font-size:15px;font-weight:700;color:#0f172a;">{e(stock.get('name'))} <span style="font-size:11px;color:#64748b;">{e(stock.get('ticker'))}</span></div>
<div style="margin-top:7px;"><b>相比上一期：</b>{e(stock.get('change_since_yesterday'))}</div>
{f'<div style="margin-top:6px;"><b>为什么重要：</b>{e(stock.get("why_it_matters"))}</div>' if stock.get('why_it_matters') else ''}
{f'<div style="margin-top:6px;"><b>接下来观察：</b>{watch}</div>' if watch else ''}
<div style="font-size:11px;color:#64748b;margin-top:7px;">{e(stock.get('verification_status'))}{(' · ' + source) if source else ''}</div>
</td></tr></table>"""

    papers = gemini_data.get("academic_papers", [])
    if papers:
        html += '<div style="font-size:18px;font-weight:700;color:#06604a;margin:24px 0 12px;">🧬 每日学术文献</div>'
        for item in papers:
            paper_label = (
                "与你的研究相关"
                if item.get("paper_type") == "personal_research"
                else "医学与生命科学前沿"
            )
            intervention = item.get("drug_or_intervention")
            inspiration = item.get("research_inspiration")
            html += f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:13px;background-color:#f0fdf7;border:1px solid #ccefe0;">
<tr><td style="padding:16px 17px;font-size:13px;line-height:1.72;color:#14532d;">
<div style="font-size:11px;color:#059669;">{e(paper_label)}</div>
<div style="font-size:15px;font-weight:700;color:#065f46;margin-top:4px;">{e(item.get('project_title'))}</div>
<div style="font-size:11px;color:#059669;margin:5px 0 9px;">{e(item.get('journal_and_time'))} · {e(item.get('doi_or_pmid'))} · {source_html(item, '论文页面')}</div>
<b>研究问题：</b>{e(item.get('background'))}<br>
<b>方法与发现：</b>{e(item.get('method_and_findings'))}<br>
<b>为什么重要：</b>{e(item.get('significance'))}
{f'<br><b>涉及的药物或干预：</b>{e(intervention)}' if intervention else ''}
{f'<div style="margin-top:9px;padding:9px 11px;background-color:#ffffff;border-left:3px solid #10b981;"><b>对你的研究有什么启发：</b>{e(inspiration)}</div>' if inspiration else ''}
</td></tr></table>"""

    pearl = gemini_data.get("medical_pearl") or {}
    if pearl.get("question"):
        html += f"""
<div style="font-size:18px;font-weight:700;color:#7f1d1d;margin:24px 0 12px;">🩺 Medical Pearl</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#fff7f7;border:1px solid #fecaca;">
<tr><td style="padding:16px 17px;font-size:13px;line-height:1.75;color:#4b1d1d;">
<div style="font-size:11px;color:#b91c1c;">{e(pearl.get('category'))}</div>
<div style="font-size:16px;font-weight:700;margin:4px 0 8px;">{e(pearl.get('question'))}</div>
{f'<div style="margin-bottom:8px;"><b>病例或场景：</b>{e(pearl.get("case_or_context"))}</div>' if pearl.get('case_or_context') else ''}
<b>发生了什么：</b>{e(pearl.get('what_is_happening'))}<br><br>
<b>临床上怎么想：</b>{e(pearl.get('clinical_thinking'))}
<div style="margin-top:9px;padding:9px 11px;background-color:#ffffff;border-left:3px solid #dc2626;"><b>最值得记住：</b>{e(pearl.get('key_takeaway'))}</div>
<div style="font-size:11px;color:#7f1d1d;margin-top:8px;">{e(pearl.get('guideline_and_year'))}{(' · ' + source_html(pearl)) if source_html(pearl) else ''}</div>
</td></tr></table>"""

    concept = gemini_data.get("science_concept") or {}
    if concept.get("term"):
        html += f"""
<div style="font-size:18px;font-weight:700;color:#5b217d;margin:24px 0 12px;">💡 Fun Facts</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#faf5ff;border:1px solid #ead7fa;">
<tr><td style="padding:16px 17px;font-size:13px;line-height:1.72;color:#4c1d65;">
<div style="font-size:16px;font-weight:700;">{e(concept.get('term'))}</div>
<div style="font-size:11px;color:#7e22ce;margin-bottom:9px;">{e(concept.get('content_type'))} · {e(concept.get('field'))}</div>
<b>简单解释：</b>{e(concept.get('definition'))}<br><br>
<b>实际场景：</b>{e(concept.get('scenario'))}<br><br>
<b>发现与趣闻：</b>{e(concept.get('discovery_or_fun_fact'))}
<div style="font-size:11px;color:#7e22ce;margin-top:8px;">{source_html(concept)}</div>
</td></tr></table>"""

    quote = gemini_data.get("romantic_quote")
    if quote:
        html += f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:26px;background-color:#fdf2f8;border:1px solid #f8cfe0;">
<tr><td align="center" style="padding:22px 18px;color:#be185d;font-size:15px;font-weight:700;line-height:1.8;">🌸 {e(quote)} 💖</td></tr>
</table>"""

    html += f"""
<div style="font-size:10px;line-height:1.6;color:#94a3b8;margin-top:20px;padding-top:12px;border-top:1px solid #edf0f4;">
免责声明：本邮件为自动整理的信息摘要，不构成投资、诊疗或其他专业建议。涉及交易、药物剂量、急救流程和禁忌证时，请以交易所、上市公司、最新指南、期刊及医疗机构正式信息为准。
</div>
</td></tr>
<tr><td align="center" style="padding:18px;background-color:#fafafa;color:#a1a1aa;font-size:10px;">© {now_bj.year} Morning Intelligence Letter · Coze × Gemini Grounded Search</td></tr>
</table></td></tr></table></body></html>"""
    return html


# ==========================================
# 7. 邮件发送与主流程
# ==========================================
def send_email(html_body):
    missing = [
        name
        for name, value in {
            "SMTP_SERVER": smtp_server,
            "SENDER_EMAIL": sender_email,
            "SENDER_PASSWORD": sender_password,
            "RECEIVER_EMAIL": receiver_email,
        }.items()
        if not value
    ]
    if missing:
        log(f"邮件配置缺失：{', '.join(missing)}")
        return False

    log("正在发送每日晨报")
    message = MIMEMultipart("alternative")
    message["Subject"] = f"{today_str} 今日市场与医学晨报"
    message["From"] = sender_email
    message["To"] = receiver_email
    if cc_email:
        message["Cc"] = cc_email
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid()

    plain_body = f"{today_str} 每日晨报已生成，请使用支持 HTML 的邮件客户端阅读。"
    message.attach(MIMEText(plain_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    recipients = [receiver_email] + ([cc_email] if cc_email else [])
    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipients, message.as_string())
        log("每日晨报已成功发送")
        return True
    except Exception as exc:
        log(f"邮件发送失败：{str(exc)[:400]}")
        return False


def main():
    log("开始制作今日晨报")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        domestic_future = executor.submit(fetch_coze_data)
        gemini_future = executor.submit(fetch_gemini_data)
        domestic_data = domestic_future.result()
        gemini_data = gemini_future.result()

    if not gemini_data:
        log("市场、新闻、科研与医学数据获取失败，本次不发送残缺日报。")
        sys.exit(1)

    html_body = format_html(domestic_data, gemini_data)
    if not send_email(html_body):
        sys.exit(1)

    # 只有邮件真实发送成功后才更新历史，避免失败任务污染去重记录。
    save_report_history(domestic_data, gemini_data)


if __name__ == "__main__":
    main()
