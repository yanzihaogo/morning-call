import os
import smtplib
import sys
import re
from google import genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone

def log(message):
    bj_time = datetime.now(timezone(timedelta(hours=8))).strftime('%H:%M:%S')
    print(f"[{bj_time}] [System Audit] {message}")
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
# 2. “可爱深度”指令 (包含新闻摘录与情话)
# ==========================================
STOCKS = ["航发科技", "航天动力", "航发控制", "长江电力", "多氟多", "英维克", "中国能建", "中国船舶", "云南锗业"]

PROMPT = f"""
今天是 {today_str}。请为我的量化员及其医学博士女友生成日报 🎀。

🚨【核心指令】：
1. 严禁 Markdown 符号（**, ###）。仅限使用 HTML 标签。
2. 全程使用可爱 Emoji (如 🌈, 🍭, 🧪, 📈, 🚀)。
3. 必须包含末尾的【专属浪漫彩蛋】模块。

### 📦 采编细节：

#### 1. 🌍 全球热点速递 (限 3-5 条热点新闻摘录)
- **范围**：从 [人工智能, 军工装备, 电池, 小金属, 银行, 多元金融] 中挑选。
- **要求**：不要总结板块走势！请直接摘录 3-5 条最具冲击力的新闻标题和简短核心内容。
- **样式**：使用 <li> 标签分行，标题加粗。

#### 2. 🧬 医学博士学术精要 (深度回归)
- 精选 2 篇顶刊，每篇 200 字以上。标注[药物通用名]。
- 样式：核心结论使用 <b><u>加粗并划线</u></b>。使用圆角卡片渲染。

#### 3. 📊 资产四维精读 (标的: {', '.join(STOCKS)})
- 结构：核心逻辑 + [支撑/压力位] + 简短操作建议。

#### 4. 💖 专属浪漫彩蛋
- **内容**：原创一段甜甜的情话。严禁出现任何专业术语。
- **样式**：必须包含在粉色渐变卡片中。
"""

# ==========================================
# 3. 运行逻辑 (带 Markdown 物理强踢)
# ==========================================
def run_task():
    model_id = 'gemini-2.5-flash'
    log(f"📡 正在调用 {model_id} 生成可爱版 HTML 报表...")
    
    try:
        response = client.models.generate_content(model=model_id, contents=PROMPT)
        raw_text = response.text
        
        # 深度清洗 Markdown 杂质
        clean_content = re.sub(r'```html|```|markdown', '', raw_text).strip()
        clean_content = clean_content.replace('**', '')
        clean_content = clean_content.replace('###', '')
        clean_content = clean_content.replace('* ', '• ')
        
        return clean_content
    except Exception as e:
        log(f"❌ Gemini 生成异常: {str(e)}")
        return None

def send_mail(html_body):
    log("📧 正在打包发送含有“情感溢价”的日报...")
    msg = MIMEMultipart()
    msg['Subject'] = f"✨ {today_str} 资产周报 × 🧬 博士雷达 🎀"
    msg['From'], msg['To'] = SENDER_EMAIL, RECEIVER_EMAIL
    
    # 注入全局视觉：修复“乌泱泱”堆砌，加入粉色渐变
    final_html = f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, sans-serif; line-height: 1.8; color: #334155; max-width: 800px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px; border-bottom: 2px solid #f1f5f9; padding-bottom: 15px;">
            <h2 style="color: #1e40af;">🌤️ Daily Intelligence 🍭</h2>
            <p style="color: #94a3b8; font-size: 12px;">QUANT + MEDICINE INSIGHTS</p>
        </div>
        
        <style>
            ul {{ padding-left: 20px; }}
            li {{ margin-bottom: 12px; }}
            h4 {{ color: #0f172a; margin-top: 0; }}
        </style>

        {html_body}
        
        <p style="text-align: center; color: #cbd5e1; font-size: 11px; margin-top: 50px;">&copy; 2026 Capt. SJ · 自检通过 🌈</p>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(final_html, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL, CC_EMAIL], msg.as_string())
        log("🎉 日报已精准推送。")
    except Exception as e:
        log(f"❌ 发信系统故障: {str(e)}")

# ==========================================
# 🚀 修正入口逻辑 (自查三遍)
# ==========================================
if __name__ == '__main__':
    log("🎬 脚本正式启动...")
    report = run_task()
    if report:
        # 这里是 send_mail，定义处也是 send_mail，一致性 100%
        send_mail(report) 
    else:
        sys.exit(1)
