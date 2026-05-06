import os
import smtplib
import sys
import re
import time
# 注意：2026 年新版导入方式
from google import genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone

def log(message):
    bj_time = datetime.now(timezone(timedelta(hours=8))).strftime('%H:%M:%S')
    print(f"[{bj_time}] {message}")
    sys.stdout.flush()

# ==========================================
# 1. 配置中心 (新版 SDK 适配)
# ==========================================
API_KEY = os.getenv('GOOGLE_API_KEY')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')
RECEIVER_EMAIL = "779825335@qq.com"
CC_EMAIL = "15757699818@163.com"

if not all([API_KEY, SMTP_SERVER, SENDER_EMAIL, SENDER_PASSWORD]):
    log("❌ 错误：环境变量配置不全。")
    sys.exit(1)

# 初始化新版 Client
try:
    client = genai.Client(api_key=API_KEY)
    log("✅ Gemini 新版引擎初始化成功")
except Exception as e:
    log(f"❌ 初始化失败：{str(e)}")
    sys.exit(1)

bj_tz = timezone(timedelta(hours=8))
today_str = datetime.now(bj_tz).strftime('%Y年%m月%d日')

# ==========================================
# 2. 蒸馏指令 (Prompt)
# ==========================================
STOCKS = ["航发科技", "航天动力", "航发控制", "长江电力", "多氟多", "英维克", "中国能建", "中国船舶", "云南锗业"]

PROMPT = f"""
今天是 {today_str}。请执行[博士级逻辑蒸馏]任务。
要求：严禁废话。个股复盘需关联造船板价格、锗价及宏观流动性。
医学综述必须标注[药物通用名]，包含①研究团队 ②科学痛点 ③技术方法 ④核心突破 ⑤转化价值。

标的名单：{', '.join(STOCKS)}

输出要求：直接返回 HTML 代码。
"""

# ==========================================
# 3. 运行逻辑 (新版 API 调用)
# ==========================================
def run_task():
    log("📡 正在发起 2026 版深度采编请求...")
    try:
        # 新版 API 调用语法更为直观
        response = client.models.generate_content(
            model='gemini-1.5-pro', 
            contents=PROMPT
        )
        
        # 新版获取文本的方式依然是 .text
        content = response.text
        
        if "```html" in content:
            content = re.search(r"```html(.*?)```", content, re.DOTALL).group(1)
        elif "```" in content:
            content = re.search(r"```(.*?)```", content, re.DOTALL).group(1)
            
        log("✅ 报告内容蒸馏成功")
        return content.strip()
    except Exception as e:
        log(f"❌ Gemini 生成内容失败：{str(e)}")
        return None

def send_mail(html_body):
    log("📧 正在推送到邮箱...")
    msg = MIMEMultipart()
    msg['Subject'] = f"⚡ {today_str} 核心资产追踪 × 🧬 医学博士雷达"
    msg['From'], msg['To'] = SENDER_EMAIL, RECEIVER_EMAIL
    
    final_html = f"""
    <html>
    <body style="font-family: sans-serif; line-height: 1.6; color: #334155; padding: 10px;">
        {html_body}
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
        log(f"❌ 邮件发送失败：{str(e)}")

if __name__ == '__main__':
    log("🎬 脚本已启动 (Gemini 2026 SDK)")
    report_content = run_task()
    if report_content:
        send_mail(report_content)
        log("✨ 任务闭环。")
    else:
        sys.exit(1)
