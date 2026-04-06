import os
import requests
import json
import re
import time
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone

# 实时日志输出
def log(message):
    print(f"[{datetime.now(timezone(timedelta(hours=8))).strftime('%H:%M:%S')}] {message}")
    sys.stdout.flush()

# ==========================================
# 1. 配置中心
# ==========================================
coze_token = os.getenv('COZE_API_TOKEN')
coze_bot_id = os.getenv('COZE_BOT_ID')
smtp_server = os.getenv('SMTP_SERVER')       
sender_email = os.getenv('SENDER_EMAIL')     
sender_password = os.getenv('SENDER_PASSWORD') 
receiver_email = "779825335@qq.com"   
cc_email = "15757699818@163.com"     

tz_bj = timezone(timedelta(hours=8))
now_bj = datetime.now(tz_bj)
today_str = now_bj.strftime('%Y年%m月%d日')

# ==========================================
# 2. 账本系统
# ==========================================
HISTORY_FILE = "news_history.txt"

def get_past_news():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def save_new_history(data):
    new_titles = []
    for item in data.get('sector_news', []) + data.get('medical_news', []):
        if item.get('title'): new_titles.append(item.get('title'))
    if not new_titles: return
    lines = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
    lines.extend(new_titles)
    lines = lines[-100:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        for l in lines: f.write(l + "\n")

# ==========================================
# 3. 增强版【博士级】学术与投研指令
# ==========================================
past_news_list = get_past_news()
journal_rotation = ["NEJM, Lancet", "Nature Medicine, Cell", "JAMA, BMJ", "Science Translational Medicine"][now_bj.day % 4]

SEARCH_PROMPT = f"""
今天是 {today_str}。请执行定向【博士级】学术与投研任务。
🚨【绝对去重黑名单】：{past_news_list}

【采编硬性指令】：
1. 🏭【行业精要】（2-4条）：深度复盘军工、电网、新能源最新重大政策及产业链传导逻辑。
2. ⚖️【板块建议】：给出板块仓位建议及宏观驱动力分析。
3. 🧬【学术级医药前沿】（2-4条）：
   - 受众背景：受众为医学博士，要求语言专业、硬核。
   - 重点轮换：今日侧重 {journal_rotation}。
   - 🚨【药物干预特别指令】：若涉及药物，必须在[研究问题]或[技术方法]中括号标注具体的药物通用名（Generic Name）。
   - 摘要结构（篇幅要求：每条不少于200字）：
     ① 研究团队：具体机构全称及团队核心研究方向。
     ② 研究问题：深度阐述试图解决的科学/临床痛点。
     ③ 技术方法：详述核心技术、实验模型、干预策略。
     ④ 核心突破：对比既有研究，详述其在机制或疗效上的创新点。
     ⑤ 潜在意义：讨论该研究的转化医学价值及未来临床场景。
4. 🌟【优选自选股】（仅限1只）：基于基本面、财务亮点与资金筹码面，精选【1只】优质标的。
5. 🎯【资产深度追踪】：必须详尽分析【航发科技、航天动力、航发控制、奥瑞德、长江电力、多氟多、英维克、中国能建】。
   - 增加内容：除了资金面与点位，需包含其行业竞争地位、最新财报亮点或盘中异动逻辑，字数要充实。
6. 💌【专属浪漫彩蛋】：原创文艺深情情话。🚨严禁出现任何金融、交易或医学术语。

🚨【强制 JSON 格式】：
{{
    "sector_news": [{{ "title": "标题", "summary": "摘要" }}],
    "sector_advice": "建议内容",
    "medical_news": [{{ "title": "文献标题", "journal": "期刊来源", "summary": "结构化长文本摘要" }}],
    "watchlist_recommendations": [{{ "name": "名称", "ticker": "代码", "logic": "详细推荐逻辑" }}],
    "focus_stocks": [{{ "name": "名", "advice": "建议", "key_levels": "点位", "fund_flow": "资金", "history_trend": "阶段", "reason": "详尽理由" }}],
    "romantic_quote": "文艺情话"
}}
"""

# ==========================================
# 4. 抓取逻辑 (静默等待 5 分钟)
# ==========================================
def fetch_news_from_coze():
    log("🚀 启动【博士版】采编流程，深度处理中...")
    headers = {'Authorization': f'Bearer {coze_token}', 'Content-Type': 'application/json'}
    payload = {
        "bot_id": coze_bot_id, "user_id": "quant_master", "stream": False,
        "additional_messages": [{"role": "user", "content": SEARCH_PROMPT, "content_type": "text"}]
    }

    try:
        response = requests.post('https://api.coze.cn/v3/chat', headers=headers, json=payload, timeout=60)
        res = response.json()
        if res.get('code') != 0:
            log(f"❌ API 报错: {res.get('msg')}")
            return None

        chat_id, conversation_id = res['data']['id'], res['data']['conversation_id']
        
        log("⏳ AI 正在深度检索顶刊文献与行情，预计需要 2-3 分钟...")
        for i in range(30):
            ret_res = requests.get(f'https://api.coze.cn/v3/chat/retrieve?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers).json()
            status = ret_res.get('data', {}).get('status')
            if status == 'completed':
                log("✅ 数据生成完毕！")
                break
            elif status in ['failed', 'canceled']:
                log(f"❌ 任务中断: {status}")
                return None
            time.sleep(10)
        else:
            log("❌ 等待超时。")
            return None

        msgs = requests.get(f'https://api.coze.cn/v3/chat/message/list?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers).json()
        content = next((m.get('content') for m in msgs.get('data', []) if m.get('type') == 'answer'), "")
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        return json.loads(json_match.group()) if json_match else None
    except Exception as e:
        log(f"❌ 异常: {str(e)}")
        return None

# ==========================================
# 5. 博士级 HTML 排版引擎
# ==========================================
def format_html(data):
    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin: 0; padding: 15px; font-family: sans-serif; background-color: #f3f4f6;">
        <div style="max-width: 700px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #1e293b 0%, #334155 100%); color: #ffffff; padding: 25px 20px; border-bottom: 3px solid #3b82f6;">
                <h2 style="margin: 0; font-size: 20px; letter-spacing: 1px;">⚡ 定制投研内参 × 🧬 博士学术雷达</h2>
                <p style="margin: 6px 0 0 0; font-size: 13px; color: #94a3b8;">{today_str} · 专业版深度追踪</p>
            </div>
            <div style="padding: 20px;">
    """
    
    # 🧬 医药学术 - 博士详尽版
    html += "<h3 style='color: #1e293b; border-bottom: 1px solid #eee; padding-bottom: 5px;'>🧬 全球医药顶刊学术前沿</h3>"
    for item in data.get('medical_news', []):
        s = item.get('summary', '').replace('①', '<br><b style="color:#059669;">[研究团队]</b> ')\
                                   .replace('②', '<br><b style="color:#059669;">[科学问题]</b> ')\
                                   .replace('③', '<br><b style="color:#059669;">[技术方法]</b> ')\
                                   .replace('④', '<br><b style="color:#059669;">[核心突破]</b> ')\
                                   .replace('⑤', '<br><b style="color:#059669;">[转化意义]</b> ')
        html += f"""
        <div style='background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 15px; margin-bottom: 18px; border-radius: 6px;'>
            <h4 style='margin: 0 0 8px 0; font-size: 15px; color: #064e3b; line-height: 1.4;'>{item.get('title')}</h4>
            <div style='color: #047857; font-size: 11px; font-weight: bold; background: #d1fae5; display: inline-block; padding: 2px 8px; border-radius: 10px;'>来源: {item.get('journal', 'N/A')}</div>
            <p style='margin: 10px 0 0 0; font-size: 13px; color: #166534; line-height: 1.7; text-align: justify;'>{s}</p>
        </div>"""

    # 🌟 优选自选股
    html += "<h3 style='color: #1e293b; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-top: 30px;'>🌟 深度研选标的</h3>"
    for rec in data.get('watchlist_recommendations', []):
        html += f"<div style='background: #fffbeb; border: 1px solid #fde68a; padding: 15px; border-radius: 8px; margin-bottom: 20px;'><b style='color: #b45309; font-size: 15px;'>{rec.get('name')} ({rec.get('ticker', 'N/A')})</b><p style='margin: 8px 0 0 0; font-size: 13px; color: #92400e; line-height: 1.7;'>{rec.get('logic')}</p></div>"

    # 🎯 核心资产追踪 (加厚版)
    html += "<h3 style='color: #1e293b; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-top: 30px;'>🎯 核心资产量价与基本面复盘</h3>"
    for stock in data.get('focus_stocks', []):
        adv = stock.get('advice', '')
        c = "#ef4444" if "加" in adv or "多" in adv else ("#10b981" if "减" in adv or "空" in adv else "#f97316")
        html += f"""
        <div style='border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 15px; overflow: hidden;'>
            <div style='background: #f8fafc; padding: 10px 15px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center;'>
                <b style='font-size: 14px;'>{stock.get('name')}</b> 
                <span style='color:white; background:{c}; padding: 3px 8px; border-radius: 4px; font-size: 11px;'>{adv}</span>
            </div>
            <div style='padding: 12px 15px; font-size: 13px; color: #475569;'>
                <p style='margin: 0;'><b>📊 关键点位:</b> {stock.get('key_levels')} | <b>🌊 资金动向:</b> {stock.get('fund_flow')}</p>
                <p style='margin: 8px 0;'><b>📉 历史分位:</b> {stock.get('history_trend')}</p>
                <p style='color:{c}; font-weight:bold; border-top: 1px dashed #eee; padding-top: 8px; margin: 8px 0 0 0;'>详尽逻辑: {stock.get('reason')}</p>
            </div>
        </div>"""

    # 🏭 行业精要
    html += "<h3 style='color: #1e293b; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-top: 30px;'>🏭 重点行业政策与传导</h3>"
    for item in data.get('sector_news', []):
        html += f"<div style='margin-bottom: 15px;'><h4 style='margin: 0 0 5px 0; font-size: 14px;'>▪ {item.get('title')}</h4><p style='margin:0; font-size: 13px; color: #475569; line-height: 1.6;'>{item.get('summary')}</p></div>"

    # 💌 浪漫彩蛋
    html += f"""
            </div>
            <div style="background: linear-gradient(135deg, #fff1f2 0%, #ffe4e6 100%); padding: 35px 25px; text-align: center; border-top: 1px dashed #fda4af;">
                <p style="margin: 0; font-size: 15px; color: #be123c; font-style: italic; line-height: 1.8; letter-spacing: 1px;">"{data.get('romantic_quote')}"</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_email(body):
    log("📧 正在发送【博士级】定制研报...")
    msg = MIMEMultipart()
    msg['Subject'] = f"⚡ {today_str} 核心资产追踪 × 🧬 医学顶刊雷达"
    msg['From'], msg['To'] = sender_email, receiver_email
    msg.attach(MIMEText(body, 'html', 'utf-8'))
    with smtplib.SMTP_SSL(smtp_server, 465) as s:
        s.login(sender_email, sender_password)
        s.sendmail(sender_email, [receiver_email, cc_email], msg.as_string())
    log("✅ 邮件推送成功！")

# ==========================================
# 🚀 启动
# ==========================================
if __name__ == '__main__':
    log("🎬 脚本正式启动...")
    report_data = fetch_news_from_coze()
    if report_data:
        send_email(format_html(report_data))
        save_new_history(report_data)
        log("✨ 任务完成。")
    else:
        log("⚠️ 未能生成报告。")
