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

if not API_KEY:
    log("❌ 错误：未检测到 GOOGLE_API_KEY。")
    sys.exit(1)

# 初始化 2026 新版 Client
client = genai.Client(api_key=API_KEY)

bj_tz = timezone(timedelta(hours=8))
today_str = datetime.now(bj_tz).strftime('%Y年%m月%d日')

# ==========================================
# 2. 博士级蒸馏指令 (针对 2.5 系列优化)
# ==========================================
STOCKS = ["航发科技", "航天动力", "航发控制", "长江电力", "多氟多", "英维克", "中国能建", "中国船舶", "云南锗业"]

PROMPT = f"""
今天是 {today_str}。请执行[博士级逻辑蒸馏]任务。
标的名单：{', '.join(STOCKS)}

要求：
1. 【量化复盘】：分析 9 只个股。关联造船板价格、锗价及宏观流动性。给出具体的支撑/压力位。
2. 【医学雷达】：检索顶刊文献。必须标注[药物通用名]，包含团队、痛点、方法、突破、价值。
3. 【排版】：直接返回带有背景色块的 HTML 代码，确保专业美观。
"""

# ==========================================
# 3. 运行逻辑 (匹配 2.5/2.0 模型 ID)
# ==========================================
def run_task():
    # 根据你的面板截图，这些是 2026 年你可用的模型 ID
    model_candidates = [
        'gemini-2.5-pro', 
        'gemini-2.5-flash', 
        'gemini-2.0-flash'
    ]
    
    content = None
    
    for model_id in model_candidates:
        log(f"📡 尝试调用次世代模型: {model_id} ...")
        try:
            # 2026 版新语法调用
            response = client.models.generate_content(
                model=model_id, 
                contents=PROMPT
            )
            content = response.text
            if content:
                log(f"✅ 使用 {model_id} 蒸馏成功")
                break
        except Exception as e:
            log(f"⚠️ 模型 {model_id} 调用失败，尝试下一个候选者。详情: {str(e)}")
    
    if not content:
        log("❌ 所有可用模型（2.5/2.0 系列）均无法连接。")
        return None

    # 清理 Markdown 代码块
    if "```html" in content:
        content = re.search(r"```html(.*?)```", content, re.DOTALL).group(1)
    elif "```" in content:
        content = re.search(r"```(.*?)```", content, re.DOTALL).group(1)
            
    return content.strip()

def send_mail(html_body):
    log("📧 正在打包推送到邮箱...")
    msg = MIMEMultipart()
    msg['Subject'] = f"⚡ {today_str} 核心资产追踪 × 🧬 医学博士雷达 (2.5 Pro 版)"
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
        log("🎉 日报已送达邮箱。")
    except Exception as e:
        log(f"❌ 邮件模块报错：{str(e)}")

if __name__ == '__main__':
    log("🎬 脚本启动 (已适配 Gemini 2.5 权限)")
    report_content = run_task()
    if report_content:
        send_mail(report_content)
        log("✨ 今日自动化流程完美闭环。")
    else:
        sys.exit(1)
