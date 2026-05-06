import os
import smtplib
import sys
import re
import time
from google import genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone

# 【日志函数】
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
# 2. “可爱+深度”蒸馏指令
# ==========================================
STOCKS = ["航发科技", "航天动力", "航发控制", "长江电力", "多氟多", "英维克", "中国能建", "中国船舶", "云南锗业"]

PROMPT = f"""
今天是 {today_str}。你现在是一个超级可爱、专业且贴心的博士级研报助手 🎀。
请为我的量化交易员用户及其医学博士女友生成一份日报。

### 🦄 写作规范：
1. **可爱属性**：在每个标题和核心段落中加入大量的 Emoji (如 ✨, 🚀, 💊, 📊, 🌸)，让排版显得生动可爱。
2. **逻辑蒸馏**：拒绝敷衍。医学部分必须有深度，金融部分必须有具体的支撑压力位测算。
3. **样式要求**：直接返回 HTML。

### 📦 模块指令：

#### 🧬 医学博士学术前沿 (受众: 博士女友)
- **内容**：复盘 2-3 篇顶刊。必须包含：研究团队、科学痛点、技术方法、核心突破、转化价值。
- **标注**：药物必须括号标注[通用名 Generic Name]。
- **样式**：包裹在 <div style="background-color: #f0fdf4; padding: 18px; border-radius: 15px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);"> 中。**不要在左侧加粗竖条颜色条**。

#### 📈 核心资产深度复盘 (标的: {', '.join(STOCKS)})
- **内容**：9只股票全部覆盖。关联造船板价格、锗价、电力现货及宏观走势。
- **要求**：每只标的 180 字以上。给出具体的[量价-资金-基本面-策略]。
- **样式**：包裹在 <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 18px; border-radius: 15px; margin-bottom: 15px;"> 中。

#### 💖 专属浪漫彩蛋
- **内容**：原创一段甜甜的情话。严禁出现金融、交易、医学术语。
- **样式**：包裹在 <div style="background: linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%); padding: 30px; text-align: center; border-radius: 20px; color: #be123c; font-weight: bold;"> 中。
"""

# ==========================================
# 3. 运行逻辑 (适配 2026 新版 API)
# ==========================================
def run_task():
    # 自动尝试优先级最高的模型
    model_candidates = ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.0-flash']
    content = None
    
    for model_id in model_candidates:
        log(f"📡 尝试调用模型: {model_id} ...")
        try:
            response = client.models.generate_content(model=model_id, contents=PROMPT)
            content = response.text
            if content:
                log(f"✅ 使用 {model_id} 生成成功")
                break
        except Exception as e:
            log(f"⚠️ {model_id} 尝试失败")
    
    if not content: return None

    # 清理代码块标记
    if "```html" in content:
        content = re.search(r"```html(.*?)```", content, re.DOTALL).group(1)
    elif "```" in content:
        content = re.search(r"```(.*?)```", content, re.DOTALL).group(1)
            
    return content.strip()

def send_mail(html_body):
    log("📧 正在推送到邮箱...")
    msg = MIMEMultipart()
    msg['Subject'] = f"✨ {today_str} 核心资产追踪 × 🧬 学术前沿雷达 🎀"
    msg['From'], msg['To'] = SENDER_EMAIL, RECEIVER_EMAIL
    
    final_html = f"""
    <html>
    <body style="font-family: -apple-system, sans-serif; line-height: 1.6; color: #334155; max-width: 800px; margin: 0 auto; padding: 20px;">
        <h2 style="text-align: center; color: #1e40af;">🌤️ QUANT + MEDICINE BRIEFING</h2>
        <p style="text-align: center; font-size: 13px; color: #94a3b8;">{today_str} · 星际与医学周报</p>
        <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0;">
        {html_body}
    </body>
    </html>
    """
    msg.attach(MIMEText(final_html, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL, CC_EMAIL], msg.as_string())
        log("🎉 日报已精准空投到邮箱。")
    except Exception as e:
        log(f"❌ 发信失败：{str(e)}")

if __name__ == '__main__':
    log("🎬 脚本启动 (2026 可爱蒸馏版)")
    report = run_task()
    if report:
        send_mail(report)
        log("✨ 今日任务完美闭合。")
    else:
        sys.exit(1)
