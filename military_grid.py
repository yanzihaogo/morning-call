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

# 强制实时输出日志，方便在 GitHub Actions 监控
def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
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
# 2. 账本系统 (去重深度：100条)
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
# 3. 增强版学术与投研指令
# ==========================================
past_news_list = get_past_news()
# 期刊轮换逻辑
journal_rotation = ["NEJM, Lancet", "Nature Medicine, Cell", "JAMA, BMJ", "Science Translational Medicine"][now_bj.day % 4]

SEARCH_PROMPT = f"""
今天是 {today_str}。请执行定向学术与投研任务。

🚨【绝对去重黑名单】（严禁重复报道）：
{past_news_list}

【硬性采编指令】：
1. 🏭【行业精要】（2-4条）：避开黑名单，复盘军工、电网、新能源最新政策。
2. ⚖️【板块建议】：给出上述板块的仓位建议。
3. 🧬【学术级医药前沿】（2-4条）：
   - 重点轮换：今日优先检索 {journal_rotation} 的最新研究。
   - 深度去重：若核心药物/靶点/机制与黑名单高度重合，视为旧闻。
   - 摘要结构（严格4-6句连续段落）：①研究团队及方向；②试图解决的科学问题；③核心技术/方法；④相比既有研究的核心突破（严禁空泛）；⑤潜在医学价值。
4. 🌟【优选自选股】（仅限1只）：基于基本面与筹码面，精选【1只】最优质个股推荐加入自选。
5. 🎯【金股深度追踪】：必须且只能分析【航发科技、航天动力、航发控制、奥瑞德、长江电力、多氟多、英维克、中国能建】。
   - 给出资金面动向、支撑/压力位测算、长线历史位置及明确的操作建议。
6. 💌【专属浪漫彩蛋】：原创一句极其文艺、深情的浪漫情话。
   - 🚨【绝对禁令】：情话内容必须与股票、金融、K线、均线、交易等任何术语绝对无关，回归文学与美感。

🚨【强制 JSON 格式】：
{{
    "sector_news": [{{"title": "标题", "summary": "摘要"}}],
    "sector_advice": "建议",
    "medical_news": [{{"title": "标题", "journal": "来源", "summary": "①团队...②问题...③方法...④突破...⑤意义"}}],
    "watchlist_recommendations": [{{"name": "名称", "ticker": "代码", "logic": "逻辑"}}],
    "focus_stocks": [{{
        "name": "股票名", "fund_flow": "资金", "key_levels": "点位", "history_trend": "阶段", "advice": "建议", "reason": "理由"
    }}],
    "romantic_quote": "浪漫情话"
}}
"""

# ==========================================
# 4. 抓取与解析逻辑
# ==========================================
def fetch_news_from_coze():
    log("🚀 启动 Coze AI 采编流程...")
    headers = {'Authorization': f'Bearer {coze_token}', 'Content-Type': 'application/json'}
    payload = {
        "bot_id": coze_bot_id, "user_id": "quant_master", "stream": False,
        "additional_messages": [{"role": "user", "content": SEARCH_PROMPT, "content_type": "text"}]
    }

    try:
        res = requests.post('https://api.coze.cn/v3/chat', headers=headers, json=payload, timeout=60).json()
        chat_id, conversation_id = res['data']['id'], res['data']['conversation_id']
        
        for i in range(40):
            ret = requests.get(f'https://api.coze.cn/v3/chat/retrieve?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers).json()
            status = ret.get('data', {}).get('status')
            log(f"⏳ AI 正在思考中... 当前状态: {status}")
            if status == 'completed': break
            if status in ['failed', 'canceled']: return None
            time.sleep(2)

        msgs = requests.get(f'https://api.coze.cn/v3/chat/message/list?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers).json()
        content = next((m.get('content') for m in msgs.get('data', []) if m.get('type') == 'answer'), "")
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        return json.loads(json_match.group()) if json_match else None
    except Exception as e:
        log(f"❌ 抓取异常: {e}")
        return None

# ==========================================
# 5. HTML 排版引擎
# ==========================================
def format_html(data):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin: 0; padding: 15px; font-family: -apple-system, sans-serif; background-color: #f3f4f6;">
        <div style="max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 25px 20px; border-bottom: 3px solid #38bdf8;">
                <h2 style="margin: 0; font-size: 22px;">⚡ 定制投研雷达 × 🧬 医学前沿摘要</h2>
                <p style="margin: 8px 0 0 0; font-size: 13px; color: #94a3b8;">{today_str} · 学术去重版</p>
            </div>
            <div style="padding: 24px 20px;">
    """
    
    # 医学前沿
    html += """<h3 style="color: #0f172a; border-bottom: 2px solid #cbd5e1; padding-bottom: 8px;">🧬 医药学术前沿</h3>"""
    for item in data.get('medical_news', []):
        s = item.get('summary', '').replace('①', '<br><b>[团队]</b> ').replace('②', '<br><b>[问题]</b> ').replace('③', '<br><b>[方法]</b> ').replace('④', '<br><b>[突破]</b> ').replace('⑤', '<br><b>[意义]</b> ')
        html += f"""<div style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 15px; margin-bottom: 16px; border-radius: 6px;">
                    <h4 style="margin: 0 0 8px 0; color: #065f46;">{item.get('title')}</h4>
                    <div style="color: #047857; font-size: 11px; font-weight: bold; margin-bottom: 5px;">来源: {item.get('journal')}</div>
                    <p style="margin: 0; font-size: 14px; color: #166534; line-height: 1.6;">{s}</p></div>"""

    # 优选股
    html += """<h3 style="color: #0f172a; border-bottom: 2px solid #cbd5e1; padding-bottom: 8px; margin-top: 30px;">🌟 每日优选精选</h3>"""
    for rec in data.get('watchlist_recommendations', []):
        html += f"""<div style="background: linear-gradient(to right, #fffbeb, #fef3c7); border: 1px solid #fde68a; padding: 15px; border-radius: 8px; margin-bottom: 16px;">
                    <b style="color: #b45309;">{rec.get('name')} ({rec.get('ticker')})</b>
                    <p style="margin: 8px 0 0 0; font-size: 14px; color: #92400e; line-height: 1.6;">{rec.get('logic')}</p></div>"""

    # 金股分析
    html += """<h3 style="color: #0f172a; border-bottom: 2px solid #cbd5e1; padding-bottom: 8px; margin-top: 30px;">🎯 核心金股深度追踪</h3>"""
    for stock in data.get('focus_stocks', []):
        adv = stock.get('advice', '')
        c = "#ef4444" if "加" in adv or "多" in adv else ("#10b981" if "减" in adv or "空" in adv else "#f97316")
        html += f"""<div style="border: 1px solid #e2e8f0; border-radius: 10px; margin-bottom: 15px; overflow: hidden;">
                    <div style="background: #f8fafc; padding: 10px 15px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between;">
                        <b>{stock.get('name')}</b> <span style="color:white; background:{c}; padding: 2px 8px; border-radius: 4px; font-size: 12px;">{adv}</span>
                    </div>
                    <div style="padding: 12px 15px; font-size: 13px; color: #475569;">
                        <table width="100%">
                            <tr><td>📊 点位: {stock.get('key_levels')}</td><td>🌊 资金: {stock.get('fund_flow')}</td></tr>
                        </table>
                        <p style="margin: 8px 0;">📈 阶段: {stock.get('history_trend')}</p>
                        <p style="color:{c}; font-weight:bold; border-top: 1px dashed #eee; padding-top: 8px; margin: 0;">理由: {stock.get('reason')}</p>
                    </div></div>"""

    # 浪漫彩蛋
    html += f"""
            </div>
            <div style="background: linear-gradient(135deg, #fff0f3 0%, #ffe4e6 100%); padding: 30px 20px; text-align: center; border-top: 1px dashed #fda4af;">
                <div style="font-size: 24px; margin-bottom: 10px;">💌</div>
                <p style="margin: 0; font-size: 15px; color: #be123c; font-style: italic; line-height: 1.8;">"{data.get('romantic_quote')}"</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_email(body):
    log("📧 正在准备发送邮件...")
    msg = MIMEMultipart()
    msg['Subject'] = f"⚡ {today_str} 核心资产追踪 × 🧬 学术前沿"
    msg['From'], msg['To'] = sender_email, receiver_email
    msg.attach(MIMEText(body, 'html', 'utf-8'))
    with smtplib.SMTP_SSL(smtp_server, 465) as s:
        s.login(sender_email, sender_password)
        s.sendmail(sender_email, [receiver_email, cc_email], msg.as_string())
    log("✅ 邮件发送成功！")

# ==========================================
# 🚀 启动引擎
# ==========================================
if __name__ == '__main__':
    log("🎬 脚本正式开始运行...")
    report_data = fetch_news_from_coze()
    if report_data:
        email_body = format_html(report_data)
        send_email(email_body)
        save_new_history(report_data)
        log("✨ 任务成功闭环。")
    else:
        log("⚠️ AI 未返回有效数据，请检查 Coze 状态或账本是否已满。")
