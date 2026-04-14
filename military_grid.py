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
coze_token = os.getenv('COZE_API_TOKEN', '').strip()
coze_bot_id = os.getenv('COZE_BOT_ID', '').strip()
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
# 3. 终极版【事实锚定+深度复盘】指令
# ==========================================
past_news_list = get_past_news()
journal_rotation = ["NEJM, Lancet", "Nature Medicine, Cell", "JAMA, BMJ", "Science Translational Medicine"][now_bj.day % 4]

SEARCH_PROMPT = f"""
今天是 {today_str}。请执行最高专业等级的学术与投研复盘任务。
🚨【黑名单记录】：{past_news_list}

【硬性指令 - 严禁虚构事实】：
1. 🏭【行业精要】（2-4条）：深度解析军工、电网、新能源政策。包含产业链上下游传导逻辑。
2. ⚖️【板块建议】：详细说明加减仓比例及宏观基本面支撑。
3. 🧬【博士级医药前沿】（2-4条）：
   - 受众：医学博士。今日轮换：{journal_rotation}。
   - 🚨【关键要求】：若涉及药物，必须括号标注通用名（Generic Name）。
   - 摘要结构（每条200字+）：①研究团队及方向；②科学痛点（标注药物通用名）；③技术方法与实验模型；④核心创新突破点；⑤未来转化应用价值。
4. 🌟【优选自选股】（1只）：深度拆解一只具备基本面反转或筹码集中的标的。
5. 🎯【金股深度追踪】（重磅板块）：详尽复盘【航发科技、航天动力、航发控制、奥瑞德、长江电力、多氟多、英维克、中国能建】。
   - 🚨【事实审计】：严禁臆测未披露的财报数据（如25年报/26一季报）。若无确切披露，转而分析其在所属产业链的竞争位、近期大宗交易动向或技术面分位。
   - 结构化复盘（每只标的不少于150字）：
     - [量价/筹码]: 测算支撑/压力位，分析近期放量收缩情况。
     - [资金面]: 追踪主力资金、北向资金或机构席位变动。
     - [基本面动态]: 分析最新已披露公告、订单或所属行业景气度。
     - [操作策略]: 给出明确的操作建议及理由。
6. 💌【专属浪漫彩蛋】：原创情话。🚨严禁出现任何金融或医学术语。

🚨【强制 JSON 格式】：
{{
    "sector_news": [{{ "title": "标题", "summary": "详尽摘要" }}],
    "sector_advice": "建议逻辑",
    "medical_news": [{{ "title": "文献名", "journal": "期刊", "summary": "①团队...②痛点...③技术...④突破...⑤价值" }}],
    "watchlist_recommendations": [{{ "name": "名称", "ticker": "代码", "logic": "详细逻辑" }}],
    "focus_stocks": [{{ "name": "名", "advice": "建议", "key_levels": "支撑/压力位", "fund_flow": "资金详情", "history_trend": "历史位置", "reason": "【四维拆解】详尽逻辑" }}],
    "romantic_quote": "浪漫情话"
}}
"""

# ==========================================
# 4. 抓取逻辑 (包含防重试与深度容错)
# ==========================================
def fetch_news_from_coze(retry=0):
    if retry > 1: return None
    log(f"🚀 启动深度采编流程 (尝试 {retry+1})...")
    headers = {'Authorization': f'Bearer {coze_token}', 'Content-Type': 'application/json'}
    payload = {
        "bot_id": coze_bot_id, "user_id": "quant_master", 
        "additional_messages": [{"role": "user", "content": SEARCH_PROMPT, "content_type": "text"}]
    }

    try:
        response = requests.post('https://api.coze.cn/v3/chat', headers=headers, json=payload, timeout=60)
        res = response.json()
        if res.get('code') != 0: return None
        
        chat_id, conversation_id = res['data']['id'], res['data']['conversation_id']
        
        for i in range(25):
            ret = requests.get(f'https://api.coze.cn/v3/chat/retrieve?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers).json()
            status = ret.get('data', {}).get('status')
            if status == 'completed':
                msgs = requests.get(f'https://api.coze.cn/v3/chat/message/list?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers).json()
                content = next((m.get('content') for m in msgs.get('data', []) if m.get('type') == 'answer'), "")
                return json.loads(re.search(r'\{.*\}', content, re.DOTALL).group())
            elif status in ['failed', 'canceled']:
                time.sleep(10)
                return fetch_news_from_coze(retry + 1)
            time.sleep(15)
        return None
    except:
        return fetch_news_from_coze(retry + 1)

# ==========================================
# 5. 专业版 HTML 排版
# ==========================================
def format_html(data):
    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin: 0; padding: 15px; font-family: sans-serif; background-color: #f3f4f6;">
        <div style="max-width: 700px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 25px 20px; border-bottom: 3px solid #3b82f6; text-align: center;">
                <h2 style="margin: 0; font-size: 20px; letter-spacing: 1.5px;">⚡ 定制投研内参 × 🧬 博士学术雷达</h2>
                <p style="margin: 8px 0 0 0; font-size: 13px; color: #94a3b8;">{today_str} · 深度同步版</p>
            </div>
            <div style="padding: 20px;">
    """
    
    # 🧬 医药学术
    html += "<h3 style='color: #0f172a; border-bottom: 2px solid #10b981; padding-bottom: 5px;'>🧬 全球医药顶刊深度追踪</h3>"
    for item in data.get('medical_news', []):
        s = item.get('summary', '').replace('①', '<br><b style="color:#059669;">[研究团队]</b> ').replace('②', '<br><b style="color:#059669;">[科学痛点]</b> ').replace('③', '<br><b style="color:#059669;">[技术方法]</b> ').replace('④', '<br><b style="color:#059669;">[核心突破]</b> ').replace('⑤', '<br><b style="color:#059669;">[转化价值]</b> ')
        html += f"<div style='background-color: #f0fdf4; border-left: 5px solid #10b981; padding: 15px; margin-bottom: 20px; border-radius: 4px;'><h4 style='margin: 0 0 5px 0; font-size: 15px; color:#064e3b;'>{item.get('title')}</h4><p style='margin:0; font-size: 13px; color:#166534; line-height:1.7; text-align:justify;'>{s}</p></div>"

    # 🎯 金股复盘
    html += "<h3 style='color: #0f172a; border-bottom: 2px solid #3b82f6; padding-bottom: 5px; margin-top: 30px;'>🎯 核心资产四维分析报告</h3>"
    for stock in data.get('focus_stocks', []):
        adv = stock.get('advice', '')
        c = "#ef4444" if "加" in adv or "多" in adv else ("#10b981" if "减" in adv or "空" in adv else "#f97316")
        html += f"""
        <div style='border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 18px; overflow: hidden;'>
            <div style='background: #f8fafc; padding: 10px 15px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center;'>
                <b style='font-size: 15px;'>{stock.get('name')}</b> 
                <span style='color:white; background:{c}; padding: 3px 10px; border-radius: 4px; font-size: 11px; font-weight:bold;'>{adv}</span>
            </div>
            <div style='padding: 15px; font-size: 13px; color: #334155;'>
                <p style='margin:0 0 10px 0;'><b>📊 点位区间:</b> {stock.get('key_levels')} | <b>🌊 资金流向:</b> {stock.get('fund_flow')}</p>
                <div style='background:#f1f5f9; padding:10px; border-radius:4px; line-height:1.7; color:#475569;'>{stock.get('reason')}</div>
            </div>
        </div>"""

    # 🏭 行业精要
    html += "<h3 style='color: #1e293b; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-top: 30px;'>🏭 重点行业政策与传导</h3>"
    for item in data.get('sector_news', []):
        html += f"<div style='margin-bottom: 15px;'><h4 style='margin: 0 0 4px 0; font-size: 14px;'>▪ {item.get('title')}</h4><p style='margin:0; font-size: 13px; color: #475569; line-height: 1.6;'>{item.get('summary')}</p></div>"

    # 💌 情话
    html += f"</div><div style='background: #fff1f2; padding: 35px 25px; text-align: center; border-top: 1px dashed #fda4af;'><p style='margin: 0; font-size: 15px; color: #be123c; font-style: italic; line-height: 1.8; letter-spacing: 1px;'>\"{data.get('romantic_quote')}\"</p></div></div></body></html>"
    return html

def send_email(body):
    log("📧 正在发送【四维深度版】研报...")
    msg = MIMEMultipart()
    msg['Subject'] = f"⚡ {today_str} 核心资产深度复盘 × 🧬 医学顶刊雷达"
    msg['From'], msg['To'] = sender_email, receiver_email
    msg.attach(MIMEText(body, 'html', 'utf-8'))
    with smtplib.SMTP_SSL(smtp_server, 465) as s:
        s.login(sender_email, sender_password)
        s.sendmail(sender_email, [receiver_email, cc_email], msg.as_string())
    log("✅ 邮件推送成功！")

if __name__ == '__main__':
    log("🎬 脚本已启动...")
    report_data = fetch_news_from_coze()
    if report_data:
        send_email(format_html(report_data))
        save_new_history(report_data)
        log("✨ 今日任务闭环完成。")
