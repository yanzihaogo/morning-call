import os
import requests
import json
import re
import time
import smtplib
import sys
import unicodedata
import concurrent.futures
from google import genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone

def log(message):
    bj_time = datetime.now(timezone(timedelta(hours=8))).strftime('%H:%M:%S')
    print(f"[{bj_time}] [🚀 MoE 双核系统] {message}")
    sys.stdout.flush()

# ==========================================
# 1. 统一配置中心 (DeepSeek + Gemini 双擎)
# ==========================================
deepseek_api_key = os.getenv('DEEPSEEK_API_KEY', '').strip()
gemini_api_key = os.getenv('GOOGLE_API_KEY', '').strip()

smtp_server = os.getenv('SMTP_SERVER')       
sender_email = os.getenv('SENDER_EMAIL')     
sender_password = os.getenv('SENDER_PASSWORD') 
receiver_email = "779825335@qq.com"   
cc_email = "15757699818@163.com"     

tz_bj = timezone(timedelta(hours=8))
now_bj = datetime.now(tz_bj)
today_str = now_bj.strftime('%Y年%m月%d日')

# 初始化 Gemini 客户端
gemini_client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None

# ==========================================
# 2. 账本系统 (防重复记录)
# ==========================================
HISTORY_FILE = "news_history.txt"
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

# ==========================================
# 3. 双核 Prompt 指令集
# ==========================================

# 🇨🇳 引擎 A (DeepSeek): 专注 A 股核心逻辑与国内宏观 (严谨逻辑判定)
DOMESTIC_PROMPT = f"""
今天是 {today_str}。请执行 A 股实盘与国内政策精准提取。
🚨【黑名单记录】：{past_news_list} (避开这些已报道过的新闻)
【硬性指令】：
1. 🏭【行业精要】（2-4条）：国内军工、电网、新能源真实政策与传导。
2. 🎯【金股深度追踪】：【航发科技、航天动力、航发控制、长江电力、多氟多、英维克、中国能建、中国船舶、云南锗业】。
   - 基于最新的基本面、订单和产业逻辑进行深度推演。
   - 输出红绿估值判断：看多/低位输出 #ef4444，看空/高位输出 #10b981，震荡输出 #f97316。

🚨【强制以纯 JSON 格式返回】：
{{
    "sector_news": [{{ "title": "标题", "summary": "详尽摘要" }}],
    "focus_stocks": [{{ "name": "股票名", "advice": "极简建议", "key_levels": "量价及筹码结构", "fund_flow": "资金趋势判定", "reason": "硬核基本面逻辑", "valuation_color": "必须为 #ef4444 或 #10b981 或 #f97316" }}]
}}
"""

# 🌍 引擎 B (Gemini 3.5): 专注全球外盘、医学顶刊与情感彩蛋 (去幻觉引擎)
GEMINI_PROMPT = f"""
今天是 {today_str}。请执行全球前沿探索与学术提炼。
🚨【核心指令】：
1. 全局抓取 6-8 条外盘宏观或前沿科技快讯，严禁捏造URL，必须提供搜索关键词。
2. 精读 2 篇顶级医学文献，必须包含[药物通用名]。
3. 严禁使用任何花体字或特殊 Unicode 数学字符。

🚨【强制以纯 JSON 格式返回】：
{{
    "global_news_flash": [
        {{
            "sector_tag": "板块分类",
            "time_location": "时间+地点",
            "entity": "发布机构(严禁模糊)",
            "summary": "硬核内容摘要",
            "search_keyword": "验证该新闻的精确搜索关键词"
        }}
    ],
    "medical_news": [
        {{
            "journal_and_time": "期刊名与时间",
            "drug_name": "靶向药物通用名",
            "background": "痛点",
            "method_breakthrough": "核心技术与突破数据",
            "clinical_value": "临床价值"
        }}
    ],
    "romantic_quote": "用航海的意象，写给医学科研女友的早安情话（50字内，不提具体身份，只要那种乘风破浪与守护生命交相辉映的浪漫意境）"
}}
"""

# ==========================================
# 4. 双核调度函数
# ==========================================
def fetch_domestic_data(retry=0):
    if not deepseek_api_key:
        log("⚠️ 未检测到 DEEPSEEK_API_KEY，跳过国内数据拉取。")
        return None
    if retry > 2: return None
    
    log(f"🇨🇳 启动国内主力引擎 DeepSeek (尝试 {retry+1})...")
    headers = {
        'Authorization': f'Bearer {deepseek_api_key}',
        'Content-Type': 'application/json'
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": DOMESTIC_PROMPT}],
        "response_format": {"type": "json_object"} # 强制输出 JSON 格式
    }
    
    try:
        response = requests.post('https://api.deepseek.com/chat/completions', headers=headers, json=payload, timeout=60)
        res_json = response.json()
        
        if 'choices' in res_json:
            content = res_json['choices'][0]['message']['content']
            return json.loads(content)
        else:
            time.sleep(5)
            return fetch_domestic_data(retry + 1)
    except Exception as e:
        log(f"❌ DeepSeek 报错: {str(e)}")
        time.sleep(5)
        return fetch_domestic_data(retry + 1)

def fetch_gemini_data():
    if not gemini_client: return None
    model_candidates = ['gemini-3.5-flash', 'gemini-3-flash', 'gemini-2.5-flash']
    
    for model_id in model_candidates:
        for attempt in range(3):
            log(f"🌍 正在激活国际引擎 {model_id} (尝试 {attempt+1})...")
            try:
                response = gemini_client.models.generate_content(
                    model=model_id, 
                    contents=GEMINI_PROMPT,
                    config={"response_mime_type": "application/json"}
                )
                raw_text = response.text
                if not raw_text: raise Exception("空数据")
                
                # 物理清洗花体字
                purified_text = unicodedata.normalize('NFKC', raw_text)
                return json.loads(purified_text)
            except Exception as e:
                err_msg = str(e)
                if "503" in err_msg or "429" in err_msg:
                    time.sleep(15)
                    continue
                break
    return None

# ==========================================
# 5. 跨模态数据缝合与 HTML 渲染
# ==========================================
def format_html(domestic_data, gemini_data):
    domestic_data = domestic_data or {}
    gemini_data = gemini_data or {}
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin: 0; padding: 15px; font-family: -apple-system, sans-serif; background-color: #f8fafc; color: #334155;">
        <div style="max-width: 750px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.01);">
            <div style="text-align: center; margin-bottom: 25px; padding: 20px; border-bottom: 1px solid #e2e8f0;">
                <h2 style="color: #1e40af; margin: 0; font-size: 22px;">🌤️ Daily Financial Intelligence</h2>
                <p style="color: #94a3b8; font-size: 12px; margin-top: 5px; letter-spacing: 1px;">DOMESTIC QUANT & GLOBAL ACADEMIC</p>
            </div>
            <div style="padding: 0 20px 20px 20px;">
    """
    
    # 🌍 全局高优快讯 (Gemini 提供)
    if gemini_data.get('global_news_flash'):
        html += "<h3 style='color: #1e3c72; border-bottom: 2px solid #3b82f6; padding-bottom: 6px;'>🌍 全球高优行业快讯池</h3>"
        html += "<div style='background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; margin-bottom: 20px;'>"
        for idx, news in enumerate(gemini_data.get('global_news_flash', [])):
            html += f"""
            <div style="font-size: 13.5px; line-height: 1.7; text-align: justify; margin-bottom: 12px;">
                <span style="background-color: #e2e8f0; color: #334155; padding: 2px 6px; border-radius: 4px; font-size: 11px;">{news.get('sector_tag')}</span>
                <span style="color: #64748b;">[{news.get('time_location')}]</span> 
                <b style="color: #1e40af;">{news.get('entity')}</b>: {news.get('summary')} 
                <div style="margin-top: 4px; font-size: 12px;">
                    🔍 <span style="color: #ea580c; background-color: #fff7ed; padding: 2px 5px; border-radius: 4px; border: 1px solid #ffedd5;">搜索关键词：<b>{news.get('search_keyword')}</b></span>
                </div>
            </div>
            """
        html += "</div>"

    # 🇨🇳 行业政策精要 (DeepSeek 提供)
    if domestic_data.get('sector_news'):
        html += "<h3 style='color: #1e293b; border-bottom: 2px solid #64748b; padding-bottom: 6px;'>🏭 国内重点行业逻辑与政策传导</h3>"
        for item in domestic_data.get('sector_news', []):
            html += f"<div style='margin-bottom: 15px;'><h4 style='margin: 0 0 4px 0; font-size: 14.5px;'>▪ {item.get('title')}</h4><p style='margin:0; font-size: 13px; color: #475569; line-height: 1.6;'>{item.get('summary')}</p></div>"

    # 🧬 医学学术精要 (Gemini 提供)
    if gemini_data.get('medical_news'):
        html += "<h3 style='color: #1e3c72; border-bottom: 2px solid #10b981; padding-bottom: 6px; margin-top: 25px;'>🧬 博士级学术前沿追踪</h3>"
        for med in gemini_data.get('medical_news', []):
            html += f"""
            <div style="background-color: #f0fdf4; border: 1px solid #dcfce7; padding: 18px; border-radius: 12px; margin-bottom: 15px;">
                <div style="font-size: 14.5px; color: #065f46; margin-bottom: 8px;"><b>📚 {med.get('journal_and_time')}</b></div>
                <div style="font-size: 13px; color: #166534; line-height: 1.6;">
                    • <b>研究背景：</b>{med.get('background')}<br>
                    • <b>靶点药物：</b><span style="background-color:#dcfce7; padding: 1px 4px; border-radius:3px;"><b>{med.get('drug_name')}</b></span><br>
                    • <b>方法突破：</b>{med.get('method_breakthrough')}<br>
                    • <b>转化价值：</b><b><u>{med.get('clinical_value')}</u></b>
                </div>
            </div>
            """

    # 🎯 核心资产精读 (DeepSeek 提供)
    if domestic_data.get('focus_stocks'):
        html += "<h3 style='color: #1e3c72; border-bottom: 2px solid #3b82f6; padding-bottom: 6px; margin-top: 25px;'>📈 A 股核心资产四维精读 (红绿灯版)</h3>"
        for stock in domestic_data.get('focus_stocks', []):
            v_color = stock.get('valuation_color', '#334155')
            icon = "🔴" if "#ef4444" in v_color else ("🟢" if "#10b981" in v_color else "🟠")
            
            html += f"""
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 12px; margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 6px; align-items: center;">
                    <b style="font-size: 14.5px; color: #0f172a;">{stock.get('name')}</b> 
                    <span style="background-color: {v_color}15; color: {v_color}; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 12px; border: 1px solid {v_color}30;">估值色谱</span>
                </div>
                <div style="font-size: 13px; color: #475569; line-height: 1.6;">
                    <b>量价/资金：</b>{stock.get('key_levels')} | {stock.get('fund_flow')}<br>
                    <b>盘面逻辑：</b>{stock.get('reason')}<br>
                    <b>操作建议：</b>{icon} <span style="color: {v_color}; font-weight: bold;"><u>{stock.get('advice')}</u></span>
                </div>
            </div>
            """

    # 🌸 浪漫彩蛋 (Gemini 提供)
    if gemini_data.get('romantic_quote'):
        html += f"""
        <div style="background: linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%); padding: 25px; text-align: center; border-radius: 16px; color: #be123c; font-weight: bold; margin-top: 30px; font-size: 14.5px; box-shadow: 0 4px 10px rgba(251,207,232,0.3);">
            🌸 {gemini_data.get('romantic_quote')} 💖
        </div>
        """
        
    html += """
            </div>
            <p style="text-align: center; color: #cbd5e1; font-size: 11px; padding-bottom: 20px;">&copy; 2026 SJTU Captain's Desk · DeepSeek × Gemini 双核驱动</p>
        </div>
    </body>
    </html>
    """
    return html

def send_email(html_body):
    log("📧 正在打包发送 MoE 双引擎缝合版内参...")
    msg = MIMEMultipart()
    msg['Subject'] = f"✨ {today_str} A股量化透视 × 全球学术前沿 🎀"
    msg['From'], msg['To'] = sender_email, receiver_email
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL(smtp_server, 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, [receiver_email, cc_email], msg.as_string())
        log("🎉 双核版研报已完美投递！")
    except Exception as e:
        log(f"❌ 邮件模块报错: {str(e)}")

# ==========================================
# 🚀 主控并发调度系统
# ==========================================
def main():
    log("🎬 启动 DeepSeek + Gemini 混合专家模型调度枢纽...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_domestic = executor.submit(fetch_domestic_data)
        future_gemini = executor.submit(fetch_gemini_data)
        
        domestic_data = future_domestic.result()
        gemini_data = future_gemini.result()
        
    if not domestic_data and not gemini_data:
        log("❌ 国内与国际引擎均响应失败，任务终止。")
        sys.exit(1)
        
    if not domestic_data: log("⚠️ DeepSeek A 股数据拉取失败，本期将仅包含全球新闻与医学解析。")
    if not gemini_data: log("⚠️ Gemini 国际数据拉取失败，本期将仅包含 A 股信息。")

    send_email(format_html(domestic_data, gemini_data))
    save_new_history(domestic_data)

if __name__ == '__main__':
    main()
