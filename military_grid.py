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
# 3. 强化版学术与投研指令
# ==========================================
past_news_list = get_past_news()
journal_rotation = ["NEJM, Lancet", "Nature Medicine, Cell", "JAMA, BMJ", "Science Translational Medicine"][now_bj.day % 4]

SEARCH_PROMPT = f"""
今天是 {today_str}。请执行定向学术与投研任务。
🚨【绝对去重黑名单】：{past_news_list}

【硬性采编要求】：
1. 🏭【行业精要】（2-4条）：复盘军工、电网、新能源最新重大政策。
2. ⚖️【板块建议】：给出上述板块仓位建议。
3. 🧬【学术级医药前沿】（2-4条）：
   - 重点轮换：今日侧重 {journal_rotation}。
   - 🚨【团队与来源硬性要求】：必须写出具体的研究机构名称（如“哈佛大学医学院”、“西湖大学”）及期刊全称。严禁使用“某研究团队”、“研究人员”等模糊表述。
   - 摘要结构（严格顺序表达）：
     ① 研究团队：写出具体机构名称及团队研究方向。
     ② 研究问题：说明该研究试图解决什么科学或临床问题。
     ③ 技术方法：说明研究采用的核心技术、实验方法或治疗策略。
     ④ 核心突破：说明相比既有研究的核心创新点，严禁空泛。
     ⑤ 潜在意义：说明研究的潜在医学价值或应用场景。
4. 🌟【优选自选股】（仅限1只）：精选【1只】最优质个股，给出推荐逻辑。
5. 🎯【金股追踪】：深度分析【航发科技、航天动力、航发控制、奥瑞德、长江电力、多氟多、英维克、中国能建】。
   - 给出资金面动向、关键点位（支撑/压力）、历史位置及操作建议。
6. 💌【专属浪漫情话】：原创文艺情话。严禁出现股票、均线、指标等任何金融术语。

🚨【强制 JSON 格式】：
{{
    "sector_news": [{{ "title": "标题", "summary": "摘要" }}],
    "sector_advice": "建议内容",
    "medical_news": [{{ 
        "title": "文献标题", 
        "journal": "期刊全称(必填)", 
        "summary": "①研究团队...②研究问题...③技术方法...④核心突破...⑤潜在意义。" 
    }}],
    "watchlist_recommendations": [{{ "name": "名称", "ticker": "代码", "logic": "逻辑" }}],
    "focus_stocks": [{{ "name": "名", "advice": "建议", "key_levels": "点位", "fund_flow": "资金", "history_trend": "阶段", "reason": "理由" }}],
    "romantic_quote": "文艺情话"
}}
"""

# ==========================================
# 4. 抓取逻辑
# ==========================================
def fetch_news_from_coze():
    log("🚀 启动 Coze AI 采编（增强型学术搜索模式）...")
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
        
        log("⏳ AI 正在深度检索文献与行情，请稍候...")
        for i in range(30):
            ret_res = requests.get(f'https://api.coze.cn/v3/chat/retrieve?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers).json()
            status = ret_res.get('data', {}).get('status')
            if status == 'completed':
                log("✅ 数据处理完成！")
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
# 5. HTML 排版引擎
# ==========================================
def format_html(data):
    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin: 0; padding: 15px; font-family: sans-serif; background-color: #f3f4f6;">
        <div style="max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 25px 20px; border-bottom: 3px solid #38bdf8;">
                <h2 style="margin: 0; font-size: 20px;">⚡ 定制投研内参 × 🧬 医学前沿雷达</h2>
                <p style="margin: 6px 0 0 0; font-size: 13px; color: #94a3b8;">{today_str} · 学术增强版</p>
            </div>
            <div style="padding: 20px;">
    """
    
    # 🧬 医药学术部分 - 强化显示来源和团队
    html += "<h3 style='color: #1e293b; border-bottom: 1px solid #eee; padding-bottom: 5px;'>🧬 全球医药学术前沿</h3>"
    for item in data.get('medical_news', []):
        # 视觉增强：给每个部分加个粗体标签
        s = item.get('summary', '').replace('①', '<br><b style="color:#10b981;">[研究团队]</b> ')\
                                   .replace('②', '<br><b style="color:#10b981;">[科学问题]</b> ')\
                                   .replace('③', '<br><b style="color:#10b981;">[技术方法]</b> ')\
                                   .replace('④', '<br><b style="color:#10b981;">[核心突破]</b> ')\
                                   .replace('⑤', '<br><b style="color:#10b981;">[潜在意义]</b> ')
        
        html += f"""
        <div style='background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 12px; margin-bottom: 15px; border-radius: 4px;'>
            <h4 style='margin: 0 0 5px 0; font-size: 15px;'>{item.get('title')}</h4>
            <div style='color: #047857; font-size: 12px; font-weight: bold; background: #d1fae5; display: inline-block; padding: 2px 8px; border-radius: 10px; margin-bottom: 5px;'>
                来源: {item.get('journal', '未知期刊')}
            </div>
            <p style='margin: 8px 0 0 0; font-size: 13px; color: #166534; line-height: 1.6;'>{s}</p>
        </div>"""

    # 🌟 优选自选股
    html += "<h3 style='color: #1e293b; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-top: 25px;'>🌟 每日优选精选</h3>"
    for rec in data.get('watchlist_recommendations', []):
        html += f"<div style='background: #fffbeb; border: 1px solid #fde68a; padding: 12px; border-radius: 8px; margin-bottom: 20px;'><b style='color: #b45309; font-size: 15px;'>{rec.get('name')} ({rec.get('ticker', 'N/A')})</b><p style='margin: 5px 0 0 0; font-size: 13px; color: #92400e;'>{rec.get('logic')}</p></div>"

    # 🎯 金股追踪
    html += "<h3 style='color: #1e293b; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-top: 25px;'>🎯 核心资产量价复盘</h3>"
    for stock in data.get('focus_stocks', []):
        adv = stock.get('advice', '')
        c = "#ef4444" if "加" in adv or "多" in adv else ("#10b981" if "减" in adv or "空" in adv else "#f97316")
        html += f"<div style='border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 12px; overflow: hidden;'><div style='background: #f8fafc; padding: 8px 12px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center;'><b style='font-size: 13px;'>{stock.get('name')}</b> <span style='color:white; background:{c}; padding: 2px 6px; border-radius: 4px; font-size: 10px;'>{adv}</span></div><div style='padding: 10px 12px; font-size: 12px; color: #475569;'><p style='margin: 0;'>📊 点位: {stock.get('key_levels')} | 🌊 资金: {stock.get('fund_flow')}</p><p style='color:{c}; font-weight:bold; border-top: 1px dashed #eee; padding-top: 6px; margin: 6px 0 0 0;'>理由: {stock.get('reason')}</p></div></div>"

    # 💌 浪漫彩蛋
    html += f"</div><div style='background: linear-gradient(135deg, #fff1f2 0%, #ffe4e6 100%); padding: 30px 20px; text-align: center;'><p style='margin: 0; font-size: 15px; color: #be123c; font-style: italic; line-height: 1.8;'>\"{data.get('romantic_quote', '今天也要开心。')}\"</p></div></div></body></html>"
    return html

def send_email(body):
    msg = MIMEMultipart()
    msg['Subject'] = f"⚡ {today_str} 核心资产追踪 × 🧬 学术增强版"
    msg['From'], msg['To'] = sender_email, receiver_email
    msg.attach(MIMEText(body, 'html', 'utf-8'))
    with smtplib.SMTP_SSL(smtp_server, 465) as s:
        s.login(sender_email, sender_password)
        s.sendmail(sender_email, [receiver_email, cc_email], msg.as_string())
    log("✅ 邮件推送成功！")

if __name__ == '__main__':
    log("🎬 脚本正式启动...")
    report_data = fetch_news_from_coze()
    if report_data:
        send_email(format_html(report_data))
        save_new_history(report_data)
        log("✨ 任务完成。")
    else:
        log("⚠️ 未能生成报告。")
