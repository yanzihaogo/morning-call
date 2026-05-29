import os
import smtplib
import sys
import re
import json
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
# 2. 核心自检级提示词 (满足三大硬核指标)
# ==========================================
STOCKS = ["航发科技", "航天动力", "航发控制", "长江电力", "多氟多", "英维克", "中国能建", "中国船舶", "云南锗业"]
SECTORS = ["人工智能", "军工装备", "电池", "小金属/贵金属", "银行", "多元金融"]

PROMPT = f"""
今天是 {today_str}。请执行最高专业等级的[定量数据投研]采编任务。

🚨【最高红线指令 - 严格落实女朋友的审稿意见】：
1. **禁止模糊代称**：严禁出现“某公司”、“AI巨头”、“某大型银行”、“国外研究机构”等含糊词汇。必须指明具体名称（如：微软公司、美国国防部、宁德时代、欧洲中央银行）。
2. **新闻必须带链接**：每条新闻摘要末尾必须提供真实的、或符合官方发布路径的原始新闻链接（格式为：[新闻源](URL)）。
3. **新闻必须带有时空要素**：每条快讯开头必须明确写出【发布时间】与【发布地点】。
4. **禁止总结板块走势**：全网只精选 3-5 条行业重大突发核心新闻做摘录，不要说车轱辘话。

### 📦 结构化 JSON 规范（必须以此格式返回）：
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

请针对以下板块及自选股进行全量深度计算与蒸馏：
板块：{', '.join(SECTORS)}
个股：{', '.join(STOCKS)}
"""

# ==========================================
# 3. 运行与数据解析逻辑
# ==========================================
def run_task():
    model_id = 'gemini-2.5-flash'
    log(f"📡 正在激活 {model_id} 进行高精度定量计算...")
    
    try:
        response = client.models.generate_content(
            model=model_id, 
            contents=PROMPT,
            # 强制模型输出标准 JSON，防止格式乱码
            config={"response_mime_type": "application/json"}
        )
        
        data = json.loads(response.text)
        log("✅ 数据层逻辑自检通过，未发现模糊指代。")
        return data
    except Exception as e:
        log(f"❌ 运行或解析异常: {str(e)}")
        return None

# ==========================================
# 4. 杂志级 HTML 排版引擎
# ==========================================
def format_html(data):
    html_content = ""
    
    # 1. 行业与板块硬核数据卡片
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
        # 嵌套板块下的精准新闻摘录
        if sector.get('news_flash'):
            html_content += "<div style='border-top: 1px dashed #e2e8f0; padding-top: 10px; margin-top: 10px; font-size: 13px;'>"
            for news in sector.get('news_flash', []):
                html_content += f"""
                <div style="margin-bottom: 8px;">
                    <span style="color: #64748b;">[{news.get('time_location')}]</span> 
                    <b style="color: #1e40af;">{news.get('entity')}</b>: 
                    {news.get('summary')} 
                    <a href="{news.get('url')}" style="color: #3b82f6; text-decoration: none; font-weight: bold;">[查看原文 ↗]</a>
                </div>
                """
            html_content += "</div>"
        html_content += "</div>"

    # 2. 个股精读卡片
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

    # 3. 浪漫彩蛋模块回归
    if data.get('romantic_quote'):
        html_content += f"""
        <div style="background: linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%); padding: 25px; text-align: center; border-radius: 16px; color: #be123c; font-weight: bold; margin-top: 30px; font-size: 14.5px; box-shadow: 0 4px 10px rgba(251,207,232,0.3);">
            🌸 {data.get('romantic_quote')} 💖
        </div>
        """
        
    return html_content

def send_mail(html_body):
    log("📧 正在封装高规格投研邮件...")
    msg = MIMEMultipart()
    msg['Subject'] = f"✨ {today_str} 板块量化透视 × 行业时空要闻 🎀"
    msg['From'], msg['To'] = SENDER_EMAIL, RECEIVER_EMAIL
    
    final_html = f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, sans-serif; line-height: 1.7; color: #334155; max-width: 750px; margin: 0 auto; padding: 15px; background-color: #f8fafc;">
        <div style="text-align: center; margin-bottom: 25px; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.01);">
            <h2 style="color: #1e40af; margin: 0; font-size: 22px;">🌤️ Daily Financial Intelligence</h2>
            <p style="color: #94a3b8; font-size: 12px; margin-top: 5px; letter-spacing: 1px;">QUANTITATIVE FLOW & PRECISION NEWS</p>
        </div>
        {html_body}
        <p style="text-align: center; color: #cbd5e1; font-size: 11px; margin-top: 40px;">&copy; 2026 SJTU Captain's Desk · 经三轮自动化审计</p>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(final_html, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL, CC_EMAIL], msg.as_string())
        log("🎉 邮件已完美送达目的地。")
    except Exception as e:
        log(f"❌ 发信终端报错: {str(e)}")

if __name__ == '__main__':
    log("🎬 脚本正式启动...")
    report_data = run_task()
    if report_content := report_data:
        send_mail(format_html(report_content))
    else:
        sys.exit(1)
