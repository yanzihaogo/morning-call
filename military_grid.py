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
# 3. 提示词 (行业资讯+医学+1只个股+8只分析+纯文学情话)
# ==========================================
past_news_list = get_past_news()
journal_rotation = ["NEJM, Lancet", "Nature Medicine, Cell", "JAMA, BMJ", "Science Translational Medicine"][now_bj.day % 4]

SEARCH_PROMPT = f"""
今天是 {today_str}。请执行定向学术与投研任务。
🚨【绝对去重黑名单】：{past_news_list}

【硬性采编要求】：
1. 🏭【行业精要】（2-4条）：避开黑名单，复盘军工、电网、新能源最新重大政策。
2. ⚖️【板块建议】：给出上述板块仓位建议。
3. 🧬【学术医药前沿】（2-4条）：
   - 重点轮换：今日侧重 {journal_rotation}。
   - 摘要结构（严格4-6句连续段落）：①团队及方向；②试图解决的科学问题；③核心技术/方法；④相比既有研究的核心突破；⑤潜在医学价值。
4. 🌟【优选自选股】（仅限1只）：精选【1只】最优质个股，给出推荐逻辑。
5. 🎯【金股追踪】：必须分析【航发科技、航天动力、航发控制、奥瑞德、长江电力、多氟多、英维克、中国能建】。
   - 给出资金面、支撑/压力位、操作建议。
6. 💌【专属浪漫彩蛋】：原创文艺深情情话。
   - 🚨【禁令】：严禁出现股票、均线、成交量等任何金融术语！

🚨【强制 JSON 格式】：
{{
    "sector_news": [{{ "title": "标题", "summary": "摘要" }}],
    "sector_advice": "建议",
    "medical_news": [{{ "title": "标题", "journal": "来源", "summary": "摘要" }}],
    "watchlist_recommendations": [{{ "name": "名称", "ticker": "代码", "logic": "逻辑" }}],
    "focus_stocks": [{{ "name": "名", "advice": "建议", "key_levels": "点位", "fund_flow": "资金", "history_trend": "位置", "reason": "理由" }}],
    "romantic_quote": "浪漫情话"
}}
"""

# ==========================================
# 4. 抓取逻辑 (静默轮询模式)
# ==========================================
def fetch_news_from_coze():
    log("🚀 启动 Coze AI 采编（包含行业、学术与个股追踪）...")
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
        
        # 静默等待逻辑
        log("⏳ AI 正在深度处理数据，请稍候（仅显示一行状态）...")
        for i in range(30):
            ret_res = requests.get(f'https://api.coze.cn/v3/chat/retrieve?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers).json()
            status = ret_res.get('data', {}).get('status')
            if status == 'completed':
                log("✅ 数据处理完成！")
                break
            elif status in ['failed', 'canceled']:
                log(f"❌ 任务中断: {status}")
                return None
            time.sleep(10) # 10秒检查一次
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
# 5. HTML 排版引擎 (全模块回归版)
# ==========================================
def format_html(data):
    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin: 0; padding: 15px; font-family: sans-serif; background-color: #f3f4f6;">
        <div style="max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 25px 20px; border-bottom: 3px solid #38bdf8;">
                <h2 style="margin: 0; font-size: 20px;">⚡ 定制投研内参 × 🧬 医学前沿雷达</h2>
                <p style="margin: 6px 0 0 0; font-size: 13px; color: #94a3b8;">{today_str} · 学术去重完全体</p>
            </div>
            <div style="padding: 20px;">
    """
    
    # 🏭 行业精要
    html += "<h3 style='color: #1e293b; border-bottom: 1px solid #eee; padding-bottom: 5px;'>🏭 行业精要与政策复盘</h3>"
    for item in data.get('sector_news', []):
        summary = item.get('summary', '').replace('🎯 逻辑：', '<br><b style="color: #0284c7;">🎯 逻辑：</b>')
        html += f"<div style='margin-bottom: 15px;'><h4 style='margin: 0 0 5px 0; font-size: 15px;'>▪ {item.get('title')}</h4><p style='margin:0; font-size: 13px; color: #475569; line-height: 1.6;'>{summary}</p></div>"
    
    html += f"<div style='background-color: #fff1f2; padding: 10px; border-radius: 4px; margin-bottom: 25px; font-size: 13px; color: #be123c;'><b>⚖️ 板块仓位建议：</b>{data.get('sector_advice')}</div>"

    # 🧬 医药学术
    html += "<h3 style='color: #1e293b; border-bottom: 1px solid #eee; padding-bottom: 5px;'>🧬 全球医药学术前沿</h3>"
    for item in data.get('medical_news', []):
        s = item.get('summary', '').replace('①', '<br><b>[团队]</b> ').replace('②', '<br><b>[问题]</b> ').replace('③', '<br><b>[方法]</b> ').replace('④', '<br><b>[突破]</b> ').replace('⑤', '<br><b>[意义]</b> ')
        html += f"<div style='background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 12px; margin-bottom: 15px; border-radius: 4px;'><h4 style='margin: 0 0 5px 0; font-size: 14px; color: #065f46;'>{item.get('title')}</h4><p style='margin: 0; font-size: 12px; color: #166534; line-height: 1.6;'>{s}</p></div>"

    # 🌟 优选自选股
    html += "<h3 style='color: #1e293b; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-top: 25px;'>🌟 每日优选精选 (仅此一只)</h3>"
    for rec in data.get('watchlist_recommendations', []):
        html += f"<div style='background: #fffbeb; border: 1px solid #fde68a; padding: 12px; border-radius: 8px; margin-bottom: 20px;'><b style='color: #b45309; font-size: 15px;'>{rec.get('name')} ({rec.get('ticker')})</b><p style='margin: 5px 0 0 0; font-size: 13px; color: #92400e; line-height: 1.6;'>{rec.get('logic')}</p></div>"

    # 🎯 金股深度追踪 (包含中国能建)
    html += "<h3 style='color: #1e293b; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-top: 25px;'>🎯 核心资产量价复盘</h3>"
    for stock in data.get('focus_stocks', []):
        adv = stock.get('advice', '')
        c = "#ef4444" if "加" in adv or "多" in adv else ("#10b981" if "减" in adv or "空" in adv else "#f97316")
        html += f"<div style='border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 12px; overflow: hidden;'><div style='background: #f8fafc; padding: 8px 12px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center;'><b style='font-size: 13px;'>{stock.get('name')}</b> <span style='color:white; background:{c}; padding: 2px 6px; border-radius: 4px; font-size: 10px;'>{adv}</span></div><div style='padding: 10px 12px; font-size: 12px; color: #475569;'><p style='margin: 0;'>📊 点位: {stock.get('key_levels')} | 🌊 资金: {stock.get('fund_flow')}</p><p style='color:{c}; font-weight:bold; border-top: 1px dashed #eee; padding-top: 6px; margin: 6px 0 0 0;'>理由: {stock.get('reason')}</p></div></div>"

    # 💌 浪漫彩蛋
    html += f"</div><div style='background: #fff1f2; padding: 25px 20px; text-align: center;'><p style='margin: 0; font-size: 15px; color: #be123c; font-style: italic; line-height: 1.8;'>\"{data.get('romantic_quote')}\"</p></div></div></body></html>"
    return html

def send_email(body):
    msg = MIMEMultipart()
    msg['Subject'] = f"⚡ {today_str} 核心资产追踪 × 🧬 学术前沿"
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
        log("✨ 今日日报已完整闭环。")
    else:
        log("⚠️ 未能生成完整报告。")
