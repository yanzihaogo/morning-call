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

# 强制实时输出日志
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
# 3. 增强版指令 (略微精简个股以保稳定性)
# ==========================================
past_news = get_past_news()
SEARCH_PROMPT = f"""
今天是 {today_str}。执行医学博士级学术与投研任务。
🚨【去重黑名单】：{past_news}

【指令】：
1. 🏭【行业精要】：分析军工、船舶、电网、新能源最新政策。
2. 🧬【医学博士前沿】（2-3条）：必须标注药物通用名(Generic Name)。每条200字+，含团队、痛点、方法、突破、价值。
3. 🎯【资产深度复盘】：追踪【航发科技、航天动力、长江电力、英维克、中国能建、中国船舶、云南锗业】。
   - 每只不少于150字。严禁虚构。
4. 💌【专属浪漫彩蛋】：原创情话。严禁金融词汇。

🚨【强制 JSON 格式】：
{{
    "sector_news": [], "sector_advice": "", "medical_news": [], "watchlist_recommendations": [], "focus_stocks": [], "romantic_quote": ""
}}
"""

# ==========================================
# 4. 抓取逻辑 (增加原始错误透传)
# ==========================================
def fetch_news_from_coze(retry=0):
    if retry > 1: return None
    log(f"🚀 发起 API 请求 (第 {retry+1} 次尝试)...")
    headers = {'Authorization': f'Bearer {coze_token}', 'Content-Type': 'application/json'}
    payload = {
        "bot_id": coze_bot_id, 
        "user_id": "quant_master", 
        "additional_messages": [{"role": "user", "content": SEARCH_PROMPT, "content_type": "text"}]
    }

    try:
        response = requests.post('https://api.coze.cn/v3/chat', headers=headers, json=payload, timeout=60)
        res = response.json()
        if res.get('code') != 0: 
            log(f"❌ API 握手失败: {res.get('msg')} (代码: {res.get('code')})")
            return None
        
        chat_id, conv_id = res['data']['id'], res['data']['conversation_id']
        
        for i in range(30):
            ret_res = requests.get(f'https://api.coze.cn/v3/chat/retrieve?chat_id={chat_id}&conversation_id={conv_id}', headers=headers).json()
            status = ret_res.get('data', {}).get('status')
            
            if status == 'completed':
                log("✅ AI 生成完毕！正在提取内容...")
                msgs = requests.get(f'https://api.coze.cn/v3/chat/message/list?chat_id={chat_id}&conversation_id={conv_id}', headers=headers).json()
                content = next((m.get('content') for m in msgs.get('data', []) if m.get('type') == 'answer'), "")
                return json.loads(re.search(r'\{.*\}', content, re.DOTALL).group())
            
            elif status in ['failed', 'canceled']:
                error_info = ret_res.get('data', {}).get('last_error', {})
                log(f"❌ AI 任务失败！具体原因: {error_info.get('msg', '未知错误')} (代码: {error_info.get('code', 'N/A')})")
                time.sleep(10)
                return fetch_news_from_coze(retry + 1)
            
            if i % 5 == 0: log(f"⏳ AI 正在深度处理中... 状态: {status}")
            time.sleep(15)
        return None
    except Exception as e:
        log(f"❌ 运行异常: {e}")
        return fetch_news_from_coze(retry + 1)

# (format_html 和 send_email 模块保持不变)
def format_html(data):
    # 此处省略已有的 HTML 排版逻辑...
    return "<html>...</html>" # 实际代码中请保留之前的 format_html

def send_email(body):
    # 此处省略已有的发送邮件逻辑...
    log("✅ 邮件发送成功！")

if __name__ == '__main__':
    log("🎬 脚本已启动...")
    report_data = fetch_news_from_coze()
    if report_data:
        send_email(format_html(report_data))
        save_new_history(report_data)
        log("✨ 今日任务完美闭环。")
    else:
        log("❌ 最终未能生成有效报告。")
        sys.exit(1) # 关键改动：强制让 GitHub Actions 变红报警
