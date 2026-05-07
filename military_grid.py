import os
import smtplib
import sys
import re
import time
from google import genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone

# --- 日志记录 ---
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
# 2. 定向蒸馏指令 (新版精简 Prompt)
# ==========================================
STOCKS = ["航发科技", "航天动力", "航发控制", "长江电力", "多氟多", "英维克", "中国能建", "中国船舶", "云南锗业"]

PROMPT = f"""
今天是 {today_str}。请为我的量化交易员用户及其医学博士女友生成一份[极简蒸馏版]日报 ✨。

### 🎨 视觉风格协议：
1. **可爱化**: 标题和重点必须带有 Emoji (如 🤖, ⚔️, 🔋, 💎, 🏦, 💖)。
2. **精炼化**: 拒绝长难句，每条信息都要经过“脱水”处理。
3. **加粗**: 对医学关键结论和金融核心点位使用 <b> 标签进行强调。

### 📦 模块指令：

#### 🌐 全球板块风向标 (精简速览)
- 覆盖：人工智能、军工装备、电池、小金属/贵金属、银行、多元金融。
- 每板块限 2 条核心快讯，每条限 50 字，必须包含对投资偏好的影响。

#### 🧬 医学博士学术精要 (深度蒸馏)
- 内容：复盘 2 篇顶刊文献。
- 结构：[研究背景]、[方法/突破]、[转化价值]。
- 要求：**核心结论必须加粗并使用下划线（text-decoration: underline）**。
- 字数：每篇限 150 字，标注具体的[药物通用名]。
- 样式：包裹在 <div style="background-color: #f0fdf4; padding: 15px; border-radius: 12px; margin-bottom: 20px;">。

#### 📊 资产四维精读 (标的: {', '.join(STOCKS)})
- 内容：每只标的 100-120 字。
- 结构：核心逻辑 + **[支撑/压力位]** + 简短操作建议。
- 样式：包裹在 <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 12px; margin-bottom: 15px;">。

#### 💖 浪漫粉色彩蛋
- 原创甜味情话，严禁专业术语。
- 样式：包裹在 <div style="background: linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%); padding: 25px; text-align: center; border-radius: 15px; color: #be123c;">。
"""

# ==========================================
# 3. 运行逻辑
# ==========================================
def run_task():
    model_candidates = ['gemini-2.5-pro', 'gemini-2.5-flash']
    content = None
    
    for model_id in model_candidates:
        log(f"📡 正在尝试调用模型: {model_id} ...")
        try:
            response = client.models.generate_content(model=model_id, contents=PROMPT)
            content = response.text
            if content:
                log(f"✅ 使用 {model_id} 成功生成内容")
                break
        except Exception as e:
            log(f"⚠️ {model_id} 响应异常，尝试切换...")
    
    if not content: return None

    # 清理代码块标记
    if "```html" in content:
        content = re.search(r"```html(.*?)```", content, re.DOTALL).group(1)
    elif "```" in content:
        content = re.search(r"```(.*?)```", content, re.DOTALL).group(1)
            
    return content.strip()

def send_mail(html_body):
    log("📧 正在打包发送...")
    msg = MIMEMultipart()
    msg['Subject'] = f"✨ {today_str} 资产周报 × 🧬 博士雷达 🎀"
    msg['From'], msg['To'] = SENDER_EMAIL, RECEIVER_EMAIL
    
    # 全局 CSS 注入，增强美观度
    final_html = f"""
    <html>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; line-height: 1.5; color: #334155; max-width: 750px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #1e40af; margin-bottom: 5px; font-size: 24px;">🌤️ Daily Intelligence</h1>
            <p style="color: #94a3b8; font-size: 12px; letter-spacing: 2px;">QUANT + MEDICINE INSIGHTS</p>
        </div>
        {html_body}
        <p style="text-align: center; color: #cbd5e1; font-size: 11px; margin-top: 40px;">&copy; 2026 SJTU Captain's Desk. All Rights Reserved.</p>
    </body>
    </html>
    """
    msg.attach(MIMEText(final_html, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL, CC_EMAIL], msg.as_string())
        log("🎉 任务圆满完成。")
    except Exception as e:
        log(f"❌ 发信异常：{str(e)}")

if __name__ == '__main__':
    log("🎬 脚本启动 (2026 精简美化版)")
    report = run_task()
    if report:
        send_mail(report)
    else:
        log("❌ 报告生成失败")
        sys.exit(1)
