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
# 1. 统一配置中心 (Coze + Gemini 双擎)
# ==========================================
coze_token = os.getenv('COZE_API_TOKEN', '').strip()
coze_bot_id = os.getenv('COZE_BOT_ID', '').strip()
gemini_api_key = os.getenv('GOOGLE_API_KEY', '').strip()

smtp_server = os.getenv('SMTP_SERVER')       
sender_email = os.getenv('SENDER_EMAIL')     
sender_password = os.getenv('SENDER_PASSWORD') 
receiver_email = "779825335@qq.com"   
cc_email = "15757699818@163.com"     

tz_bj = timezone(timedelta(hours=8))
now_bj = datetime.now(tz_bj)
today_str = now_bj.strftime('%Y年%m月%d日')

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
COZE_PROMPT = f"""
今天是 {today_str}。请执行 A 股重点行业与三大核心标的的精准深度研判。
🚨【历史已报过滤】：{past_news_list}

【执行要求】：
1. 🏭【行业精要】（2-4条）：聚焦国内半导体晶圆制造、新能源新材料、资本市场改革与大金融政策传导。
2. 🎯【金股深度追踪】：严格仅追踪【多氟多】、【华虹宏力】、【中信证券】三只核心标的，剔除其余无关个股。
   - 【标的1：多氟多】：深入分析六氟磷酸锂价格周期、电子级氟化氢/氢氟酸产能扩张、储能及钠电新材料业务兑现度与量价博弈。
   - 【标的2：华虹宏力（华虹公司/华虹半导体）】：深入分析特色工艺晶圆代工产能利用率、功率器件/MCU/CIS汽车电子需求、12英寸晶圆厂扩产进度与PB估值修复空间。
   - 【标的3：中信证券】：深入分析全市场成交量中枢、券商并购重组预期、资本市场逆周期调节政策弹性、机构业务与财富管理估值中枢。
   - 请调用联网搜索，获取这三只标的的最新真实估值中枢、关键技术价格区间及基本面重大动向。
   - 严禁输出“工具接口异常”等报错字样；若无法获取秒级实时价格，依据最新财报基本面、行业周期拐点与关键支撑阻力带进行深度定性推演。
   - 采用[投资亮点]与[风险因素]双边对抗评估模式。
   - 输出趋势颜色：看多/低位输出 #ef4444，看空/高位输出 #10b981，震荡输出 #f97316。

🚨【强制以纯 JSON 格式返回】：
{{
    "sector_news": [{{ "title": "行业动态标题", "summary": "详尽逻辑摘要" }}],
    "focus_stocks": [
        {{ 
            "name": "多氟多", 
            "trend_signal": "极简趋势状态(如: 触底反弹 / 估值筑底 / 震荡蓄势)", 
            "price_info": "估值中枢与关键区间(如: 核心支撑区间 / 估值历史低位分位)", 
            "key_levels": "盘面博弈与筹码结构逻辑分析", 
            "highlights": ["亮点1", "亮点2"], 
            "risks": ["风险1", "风险2"], 
            "valuation_color": "必须为 #ef4444 或 #10b981 或 #f97316" 
        }},
        {{ 
            "name": "华虹宏力", 
            "trend_signal": "极简趋势状态(如: 产能饱满 / 周期回暖 / 估值修复)", 
            "price_info": "估值中枢与关键区间(如: 核心支撑区间 / PB估值分位)", 
            "key_levels": "盘面博弈与筹码结构逻辑分析", 
            "highlights": ["亮点1", "亮点2"], 
            "risks": ["风险1", "风险2"], 
            "valuation_color": "必须为 #ef4444 或 #10b981 或 #f97316" 
        }},
        {{ 
            "name": "中信证券", 
            "trend_signal": "极简趋势状态(如: 头部溢价 / 政策共振 / 高位震荡)", 
            "price_info": "估值中枢与关键区间(如: PB估值中枢 / 核心平台支撑)", 
            "key_levels": "盘面博弈与筹码结构逻辑分析", 
            "highlights": ["亮点1", "亮点2"], 
            "risks": ["风险1", "风险2"], 
            "valuation_color": "必须为 #ef4444 或 #10b981 或 #f97316" 
        }}
    ]
}}
"""

GEMINI_PROMPT = f"""
今天是 {today_str}。请执行全球前沿探索、科学趣味发现（Fun Facts）与学术深读。
🚨【核心指令】：
1. 全局抓取 6-8 条外盘宏观或前沿科技快讯，严禁捏造URL，必须提供搜索关键词。
2. 精读 2 篇顶级医学文献，标题必须是论文项目名称，并在所有专有名词和药物后用括号附上英语原文。
3. 💡【Fun Facts 科学趣味发现】：每天随机挑选 1 个科学核心基础名词/概念。
   - 【专业底色】：用 1-2 句话给出清晰严谨的本质学术解释；
   - 【运作场景】：附带一个它在人体生理/病理、前沿实验室或现实系统中的运作机制；
   - 【趣味发现故事】：讲述它是“如何被意外发现的”科学轶事、科学家的高光顿悟时刻、奇妙事故，或者一个极具启发性、反直觉的趣味冷知识。要求文字生动有趣、引人入胜，让晨间阅读充满惊喜；
   - 【学科概率】：70% 概率为生物学、医学或先进材料学；30% 概率跨界至天文学、认知心理学、理论物理、计算机科学或经济学。
4. 严禁使用任何花体字或特殊 Unicode 数学字符。

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
    "science_concept": {{
        "term": "科学核心基础名词 (English Name)",
        "field": "所属学科领域 (如: 结构生物学 / 凝聚态物理 / 认知神经科学 / 宏观经济学)",
        "definition": "1-2句话清晰严密的本质学术解释",
        "scenario": "在人体内或科研/现实系统中的具体运作/应用场景",
        "discovery_or_fun_fact": "发现背后的趣味轶事、尤里卡顿悟瞬间或反直觉趣闻（100字左右，生动活泼）"
    }},
    "medical_news": [
        {{
            "project_title": "研究项目或论文名称 (English Title)",
            "journal_and_time": "期刊名与发表时间",
            "drug_name": "靶向药物通用名 (English Name)",
            "background": "痛点(专有名词需带英文)",
            "method_breakthrough": "核心技术与突破数据(带英文原文)",
            "clinical_value": "临床价值"
        }}
    ],
    "romantic_quote": "写给女朋友的早安暖心短句或浪漫情话（50字以内。不限制任何主题，风格自由、清新、诗意、温柔或风趣皆可，重点是读来让人眼前一亮、晨起拥有明媚好心情）"
}}
"""

# ==========================================
# 4. 双核调度函数
# ==========================================
def fetch_coze_data(retry=0):
    if not coze_token or not coze_bot_id:
        log("⚠️ 未检测到 COZE_API_TOKEN 或 COZE_BOT_ID，跳过国内数据拉取。请检查 GitHub Secrets 配置！")
        return None
    if retry > 2: return None
    
    log(f"🇨🇳 启动国内主力引擎 Coze (尝试 {retry+1})...")
    headers = {'Authorization': f'Bearer {coze_token}', 'Content-Type': 'application/json'}
    payload = {
        "bot_id": coze_bot_id, "user_id": "quant_master", 
        "additional_messages": [{"role": "user", "content": COZE_PROMPT, "content_type": "text"}]
    }
    
    try:
        response = requests.post('https://api.coze.cn/v3/chat', headers=headers, json=payload, timeout=60)
        res = response.json()
        if res.get('code') != 0: 
            log(f"❌ Coze 发起对话失败: {res}")
            time.sleep(5)
            return fetch_coze_data(retry + 1)
        
        chat_id = res['data']['id']
        conversation_id = res['data']['conversation_id']
        
        for _ in range(36):
            ret = requests.get(f'https://api.coze.cn/v3/chat/retrieve?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers).json()
            status = ret.get('data', {}).get('status')
            
            if status == 'completed':
                msgs = requests.get(f'https://api.coze.cn/v3/chat/message/list?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers).json()
                content = next((m.get('content') for m in msgs.get('data', []) if m.get('type') == 'answer'), "")
                clean_content = re.sub(r'```json|```', '', content).strip()
                return json.loads(clean_content)
            elif status in ['failed', 'canceled']:
                log(f"❌ Coze 状态异常终止: {status}")
                time.sleep(5)
                return fetch_coze_data(retry + 1)
                
            time.sleep(5)
            
        log("❌ Coze 请求超时 (180秒未能返回数据)")
        return None
        
    except Exception as e:
        log(f"❌ Coze 网络或解析异常: {str(e)}")
        time.sleep(5)
        return fetch_coze_data(retry + 1)

def fetch_gemini_data():
    if not gemini_client: return None
    # 优先使用 Gemini 3.7 Flash 引擎
    model_candidates = ['gemini-3.7-flash', 'gemini-3.5-flash', 'gemini-3-flash', 'gemini-2.5-flash']
    
    for model_id in model_candidates:
        for attempt in range(3):
            log(f"🌍 正在激活国际引擎 {model_id} (尝试 {attempt+1})...")
            try:
                chat = gemini_client.chats.create(
                    model=model_id,
                    config={"response_mime_type": "application/json"}
                )
                response = chat.send_message(GEMINI_PROMPT)
                raw_text = response.text
                if not raw_text: raise Exception("空数据")
                
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
# 5. HTML 渲染与发送
# ==========================================
def format_html(domestic_data, gemini_data):
    domestic_data = domestic_data or {}
    gemini_data = gemini_data or {}
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin: 0; padding: 15px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f8fafc; color: #334155;">
        <div style="max-width: 750px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.01);">
            <div style="text-align: center; margin-bottom: 25px; padding: 20px; border-bottom: 1px solid #e2e8f0;">
                <h2 style="color: #1e40af; margin: 0; font-size: 22px;">🌤️ Daily Financial Intelligence</h2>
                <p style="color: #94a3b8; font-size: 12px; margin-top: 5px; letter-spacing: 1px;">DOMESTIC QUANT & GLOBAL ACADEMIC</p>
            </div>
            <div style="padding: 0 20px 20px 20px;">
    """
    
    # 1. 全球快讯
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

    # 2. Fun Facts (原科学核心概念升级版)
    if gemini_data.get('science_concept'):
        concept = gemini_data.get('science_concept', {})
        html += "<h3 style='color: #581c87; border-bottom: 2px solid #8b5cf6; padding-bottom: 6px; margin-top: 25px;'>💡 Fun Facts</h3>"
        html += f"""
        <div style="background-color: #f5f3ff; border: 1px solid #ddd6fe; border-radius: 12px; padding: 18px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <span style="font-size: 15.5px; color: #4c1d95; font-weight: bold;">💡 {concept.get('term')}</span>
                <span style="background-color: #ede9fe; color: #6d28d9; padding: 2px 8px; border-radius: 4px; font-size: 11.5px; font-weight: bold; border: 1px solid #c4b5fd;">{concept.get('field')}</span>
            </div>
            <div style="font-size: 13px; color: #3b0764; line-height: 1.6; margin-bottom: 10px;">
                <b>📖 学术释义：</b>{concept.get('definition')}
            </div>
            <div style="font-size: 12.5px; color: #5b21b6; line-height: 1.6; background-color: #ffffff; padding: 9px 12px; border-radius: 6px; border-left: 3px solid #8b5cf6; margin-bottom: 10px;">
                <b>🧪 运作机制/场景：</b>{concept.get('scenario')}
            </div>
            <div style="font-size: 12.5px; color: #6b21a8; line-height: 1.6; background-color: #fdf4ff; padding: 9px 12px; border-radius: 6px; border-left: 3px solid #d946ef;">
                <b>✨ 发现故事 / 趣味轶事：</b>{concept.get('discovery_or_fun_fact')}
            </div>
        </div>
        """

    # 3. 国内重点行业逻辑与政策传导
    if domestic_data.get('sector_news'):
        html += "<h3 style='color: #1e293b; border-bottom: 2px solid #64748b; padding-bottom: 6px; margin-top: 25px;'>🏭 国内重点行业逻辑与政策传导</h3>"
        for item in domestic_data.get('sector_news', []):
            html += f"<div style='margin-bottom: 15px;'><h4 style='margin: 0 0 4px 0; font-size: 14.5px;'>▪ {item.get('title')}</h4><p style='margin:0; font-size: 13px; color: #475569; line-height: 1.6;'>{item.get('summary')}</p></div>"

    # 4. 博士级学术前沿追踪
    if gemini_data.get('medical_news'):
        html += "<h3 style='color: #065f46; border-bottom: 2px solid #10b981; padding-bottom: 6px; margin-top: 25px;'>🧬 博士级学术前沿追踪</h3>"
        for med in gemini_data.get('medical_news', []):
            html += f"""
            <div style="background-color: #f0fdf4; border: 1px solid #dcfce7; padding: 18px; border-radius: 12px; margin-bottom: 15px;">
                <div style="font-size: 15px; color: #065f46; margin-bottom: 6px; font-weight: bold;">🔬 {med.get('project_title')}</div>
                <div style="font-size: 12.5px; color: #059669; margin-bottom: 10px; border-bottom: 1px dashed #bbf7d0; padding-bottom: 8px;">📖 {med.get('journal_and_time')}</div>
                <div style="font-size: 13px; color: #166534; line-height: 1.6;">
                    • <b>研究背景：</b>{med.get('background')}<br>
                    • <b>靶点药物：</b><span style="background-color:#dcfce7; padding: 1px 4px; border-radius:3px;"><b>{med.get('drug_name')}</b></span><br>
                    • <b>方法突破：</b>{med.get('method_breakthrough')}<br>
                    • <b>转化价值：</b><b><u>{med.get('clinical_value')}</u></b>
                </div>
            </div>
            """

    # 5. A 股核心资产双边评估矩阵 (多氟多 + 华虹宏力 + 中信证券)
    if domestic_data.get('focus_stocks'):
        html += "<h3 style='color: #1e3c72; border-bottom: 2px solid #3b82f6; padding-bottom: 6px; margin-top: 25px;'>📈 A 股核心资产双边评估矩阵</h3>"
        for stock in domestic_data.get('focus_stocks', []):
            v_color = stock.get('valuation_color', '#334155')
            price_info = stock.get('price_info', '估值中枢评估中')
            
            highlights = "".join([f"• {h}<br>" for h in stock.get('highlights', [])])
            risks = "".join([f"• {r}<br>" for r in stock.get('risks', [])])
            
            html += f"""
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 12px; margin-bottom: 15px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px; align-items: center;">
                    <b style="font-size: 15px; color: #0f172a;">{stock.get('name')}</b> 
                    <span style="background-color: {v_color}15; color: {v_color}; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; border: 1px solid {v_color}30;">{stock.get('trend_signal')}</span>
                </div>
                <div style="margin-bottom: 8px; font-size: 12.5px; color: #0369a1; background: #f0f9ff; padding: 4px 8px; border-radius: 4px; border-left: 3px solid #0284c7;">
                    <b>🎯 估值/价格中枢：</b>{price_info}
                </div>
                <div style="font-size: 13px; color: #475569; line-height: 1.6; margin-bottom: 12px;">
                    <b>📊 盘面博弈：</b>{stock.get('key_levels')}
                </div>
                
                <table width="100%" cellpadding="0" cellspacing="0" style="font-size: 12.5px; border-top: 1px dashed #cbd5e1; padding-top: 12px;">
                    <tr>
                        <td width="48%" valign="top" style="background: #fff5f5; border-left: 3px solid #ef4444; padding: 10px; border-radius: 4px;">
                            <b style="color: #b91c1c; display:block; margin-bottom:5px;">🔴 投资亮点</b>
                            <span style="color: #7f1d1d; line-height: 1.5;">{highlights}</span>
                        </td>
                        <td width="4%"></td>
                        <td width="48%" valign="top" style="background: #f0fdf4; border-left: 3px solid #10b981; padding: 10px; border-radius: 4px;">
                            <b style="color: #047857; display:block; margin-bottom:5px;">🟢 风险因素</b>
                            <span style="color: #064e3b; line-height: 1.5;">{risks}</span>
                        </td>
                    </tr>
                </table>
            </div>
            """

    # 6. 晨间情话
    if gemini_data.get('romantic_quote'):
        html += f"""
        <div style="background: linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%); padding: 25px; text-align: center; border-radius: 16px; color: #be123c; font-weight: bold; margin-top: 30px; font-size: 14.5px; box-shadow: 0 4px 10px rgba(251,207,232,0.3);">
            🌸 {gemini_data.get('romantic_quote')} 💖
        </div>
        """
        
    html += """
            </div>
            <p style="text-align: center; color: #cbd5e1; font-size: 11px; padding-bottom: 20px;">&copy; 2026 SJTU Captain's Desk · Coze × Gemini 双核驱动</p>
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

def main():
    log("🎬 启动 Coze + Gemini 混合专家模型调度枢纽...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_domestic = executor.submit(fetch_coze_data)
        future_gemini = executor.submit(fetch_gemini_data)
        
        domestic_data = future_domestic.result()
        gemini_data = future_gemini.result()
        
    if not domestic_data and not gemini_data:
        log("❌ 国内与国际引擎均响应失败，任务终止。")
        sys.exit(1)
        
    if not domestic_data: log("⚠️ Coze A 股数据拉取失败，本期将仅包含全球新闻与医学解析。")
    if not gemini_data: log("⚠️ Gemini 国际数据拉取失败，本期将仅包含 A 股信息。")

    send_email(format_html(domestic_data, gemini_data))
    save_new_history(domestic_data)

if __name__ == '__main__':
    main()
