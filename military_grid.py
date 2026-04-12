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
# 3. 增强版【博士级】指令
# ==========================================
past_news_list = get_past_news()
journal_rotation = ["NEJM, Lancet", "Nature Medicine, Cell", "JAMA, BMJ", "Science Translational Medicine"][now_bj.day % 4]

SEARCH_PROMPT = f"""
今天是 {today_str}。执行【博士级】学术与投研任务。
🚨【黑名单】：{past_news_list}

【硬性指令】：
1. 🏭【行业精要】（2-4条）：深度复盘军工、电网、新能源政策。
2. ⚖️【板块建议】：给出仓位建议。
3. 🧬【学术医药前沿】（2-4条）：
   - 受众：医学博士。今日侧重 {journal_rotation}。
   - 🚨【药物通用名锚定】：必须在[研究问题]或[技术方法]中括号标注具体的药物通用名。
   - 摘要结构（每条不少于200字）：①团队及方向；②科学/临床痛点；③技术方法（含模型/药物）；④核心创新突破；⑤转化意义。
4. 🌟【优选自选股】（仅限1只）：精选优质标的及逻辑。
5. 🎯【资产深度追踪】：详尽分析【航发科技、航天动力、航发控制、奥瑞德、长江电力、多氟多、英维克、中国能建】。
6. 💌【专属浪漫彩蛋】：原创文艺情话。🚨绝对严禁任何金融或医学术语。

🚨【强制 JSON 格式】：
{{
    "sector_news": [{{ "title": "标题", "summary": "摘要" }}],
    "sector_advice": "建议",
    "medical_news": [{{ "title": "标题", "journal": "来源", "summary": "长摘要" }}],
    "watchlist_recommendations": [{{ "name": "名", "ticker": "码", "logic": "逻辑" }}],
    "focus_stocks": [{{ "name": "名", "advice": "建议", "key_levels": "点位", "fund_flow": "资金", "history_trend": "位置", "reason": "理由" }}],
    "romantic_quote": "文艺情话"
}}
"""

# ==========================================
# 4. 抓取逻辑 (包含自动重试)
# ==========================================
def fetch_news_from_coze(retry_count=0):
    if retry_count > 1: return None # 最多重试一次
    
    log(f"🚀 发起任务 (尝试次数: {retry_count + 1})...")
    headers = {'Authorization': f'Bearer {coze_token}', 'Content-Type': 'application/json'}
    payload = {
        "bot_id": coze_bot_id, "user_id": "quant_master", "stream": False,
        "additional_messages": [{"role": "user", "content": SEARCH_PROMPT, "content_type": "text"}]
    }

    try:
        response = requests.post('https://api.coze.cn/v3/chat', headers=headers, json=payload, timeout=60)
        res = response.json()
        if res.get('code') != 0:
            log(f"❌ API 发起失败: {res.get('msg')}")
            return None

        chat_id, conversation_id = res['data']['id'], res['data']['conversation_id']
        
        log("⏳ 正在同步 AI 状态...")
        for i in range(25): # 等待 6 分钟
            ret_res = requests.get(f'https://api.coze.cn/v3/chat/retrieve?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers, timeout=30).json()
            status = ret_res.get('data', {}).get('status')
            
            if status == 'completed':
                log("✅ 生成成功！")
                msgs = requests.get(f'https://api.coze.cn/v3/chat/message/list?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers, timeout=30).json()
                content = next((m.get('content') for m in msgs.get('data', []) if m.get('type') == 'answer'), "")
                return json.loads(re.search(r'\{.*\}', content, re.DOTALL).group())
            
            elif status in ['failed', 'canceled']:
                log(f"⚠️ 任务异常中断 ({status})，准备重新发起...")
                time.sleep(10)
                return fetch_news_from_coze(retry_count + 1)
            
            time.sleep(15)
        return None
    except Exception as e:
        log(f"❌ 运行异常: {str(e)}")
        return fetch_news_from_coze(retry_count + 1)

# ==========================================
# 5. HTML 排版与发送 (博士版)
# ==========================================
def format_html(data):
    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin: 0; padding: 15px; font-family: sans-serif; background-color: #f3f4f6;">
        <div style="max-width: 700px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #1e293b 0%, #334155 100%); color: #ffffff; padding: 25px 20px; border-bottom: 3px solid #3b82f6;">
                <h2 style="margin: 0; font-size: 20px;">⚡ 定制投研内参 × 🧬 博士学术雷达</h2>
                <p style="margin: 6px 0 0 0; font-size: 13px; color: #94a3b8;">{today_str} · 强化稳定性版</p>
            </div>
            <div style="padding: 20px;">
    """
    # 医药学术
    html += "<h3 style='color: #1e293b; border-bottom: 1px solid #eee; padding-bottom: 5px;'>🧬 全球医药顶刊学术前沿</h3>"
    for item in data.get('medical_news', []):
        s = item.get('summary', '').replace('①', '<br><b style="color:#059669;">[团队]</b> ').replace('②', '<br><b style="color:#059669;">[问题]</b> ').replace('③', '<br><b style="color:#059669;">[方法]</b> ').replace('④', '<br><b style="color:#059669;">[突破]</b> ').replace('⑤', '<br><b style="color:#059669;">[转化]</b> ')
        html += f"<div style='background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 12px; margin-bottom: 15px; border-radius: 4px;'><h4 style='margin: 0 0 5px 0; font-size: 14px;'>{item.get('title')}</h4><p style='font-size: 12px; color: #166534; line-height: 1.7;'>{s}</p></div>"
    # 资产追踪
    html += "<h3 style='color: #1e293b; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-top: 25px;'>🎯 资产深度追踪</h3>"
    for stock in data.get('focus_stocks', []):
        adv = stock.get('advice', '')
        c = "#ef4444" if "加" in adv or "多" in adv else ("#10b981" if "减" in adv or "空" in adv else "#f97316")
        html += f"<div style='border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 12px; overflow: hidden;'><div style='background: #f8fafc; padding: 8px 12px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between;'><b>{stock.get('name')}</b> <span style='color:white; background:{c}; padding: 2px 8px; border-radius: 4px; font-size: 11px;'>{adv}</span></div><div style='padding: 10px 12px; font-size: 12px; color: #475569;'><p style='margin: 0;'>点位: {stock.get('key_levels')} | 资金: {stock.get('fund_flow')}</p><p style='color:{c}; font-weight:bold; border-top: 1px dashed #eee; padding-top: 6px; margin: 6px 0 0 0;'>逻辑: {stock.get('reason')}</p></div></div>"
    # 浪漫彩蛋
    html += f"</div><div style='background: #fff1f2; padding: 30px 20px; text-align: center;'><p style='margin: 0; font-size: 14px; color: #be123c; font-style: italic; line-height: 1.8;'>\"{data.get('romantic_quote')}\"</p></div></div></body></html>"
    return html

def send_email(body):
    msg = MIMEMultipart()
    msg['Subject'] = f"⚡ {today_str} 核心资产追踪 × 🧬 医学顶刊雷达"
    msg['From'], msg['To'] = sender_email, receiver_email
    msg.attach(MIMEText(body, 'html', 'utf-8'))
    with smtplib.SMTP_SSL(smtp_server, 465) as s:
        s.login(sender_email, sender_password)
        s.sendmail(sender_email, [receiver_email, cc_email], msg.as_string())
    log("✅ 邮件推送成功！")

if __name__ == '__main__':
    log("🎬 启动程序...")
    report_data = fetch_news_from_coze()
    if report_data:
        send_email(format_html(report_data))
        save_new_history(report_data)
        log("✨ 任务完成。")
