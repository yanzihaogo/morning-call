import os
import smtplib
import sys
import re
import json
import time
import unicodedata
from google import genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone

def log(message):
    bj_time = datetime.now(timezone(timedelta(hours=8))).strftime('%H:%M:%S')
    print(f"[{bj_time}] [🔍 投研自检] {message}")
    sys.stdout.flush()

# ==========================================
# 1. 配置中心
# ==========================================
API_KEY = os.getenv('GOOGLE_API_KEY')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')
RECEIVER_EMAIL = "779825335@qq.com"
CC_EMAIL = "15757699818@163.com"

client = genai.Client(api_key=API_KEY)
bj_tz = timezone(timedelta(hours=8))
today_str = datetime.now(bj_tz).strftime('%Y年%m月%d日')

# ==========================================
# 2. 核心自检级提示词 (重构新闻池与股票逻辑)
# ==========================================
STOCKS = ["航发科技", "航天动力", "航发控制", "长江电力", "多氟多", "英维克", "中国能建", "中国船舶", "云南锗业"]
SECTORS = ["人工智能", "军工装备", "电池", "小金属/贵金属", "银行", "多元金融"]

PROMPT = f"""
今天是 {today_str}。请执行最高专业等级的[定量数据投研]与[医学顶刊精读]任务 🎀。

🚨【防幻觉与防乱码红线】：
1. 绝对禁止捏造不存在的 URL 链接！新闻来源改为提供“全网搜索关键词”。
2. 绝对禁止捏造今日的精确收盘价！个股分析请基于长线逻辑、近期大宗事件、宏观景气度及宽泛的筹码结构进行推演。
3. 严禁使用任何数学花体字或特殊 Unicode 字符。

🚨【A股红绿色彩与估值学】：
- 看多/低位支撑/买入机会：输出红色代码 `#ef4444`
- 看空/高位压力/风险提示：输出绿色代码 `#10b981`
- 震荡/观望/中性：输出橙色代码 `#f97316`

### 📦 结构化 JSON 规范 (必须严格按照此结构生成)：
{{
    "sectors_quantitative": [
        {{
            "name": "板块名称",
            "gain_loss": "今日涨跌幅(%)",
            "capital_flow": "净流入额及占成交比例",
            "volume_status": "放量/缩量状态",
            "accumulated_flow": "近5/20个交易日累计资金流向"
        }}
    ],
    "global_news_flash": [
        {{
            "sector_tag": "所属板块",
            "time_location": "时间+地点",
            "entity": "发布机构(严禁模糊指代)",
            "summary": "硬核内容摘要",
            "search_keyword": "验证该新闻的精确搜索关键词(如：宁德时代 固态电池 发布会)"
        }}
    ],
    "medical_news": [
        {{
            "journal_and_time": "期刊名与发表时间",
            "drug_name": "靶向药物通用名",
            "background": "研究痛点背景",
            "method_breakthrough": "核心技术与突破数据",
            "clinical_value": "对临床路径的实质改变"
        }}
    ],
    "stock_analysis": [
        {{
            "name": "股票名称",
            "logic": "核心宏观与筹码逻辑(不瞎编实时价格)",
            "action": "极简操作建议",
            "valuation_color": "必须是 #ef4444 或 #10b981 或 #f97316"
        }}
    ],
    "romantic_quote": "专属浪漫粉色彩蛋（绝对禁止出现金融和医学术语）"
}}

🚨【数据要求】：
- 板块定量：必须涵盖这6个板块：{', '.join(SECTORS)}
- 行业新闻池 (global_news_flash)：请进行**扩容**，从上述6个板块中全局挑选 **6 至 8 条** 真正的重磅行业突发快讯。打破平均分配，哪个板块事大就多抓！
- 个股：{', '.join(STOCKS)}
- 医学：必须包含 2 篇顶级医学文献复盘。
"""

# ==========================================
# 3. 智能抗压排队逻辑
# ==========================================
def run_task():
    model_candidates = ['gemini-3.5-flash', 'gemini-3-flash']
    max_retries = 3 
    
    for model_id in model_candidates:
        for attempt in range(max_retries):
            log(f"📡 正在激活引擎 {model_id} (尝试 {attempt+1}/{max_retries})...")
            try:
                response = client.models.generate_content(
                    model=model_id, 
                    contents=PROMPT,
                    config={"response_mime_type": "application/json"}
                )
                
                raw_text = response.text
                if not raw_text:
                    raise Exception("返回数据为空")
                
                purified_text = unicodedata.normalize('NFKC', raw_text)
                data = json.loads(purified_text)
                
                if 'medical_news' not in data or not data['medical_news']:
                    log("⚠️ 模型漏输出了医学版块，正在触发重试...")
                    raise Exception("医学版块缺失")

                log(f"✅ 成功接通 {model_id}！数据结构完全健康。")
                return data
                
            except Exception as e:
                err_msg = str(e)
                log(f"⚠️ 算力波动或格式不全: {err_msg}")
                if "503" in err_msg or "UNAVAILABLE" in err_msg or "429" in err_msg:
                    if attempt < max_retries - 1:
                        wait_time = 15 * (attempt + 1)
                        log(f"⏳ 触发防撞墙机制，等待 {wait_time} 秒...")
                        time.sleep(wait_time)
                        continue
                elif "医学版块缺失" in err_msg:
                    time.sleep(5)
                    continue
                break
                
    return None

# ==========================================
# 4. 高兼容性 HTML 渲染引擎
# ==========================================
def format_html(data):
    html_content = ""
    
    # 1. 行业风向标 (仅展示定量数据)
    html_content += "<h3 style='color: #1e3c72; border-bottom: 2px solid #3b82f6; padding-bottom: 6px; margin-top: 10px;'>📊 核心板块定量资金追踪</h3>"
    for sector in data.get('sectors_quantitative', []):
        html_content += f"""
        <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 15px; margin-bottom: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <b style="font-size: 15px; color: #0f172a;">{sector.get('name')}</b>
                <span style="background-color: #3b82f6; color: white; padding: 2px 8px; border-radius: 6px; font-size: 12px; font-weight: bold;">{sector.get('gain_loss')}</span>
            </div>
            <div style="font-size: 13px; color: #475569; line-height: 1.6;">
                • <b>资金比例：</b>{sector.get('capital_flow')} | <b>量能：</b>{sector.get('volume_status')}<br>
                • <b>中线筹码：</b>{sector.get('accumulated_flow')}
            </div>
        </div>
        """

    # 2. 全局重磅新闻池 (扩容版)
    if data.get('global_news_flash'):
        html_content += "<h3 style='color: #1e3c72; border-bottom: 2px solid #3b82f6; padding-bottom: 6px; margin-top: 30px;'>🌍 全球高优行业快讯池</h3>"
        html_content += "<div style='background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; margin-bottom: 15px;'>"
        for idx, news in enumerate(data.get('global_news_flash', [])):
            border_style = "border-bottom: 1px dashed #cbd5e1; padding-bottom: 12px; margin-bottom: 12px;" if idx < len(data['global_news_flash'])-1 else ""
            html_content += f"""
            <div style="{border_style} font-size: 13.5px; line-height: 1.7; text-align: justify;">
                <span style="background-color: #e2e8f0; color: #334155; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-right: 5px;">{news.get('sector_tag')}</span>
                <span style="color: #64748b;">[{news.get('time_location')}]</span> 
                <b style="color: #1e40af;">{news.get('entity')}</b>: {news.get('summary')} 
                <div style="margin-top: 4px; font-size: 12px;">
                    🔍 <span style="color: #ea580c; background-color: #fff7ed; padding: 2px 5px; border-radius: 4px; border: 1px solid #ffedd5;">建议搜索关键词：<b>{news.get('search_keyword')}</b></span>
                </div>
            </div>
            """
        html_content += "</div>"

    # 3. 医药学术精要
    if data.get('medical_news'):
        html_content += "<h3 style='color: #1e3c72; border-bottom: 2px solid #10b981; padding-bottom: 6px; margin-top: 30px;'>🧬 博士级学术前沿追踪</h3>"
        for med in data.get('medical_news', []):
            html_content += f"""
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

    # 4. 资产精读 (红绿灯版)
    html_content += "<h3 style='color: #1e3c72; border-bottom: 2px solid #3b82f6; padding-bottom: 6px; margin-top: 30px;'>📈 资产四维精读与估值判定</h3>"
    for stock in data.get('stock_analysis', []):
        v_color = stock.get('valuation_color', '#334155')
        icon = "🔴" if v_color == "#ef4444" else ("🟢" if v_color == "#10b981" else "🟠")
        
        html_content += f"""
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 12px; margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 6px; align-items: center;">
                <b style="font-size: 14.5px; color: #0f172a;">{stock.get('name')}</b> 
                <span style="background-color: {v_color}15; color: {v_color}; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 12px; border: 1px solid {v_color}30;">估值色谱</span>
            </div>
            <div style="font-size: 13px; color: #475569; line-height: 1.6;">
                <b>筹码逻辑：</b>{stock.get('logic')}<br>
                <b>操作建议：</b>{icon} <span style="color: {v_color}; font-weight: bold;"><u>{stock.get('action')}</u></span>
            </div>
        </div>
        """

    # 5. 浪漫彩蛋
    if data.get('romantic_quote'):
        html_content += f"""
        <div style="background: linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%); padding: 25px; text-align: center; border-radius: 16px; color: #be123c; font-weight: bold; margin-top: 30px; font-size: 14.5px; box-shadow: 0 4px 10px rgba(251,207,232,0.3);">
            🌸 {data.get('romantic_quote')} 💖
        </div>
        """
        
    return html_content

def send_mail(html_body):
    log("📧 正在发送无幻觉高精度内参...")
    msg = MIMEMultipart()
    msg['Subject'] = f"✨ {today_str} 板块量化透视 × 行业精准要闻 🎀"
    msg['From'], msg['To'] = SENDER_EMAIL, RECEIVER_EMAIL
    
    final_html = f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.7; color: #334155; max-width: 750px; margin: 0 auto; padding: 15px; background-color: #f8fafc;">
        <div style="text-align: center; margin-bottom: 25px; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.01);">
            <h2 style="color: #1e40af; margin: 0; font-size: 22px;">🌤️ Daily Financial Intelligence</h2>
            <p style="color: #94a3b8; font-size: 12px; margin-top: 5px; letter-spacing: 1px;">QUANTITATIVE FLOW & PRECISION NEWS</p>
        </div>
        {html_body}
        <p style="text-align: center; color: #cbd5e1; font-size: 11px; margin-top: 40px;">&copy; 2026 Captain's Desk · 去幻觉引擎驱动</p>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(final_html, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL, CC_EMAIL], msg.as_string())
        log("🎉 邮件投递成功！")
    except Exception as e:
        log(f"❌ 邮件模块报错: {str(e)}")

# ==========================================
# 🚀 闭环入口
# ==========================================
if __name__ == '__main__':
    log("🎬 脚本启动 (扩容版+去幻觉)...")
    report_data = run_task()
    if report_data:
        send_mail(format_html(report_data))
    else:
        log("❌ 最终结论：未能返回有效数据，任务终止。")
        sys.exit(1)
