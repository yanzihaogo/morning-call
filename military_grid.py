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
# 2. 深度定制 Prompt
# ==========================================
STOCKS = ["航发科技", "航天动力", "航发控制", "长江电力", "多氟多", "英维克", "中国能建", "中国船舶", "云南锗业"]

PROMPT = f"""
今天是 {today_str}。请为我的量化交易员及医学博士女友生成一份精致的[极简蒸馏版]日报。

### 🎨 排版规范：
- 使用 Emoji 增加亲和力 (🤖, ⚔️, 🔋, 💎, 🏦, 🧬)。
- 行业资讯必须按板块【分行列表】，严禁写成一长段文字。
- 医学摘要必须对核心结论进行 **<u>加粗并划线</u>**。

### 📦 模块指令：

#### 🌐 全球板块风向标 (精简分行版)
- 分类罗列：人工智能、军工装备、电池、小金属/贵金属、银行、多元金融。
- 格式：每板块一行，使用“•”符号。描述对投资逻辑的直接影响。

#### 🧬 医学博士学术精要 (受众: 博士女友)
- 内容：精选 2 篇顶刊文献。
- 结构：[研究背景]、[方法/突破]、[转化价值]。
- **深度要求**：单篇字数不少于 200 字。严禁万金油废话，必须提到具体的[药物通用名]和实验数据。核心结论强制加粗划线。
- 样式：包裹在 <div style="background-color: #f0fdf4; padding: 20px; border-radius: 12px; margin-bottom: 25px;">。

#### 📊 资产四维精读 (标的: {', '.join(STOCKS)})
- 内容：每只标的 120 字左右。
- 包含：核心逻辑、支撑/压力位、操作建议。
- 样式：包裹在 <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 20px; border-radius: 12px; margin-bottom: 15px;">。

#### 💖 专属浪漫粉色彩蛋
- 样式：包裹在 <div style="background: linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%); padding: 30px; text-align: center; border-radius: 15px; color: #be123c; font-weight: bold;">。

请直接输出 HTML 源码。
"""

# ==========================================
# 3. 核心逻辑
# ==========================================
def run_task():
    # 2026年优先使用 Gemini 2.5 Pro
    model_id = 'gemini-2.5-pro'
    log(f"📡 正在调用 {model_id} 进行深度逻辑蒸馏...")
    
    try:
        response = client.models.generate_content(model=model_id, contents=PROMPT)
        content = response.text
        
        # 清理可能存在的 Markdown 代码块标签
        content = re.sub(r'```html|```', '', content).strip()
        return content
    except Exception as e:
        log(f"❌ Gemini 调用失败: {str(e)}")
        return None

def send_mail(html_body):
    log("📧 正在打包并推送到邮箱...")
    msg = MIMEMultipart()
    msg['Subject'] = f"✨ {today_str} 资产周报 × 🧬 博士雷达 🎀"
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    
    # 强制注入 CSS 基础设置以解决移动端乱码和排版问题
    final_html = f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, sans-serif; line-height: 1.6; color: #334155; max-width: 750px; margin: 0 auto; padding: 15px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h2 style="color: #1e40af; margin-bottom: 5px;">🌤️ Daily Intelligence</h2>
            <p style="color: #94a3b8; font-size: 12px;">QUANT + MEDICINE INSIGHTS</p>
        </div>
        {html_body}
        <p style="text-align: center; color: #cbd5e1; font-size: 11px; margin-top: 40px;">&copy; 2026SJ Capt. Desk · 仅供内部交流</p>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(final_html, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL, CC_EMAIL], msg.as_string())
        log("✅ 日报发送成功。")
    except Exception as e:
        log(f"❌ 发信失败: {str(e)}")

if __name__ == '__main__':
    log("🎬 脚本启动...")
    report = run_task()
    if report:
        send_mail(report)
    else:
        sys.exit(1)
