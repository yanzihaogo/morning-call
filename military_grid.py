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
# 2. 核心自检级提示词 (注入反花体字指令)
# ==========================================
STOCKS = ["航发科技", "航天动力", "航发控制", "长江电力", "多氟多", "英维克", "中国能建", "中国船舶", "云南锗业"]
SECTORS = ["人工智能", "军工装备", "电池", "小金属/贵金属", "银行", "多元金融"]

PROMPT = f"""
今天是 {today_str}。请执行最高专业等级的[定量数据投研]采编任务。

🚨【最高红线指令 - 严禁特殊字体】：
所有的数字（0-9）和英文字母（a-z, A-Z）必须使用最标准、最基础的常规字符。
绝对禁止使用任何数学粗体、双线体、花体、全角字符或任何特殊的 Unicode 变体字符（严禁输出如 𝟓, 𝟚_𝟘_𝟚_𝟚, 𝐀𝐁𝐂 这样的花体）。

🚨【投研硬性要求】：
1. **严禁模糊指代**：必须指明具体名称（如：微软公司、宁德时代），严禁使用“某公司”、“AI巨头”。
2. **新闻自带链接与时空要素**：每条新闻摘要末尾必须提供原始链接，开头写明【发布时间+地点】。
3. **不要走走势总结**：只精准摘录 3-5 条行业重大核心快讯。

### 📦 结构化 JSON 规范：
{{
    "sectors_data": [
        {{
            "name": "板块名称",
            "gain_loss": "今日涨跌幅(%)",
            "capital_flow": "净流入/流出金额及占该板块总成交额的比例(%)",
            "volume_status": "相比昨日是放量、缩量还是基本持平(判断增量资金是否介入)",
            "accumulated_flow": "统计近 5个/20个交易日的累计资金流向趋势",
            "news_flash": [
                {{
                    "time_location": "时间+地点",
                    "entity": "发布机构/公司全称",
                    "summary": "硬核内容摘要",
                    "url": "原始新闻参考链接"
                }}
            ]
        }}
    ],
    "stock_analysis": [
        {{
            "name": "股票名称",
            "logic": "核心逻辑",
            "levels": "支撑位/压力位",
            "action": "极简操作建议"
        }}
    ],
    "romantic_quote": "专属浪漫粉色彩蛋（绝对禁止出现金融和医学术语）"
}}

请针对以下内容进行全量深度计算：
板块：{', '.join(SECTORS)}
个股：{', '.join(STOCKS)}
"""

# ==========================================
# 3. 智能抗压运行逻辑 (解决 503 报错与花体清洗)
# ==========================================
def run_task():
    # 建立多模型梯队防线
    model_candidates = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
    
    for model_id in model_candidates:
        max_retries = 3
        for attempt in range(max_retries):
            log(f"📡 正在请求 {model_id} (尝试第 {attempt+1}/{max_retries} 次)...")
            try:
                response = client.models.generate_content(
                    model=model_id, 
                    contents=PROMPT,
                    config={"response_mime_type": "application/json"}
                )
                
                raw_text = response.text
                if not raw_text:
                    raise Exception("返回内容为空")
                
                # --- 核心黑科技：暴力清洗花体字与特殊符号 ---
                # NFKC 标准可以将各种数学花体字（如 𝟓, 𝟚𝟘𝟚𝟞）完美打回常规 ASCII 字符原型（5, 2026）
                purified_text = unicodedata.normalize('NFKC', raw_text)
                
                data = json.loads(purified_text)
                log(f"✅ 成功通过 {model_id} 获取数据，并完成纯净度清洗。")
                return data
                
            except Exception as e:
                err_msg = str(e)
                # 捕获 503 临时超载或者不可用状态
                if "503" in err_msg or "UNAVAILABLE" in err_msg:
                    log(f"⚠️ 触发服务器超载限制(503)。原地进入冷却期...")
                    if attempt < max_retries - 1:
                        time.sleep(15) # 等待15秒后进行下一次重试
                        continue
                log(f"❌ 当前尝试失败: {err_msg}")
                break # 跳出当前重试循环，尝试下一个备用模型
                
    return None

# ==========================================
# 4. 高兼容性 HTML 渲染引擎
# ==========================================
def format_html(data):
    html_content = ""
    
    # 行业风向标板块
    html_content += "<h3 style='color: #1e3c72; border-bottom: 2px solid #3b82f6; padding-bottom: 6px; margin-top: 10px;'>🌐 核心行业风向标 & 定量资金流</h3>"
    for sector in data.get('sectors_data', []):
        html_content += f"""
        <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <b style="font-size: 16px; color: #0f172a;">📊 {sector.get('name')}</b>
                <span style="background-color: #ef4444; color: white; padding: 2px 8px; border-radius: 6px; font-size: 12px; font-weight: bold;">{sector.get('gain_loss')}</span>
            </div>
            <div style="font-size: 13.5px; color: #334155; line-height: 1.6; margin-bottom: 12px; background-color: #f8fafc; padding: 10px; border-radius: 8px;">
                • <b>资金流向比例：</b>{sector.get('capital_flow')}<br>
                • <b>量能博弈状态：</b>{sector.get('volume_status')}<br>
                • <b>长线筹码追踪：</b>{sector.get('accumulated_flow')}
            </div>
        """
        
        if sector.get('news_flash'):
            html_content += "<div style='border-top: 1px dashed #e2e8f0; padding-top: 10px; margin-top: 10px; font-size: 13px; line-height: 1.7;'>"
            for news in sector.get('news_flash', []):
                html_content += f"""
                <div style="margin-bottom: 8px; text-align: justify;">
                    <span style="color: #64748b;">[{news.get('time_location')}]</span> 
                    <b style="color: #1e40af;">{news.get('entity')}</b>: 
                    {news.get('summary')} 
                    <a href="{news.get('url')}" style="color: #3b82f6; text-decoration: none; font-weight: bold;">[查看原文 ↗]</a>
                </div>
                """
            html_content += "</div>"
        html_content += "</div>"

    # 个股追踪板块
    html_content += "<h3 style='color: #1e3c72; border-bottom: 2px solid #3b82f6; padding-bottom: 6px; margin-top: 30px;'>📈 资产四维精读报告</h3>"
    for stock in data.get('stock_analysis', []):
        html_content += f"""
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 12px; margin-bottom: 12px;">
            <div style="font-size: 14px; margin-bottom: 6px;"><b>{stock.get('name')}</b> | <span style="color: #059669; font-weight: bold;">{stock.get('levels')}</span></div>
            <div style="font-size: 13px; color: #475569; line-height: 1.6;">
                <b>逻辑简述：</b>{stock.get('logic')}<br>
                <b>操作建议：</b><u>{stock.get('action')}</u>
            </div>
        </div>
        """

    # 浪漫彩蛋板块
    if data.get('romantic_quote'):
        html_content += f"""
        <div style="background: linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%); padding: 25px; text-align: center; border-radius: 16px; color: #be123c; font-weight: bold; margin-top: 30px; font-size: 14.5px; box-shadow: 0 4px 10px rgba(251,207,232,0.3);">
            🌸 {data.get('romantic_quote')} 💖
        </div>
        """
        
    return html_content

def send_mail(html_body):
    log("📧 正在发送全自检纯净版研报...")
    msg = MIMEMultipart()
    msg['Subject'] = f"✨ {today_str} 板块量化透视 × 行业精准要闻 🎀"
    msg['From'], msg['To'] = SENDER_EMAIL, RECEIVER_EMAIL
    
    # 强制将全局字体锁死在标准无衬线字体，防止客户端回退到花体字库
    final_html = f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.7; color: #334155; max-width: 750px; margin: 0 auto; padding: 15px; background-color: #f8fafc;">
        <div style="text-align: center; margin-bottom: 25px; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.01);">
            <h2 style="color: #1e40af; margin: 0; font-size: 22px;">🌤 shrink Daily Financial Intelligence</h2>
            <p style="color: #94a3b8; font-size: 12px; margin-top: 5px; letter-spacing: 1px;">QUANTITATIVE FLOW & PRECISION NEWS</p>
        </div>
        {html_body}
        <p style="text-align: center; color: #cbd5e1; font-size: 11px; margin-top: 40px;">&copy; 2026 Captain's Desk · 自愈重试系统已启用</p>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(final_html, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL, CC_EMAIL], msg.as_string())
        log("🎉 邮件已精准送达。")
    except Exception as e:
        log(f"❌ 发信终端异常: {str(e)}")

# ==========================================
# 🚀 稳定闭环入口
# ==========================================
if __name__ == '__main__':
    log("🎬 脚本启动 (高容错降级纯净版)...")
    report_data = run_task()
    if report_data:
        send_mail(format_html(report_data))
    else:
        log("❌ 最终结论：所有模型在重试后均遭遇算力过载，任务终止。")
        sys.exit(1)
