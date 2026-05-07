import os
import smtplib
import sys
import re
import time
from google import genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone

def log(message):
    bj_time = datetime.now(timezone(timedelta(hours=8))).strftime('%H:%M:%S')
    print(f"[{bj_time}] {message}")
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
# 2. 极致排版指令 (禁止 Markdown，强制 HTML)
# ==========================================
STOCKS = ["航发科技", "航天动力", "航发控制", "长江电力", "多氟多", "英维克", "中国能建", "中国船舶", "云南锗业"]

PROMPT = f"""
今天是 {today_str}。请为我的量化交易员用户及医学博士女友生成日报。

🚨【禁止指令】：严禁使用任何 Markdown 符号（如 **, ###, -, *）。所有排版必须使用纯 HTML 标签。

### 📦 模块指令：

#### 1. 🌐 全球板块风向标 (必须使用 <ul> <li> 标签实现分行)
- 覆盖：人工智能、军工装备、电池、小金属/贵金属、银行、多元金融。
- 格式：每个板块作为一个 <li> 节点，标题使用 <b> 标签加粗。每行只写一条核心逻辑。

#### 2. 🧬 医学博士学术精要 (精选 2 篇，每篇不少于 200 字)
- 结构：使用 <h4> 渲染标题。正文使用 <p> 标签。
- 重点：必须标注[药物通用名]。核心结论必须使用 <b><u>加粗并带下划线</u></b>。
- 样式：整体包裹在 <div style="background-color: #f0fdf4; padding: 20px; border-radius: 12px; margin-bottom: 25px;"> 中。

#### 3. 📊 资产四维精读 (标的: {', '.join(STOCKS)})
- 结构：每只个股独立使用一个 <div> 卡片。
- 内容：核心逻辑 + [支撑位/压力位] + 简短操作建议。
- 样式：背景色 #f8fafc，圆角 12px，边框 1px solid #e2e8f0。

#### 🚨 浪漫彩蛋：严禁生成。

标的名单：{', '.join(STOCKS)}
请直接输出纯 HTML 代码。
"""

# ==========================================
# 3. 运行逻辑 (增加 429 容错与 HTML 清洗)
# ==========================================
def run_task():
    model_id = 'gemini-2.5-flash' # 鉴于 Pro 没配额，先用 Flash 跑通
    log(f"📡 正在调用 {model_id} 生成高保真 HTML 报表...")
    
    try:
        response = client.models.generate_content(model=model_id, contents=PROMPT)
        content = response.text
        
        # 深度清洗：移除 AI 可能残留的 Markdown 格式
        content = re.sub(r'```html|```|markdown', '', content).strip()
        # 替换任何残留的 ** 加粗为 <b>
        content = content.replace('**', '')
        # 移除残留的 ### 标题
        content = content.replace('###', '')
        
        return content
    except Exception as e:
        log(f"❌ 运行异常: {str(e)}")
        return None

def send_mail(html_body):
    log("📧 正在打包并优化视觉细节...")
    msg = MIMEMultipart()
    msg['Subject'] = f"✨ {today_str} 资产周报 × 🧬 博士雷达 (视觉优化版)"
    msg['From'], msg['To'] = SENDER_EMAIL, RECEIVER_EMAIL
    
    # 注入内联 CSS，解决行业资讯“乌泱泱”堆在一起的问题
    final_html = f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, system-ui, sans-serif; line-height: 1.8; color: #334155; max-width: 800px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 40px; border-bottom: 2px solid #f1f5f9; padding-bottom: 20px;">
            <h2 style="color: #1e40af; margin-bottom: 5px;">🌤️ Daily Intelligence</h2>
            <p style="color: #94a3b8; font-size: 13px; letter-spacing: 1px;">QUANT + MEDICINE INSIGHTS</p>
        </div>
        
        <style>
            ul {{ padding-left: 20px; }}
            li {{ margin-bottom: 12px; list-style-type: none; }}
            h4 {{ color: #0f172a; margin-top: 0; margin-bottom: 10px; border-bottom: 1px solid #e2e8f0; padding-bottom: 5px; }}
        </style>

        {html_body}
        
        <p style="text-align: center; color: #cbd5e1; font-size: 11px; margin-top: 50px;">&copy; 2026 Capt. Desk · 自动采编系统</p>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(final_html, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL, CC_EMAIL], msg.as_string())
        log("✅ 视觉优化版日报已成功发送。")
    except Exception as e:
        log(f"❌ 邮件发送失败: {str(e)}")

if __name__ == '__main__':
    log("🎬 脚本启动...")
    report = run_task()
    if report:
        send_email(report)
    else:
        sys.exit(1)
