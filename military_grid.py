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

# 实时日志输出，方便在 GitHub Actions 监控
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
    titles = [i.get('title') for i in data.get('sector_news', []) + data.get('medical_news', []) if i.get('title')]
    if not titles: return
    lines = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
    lines.extend(titles)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        for l in lines[-100:]: f.write(l + "\n")

# ==========================================
# 3. 博士级学术与全方位投研指令
# ==========================================
past_news_list = get_past_news()
journal_rotation = ["NEJM, Lancet", "Nature Medicine, Cell", "JAMA, BMJ", "Science Translational Medicine"][now_bj.day % 4]

SEARCH_PROMPT = f"""
今天是 {today_str}。请执行最高专业等级的学术复盘与多维投研任务。
🚨【绝对去重黑名单】：{past_news_list}

【硬性指令 - 严禁虚构事实】：
1. 🏭【行业精要】（2-4条）：深度解析军工、电网、新能源及中国船舶产业链政策逻辑。
2. ⚖️【板块建议】：详细说明仓位比例及驱动力。
3. 🧬【医学博士前沿】（2-4条）：
   - 受众背景：医学博士。今日轮换顶刊：{journal_rotation}。
   - 🚨【关键要求】：若研究涉及具体药物干预，必须在[科学问题]或[技术方法]的描述中，括号标注具体的药物通用名（Generic Name）。
   - 结构（每条不少于250字）：①研究团队及方向；②科学痛点（需标药物名）；③技术方法与实验模型；④核心创新突破点（禁止空泛）；⑤未来转化临床意义。
4. 🌟【优选自选股】（1只）：精选基本面爆发或机构调仓标的。
5. 🎯【资产四维复盘】：必须详尽分析【航发科技、航天动力、航发控制、长江电力、多氟多、英维克、中国能建、中国船舶、云南锗业】。
   - 🚨【严禁脑补】：严禁臆测未披露财报。若无公告，重点分析行业格局、订单预期及大宗异动。
   - 结构（每只标的不少于180字）：
     - [量价分析]: 测算支撑位/压力位，分析近期K线特征。
     - [资金面]: 追踪主力、北向及席位变动。
     - [基本面复盘]: 结合所属产业链地位及最新行业数据。
     - [策略建议]: 明确操作点位与持有逻辑。
6. 💌【专属浪漫彩蛋】：原创情话。🚨严禁出现任何金融、交易、K线或医学术语。

🚨【强制 JSON 格式】：
{{
    "sector_news": [{{ "title": "标题", "summary": "摘要" }}],
    "sector_advice": "建议逻辑",
    "medical_news": [{{ "title": "文献名", "journal": "来源", "summary": "①团队...②痛点...③技术...④突破...⑤价值" }}],
    "watchlist_recommendations": [{{ "name": "名称", "ticker": "代码", "logic": "详细逻辑" }}],
    "focus_stocks": [{{ "name": "名", "advice": "建议", "key_levels": "点位", "fund_flow": "资金", "history_trend": "位置", "reason": "【四维拆解】详尽逻辑" }}],
    "romantic_quote": "浪漫情话"
}}
"""

# ==========================================
# 4. 抓取逻辑 (包含断点重试与静默轮询)
# ==========================================
def fetch_news_from_coze(retry=0):
    if retry > 1: return None
    log(f"🚀 启动【博士版】采编流程 (尝试 {retry+1})...")
    headers = {'Authorization': f'Bearer {coze_token}', 'Content-Type': 'application/json'}
    payload = {{ "bot_id": coze_bot_id, "user_id": "quant_master", "additional_messages": [{"role": "user", "content": SEARCH_PROMPT, "content_type": "text"}] }}

    try:
        response = requests.post('https://api.coze.cn/v3/chat', headers=headers, json=payload, timeout=60)
        res = response.json()
        if res.get('code') != 0: 
            log(f"❌ API 报错: {res.get('msg')}")
            return None
        
        chat_id, conversation_id = res['data']['id'], res['data']['conversation_id']
        log("⏳ AI 正在深度处理数据（预计 2-4 分钟），请稍候...")
        
        for i in range(35): # 延长等待至约 7 分钟
            ret = requests.get(f'https://api.coze.cn/v3/chat/retrieve?chat_id={{chat_id}}&conversation_id={{conversation_id}}', headers=headers).json()
            status = ret.get('data', {{}}).get('status')
            if status == 'completed':
                log("✅ 生成成功！")
                msgs = requests.get(f'https://api.coze.cn/v3/chat/message/list?chat_id={{chat_id}}&conversation_id={{conversation_id}}', headers=headers).json()
                content = next((m.get('content') for m in msgs.get('data', []) if m.get('type') == 'answer'), "")
                return json.loads(re.search(r'\{{.*\}}', content, re.DOTALL).group())
            elif status in ['failed', 'canceled']:
                log(f"⚠️ 状态异常 ({{status}})，准备重试...")
                time.sleep(10)
                return fetch_news_from_coze(retry + 1)
            time.sleep(12)
        return None
    except Exception as e:
        log(f"❌ 运行捕获异常: {{e}}")
        return fetch_news_from_coze(retry + 1)

# ==========================================
# 5. HTML 排版引擎
# ==========================================
def format_html(data):
    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin: 0; padding: 15px; font-family: sans-serif; background-color: #f3f4f6;">
        <div style="max-width: 750px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #1e293b 0%, #334155 100%); color: #ffffff; padding: 25px 20px; border-bottom: 3px solid #3b82f6; text-align: center;">
                <h2 style="margin: 0; font-size: 20px; letter-spacing: 1.5px;">⚡ 博士级定制内参 × 🧬 学术前沿雷达</h2>
                <p style="margin: 8px 0 0 0; font-size: 13px; color: #94a3b8;">{today_str} · 专业版深度追踪</p>
            </div>
            <div style="padding: 20px;">
    """
    
    # 🧬 医药学术
    html += "<h3 style='color: #0f172a; border-bottom: 2px solid #10b981; padding-bottom: 5px;'>🧬 全球医药顶刊学术前沿</h3>"
    for item in data.get('medical_news', []):
        s = item.get('summary', '').replace('①', '<br><b style="color:#059669;">[研究团队]</b> ').replace('②', '<br><b style="color:#059669;">[科学痛点]</b> ').replace('③', '<br><b style="color:#059669;">[技术方法]</b> ').replace('④', '<br><b style="color:#059669;">[核心突破]</b> ').replace('⑤', '<br><b style="color:#059669;">[转化价值]</b> ')
        html += f"<div style='background-color: #f0fdf4; border-left: 5px solid #10b981; padding: 15px; margin-bottom: 20px; border-radius: 4px;'><h4 style='margin: 0 0 5px 0; font-size: 15px; color:#064e3b;'>{item.get('title')}</h4><div style='color: #047857; font-size: 11px; font-weight: bold;'>来源: {item.get('journal')}</div><p style='margin: 10px 0 0 0; font-size: 13px; color:#166534; line-height:1.7; text-align:justify;'>{s}</p></div>"

    # 🎯 金股分析
    html += "<h3 style='color: #0f172a; border-bottom: 2px solid #3b82f6; padding-bottom: 5px; margin-top: 30px;'>🎯 核心资产四维深度报告</h3>"
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
                <p style='margin:0 0 10px 0;'><b>📊 点位测算:</b> {stock.get('key_levels')} | <b>🌊 资金流向:</b> {stock.get('fund_flow')}</p>
                <div style='background:#f1f5f9; padding:10px; border-radius:4px; line-height:1.7; color:#475569;'>{stock.get('reason')}</div>
            </div>
        </div>"""

    # 💌 浪漫彩蛋
    html += f"</div><div style='background: #fff1f2; padding: 40px 25px; text-align: center; border-top: 1px dashed #fda4af;'><p style='margin: 0; font-size: 16px; color: #be123c; font-style: italic; line-height: 1.8;'>\"{data.get('romantic_quote')}\"</p></div></div></body></html>"
    return html

def send_email(body):
    msg = MIMEMultipart()
    msg['Subject'] = f"⚡ {today_str} 核心资产深度复盘 × 🧬 医学顶刊雷达"
    msg['From'], msg['To'] = sender_email, receiver_email
    msg.attach(MIMEText(body, 'html', 'utf-8'))
    with smtplib.SMTP_SSL(smtp_server, 465) as s:
        s.login(sender_email, sender_password)
        s.sendmail(sender_email, [receiver_email, cc_email], msg.as_string())
    log("✅ 博士专版邮件推送成功！")

if __name__ == '__main__':
    log("🎬 脚本正式启动...")
    report_data = fetch_news_from_coze()
    if report_data:
        send_email(format_html(report_data))
        save_new_history(report_data)
        log("✨ 任务成功闭环。")
