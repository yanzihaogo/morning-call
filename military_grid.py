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
    log("❌ 错误：未检测到 GOOGLE_API_KEY，请检查 GitHub Secrets。")
    sys.exit(1)

# 初始化新版 Client
client = genai.Client(api_key=API_KEY)

bj_tz = timezone(timedelta(hours=8))
today_str = datetime.now(bj_tz).strftime('%Y年%m月%d日')

# ==========================================
# 2. 核心指令 (Prompt)
# ==========================================
STOCKS = ["航发科技", "航天动力", "航发控制", "长江电力", "多氟多", "英维克", "中国能建", "中国船舶", "云南锗业"]

PROMPT = f"""
今天是 {today_str}。请执行[博士级逻辑蒸馏]任务。
标的名单：{', '.join(STOCKS)}
要求：
1. 个股复盘需关联造船板价格、锗价及宏观流动性。
2. 医学综述必须标注[药物通用名]，包含研究团队、痛点、方法、突破、价值。
输出要求：直接返回 HTML 代码，使用色块美化排版。
"""

# ==========================================
# 3. 运行逻辑 (带降级保护)
# ==========================================
def run_task():
    # 2026 年标准模型 ID 列表（按优先级排序）
    # 有时 404 是因为模型需要 'models/' 前缀，有时是因为 1.5-pro 暂时不可用
    model_candidates = ['gemini-1.5-pro', 'gemini-1.5-flash']
    
    content = None
    
    for model_id in model_candidates:
        log(f"📡 尝试调用模型: {model_id} ...")
        try:
            response = client.models.generate_content(
                model=model_id, 
                contents=PROMPT
            )
            content = response.text
            if content:
                log(f"✅ 使用 {model_id} 成功生成内容")
                break
        except Exception as e:
            error_str = str(e)
            if "404" in error_str:
                log(f"⚠️ 模型 {model_id} 报 404 错误，可能是权限或 ID 变更，准备尝试下一个...")
            else:
                log(f"❌ 调用 {model_id} 时发生其他错误: {error_str}")
    
    if not content:
        log("❌ 所有候选模型均调用失败。")
        return None

    # 清理 Markdown 标签
    if "```html" in content:
        content = re.search(r"```html(.*?)```", content, re.DOTALL).group(1)
    elif "```" in content:
        content = re.search(r"```(.*?)```", content, re.DOTALL).group(1)
            
    return content.strip()

def send_mail(html_body):
    log("📧 正在准备发送邮件...")
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
        log("🎉 邮件已送达。")
    except Exception as e:
        log(f"❌ 邮件发送失败：{str(e)}")

if __name__ == '__main__':
    log("🎬 脚本已启动 (Gemini 2026 SDK + 降级保护)")
    report_content = run_task()
    if report_content:
        send_mail(report_content)
        log("✨ 任务闭环。")
    else:
        log("❌ 流程中断：未能生成内容。")
        sys.exit(1)
