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
# 2. 极致 HTML 排版指令 (绝对禁止 Markdown)
# ==========================================
STOCKS = ["航发科技", "航天动力", "航发控制", "长江电力", "多氟多", "英维克", "中国能建", "中国船舶", "云南锗业"]

PROMPT = f"""
今天是 {today_str}。请生成日报。

🚨【核心禁令】：
严禁使用任何 Markdown 符号（如 **, ###, -, *）。所有排版必须且仅能使用 HTML 标签。

### 📦 模块指令：

#### 1. 🌐 全球板块风向标 (必须使用 <ul> <li> 标签实现分行)
- 板块：人工智能、军工装备、电池、小金属/贵金属、银行、多元金融。
- 格式：每个板块占一行 <li>，标题用 <b> 加粗。

#### 2. 🧬 医学学术精要 (每篇 200 字以上)
- 结构：标题用 <h4>，正文用 <p>。
- 重点：标注[药物通用名]，核心结论用 <b><u>加粗并带下划线</u></b>。
- 样式：包裹在 <div style="background-color: #f0fdf4; padding: 20px; border-radius: 12px; margin-bottom: 25px;">。

#### 3. 📊 资产四维精读 (标的: {', '.join(STOCKS)})
- 样式：背景 #f8fafc，圆角 12px，边框 1px solid #e2e8f0，padding: 15px，margin-bottom: 15px。
"""

# ==========================================
# 3. 运行逻辑 (彻底清理排版垃圾)
# ==========================================
def run_task():
    model_id = 'gemini-2.5-flash' 
    log(f"📡 正在调用 {model_id} 生成高保真 HTML 报表...")
    
    try:
        response = client.models.generate_content(model=model_id, contents=PROMPT)
        raw_content = response.text
        
        # --- 暴力清理 Markdown 杂质 ---
        # 1. 移除代码块包裹
        clean_content = re.sub(r'```html|```|markdown', '', raw_content).strip()
        # 2. 移除 AI 习惯性生成的 ** 加粗符号
        clean_content = clean_content.replace('**', '')
        # 3. 移除残留的 # 标题符号
        clean_content = clean_content.replace('#', '')
        # 4. 移除多余的单星号列表符
        clean_content = clean_content.replace('* ', '• ')
        
        log("✅ 报告内容已完成深度 HTML 清洗")
        return clean_content
    except Exception as e:
        log(f"❌ Gemini 调用异常: {str(e)}")
        return None

def send_mail(html_body):
    log("📧 正在打包发送视觉优化版日报...")
    msg = MIMEMultipart()
    msg['Subject'] = f"✨ {today_str} 资产周报 × 🧬 博士雷达"
    msg['From'], msg['To'] = SENDER_EMAIL, RECEIVER_EMAIL
    
    # 注入全局 CSS，确保邮件客户端正确渲染间距
    final_html = f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: sans-serif; line-height: 1.8; color: #334155; max-width: 800px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px; border-bottom: 2px solid #f1f5f9; padding-bottom: 20px;">
            <h2 style="color: #1e40af; margin-bottom: 5px;">🌤️ Daily Intelligence</h2>
            <p style="color: #94a3b8; font-size: 13px;">QUANT + MEDICINE INSIGHTS</p>
        </div>
        {html_body}
        <p style="text-align: center; color: #cbd5e1; font-size: 11px; margin-top: 50px;">&copy; 2026 Captain's Desk</p>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(final_html, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL, CC_EMAIL], msg.as_string())
        log("🎉 邮件已成功送达。")
    except Exception as e:
        log(f"❌ 发信报错: {str(e)}")

# ==========================================
# 🚀 修正后的入口逻辑 (send_mail 拼写已修正)
# ==========================================
if __name__ == '__main__':
    log("🎬 脚本启动...")
    report = run_task()
    if report:
        # 修正之前的 typo：send_email -> send_mail
        send_mail(report) 
    else:
        log("❌ 流程中断：生成内容为空")
        sys.exit(1)
