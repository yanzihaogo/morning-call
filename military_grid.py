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
# 2. 精炼蒸馏指令 (禁止情话模块)
# ==========================================
STOCKS = ["航发科技", "航天动力", "航发控制", "长江电力", "多氟多", "英维克", "中国能建", "中国船舶", "云南锗业"]

PROMPT = f"""
今天是 {today_str}。请执行[极简蒸馏版]日报任务 ✨。

### 🎨 视觉要求：
1. 行业资讯必须按板块【分行列表】，严禁段落堆砌。
2. 医学摘要核心结论必须 **<u>加粗并划线</u>**。
3. **🚨 严禁生成任何情话或浪漫彩蛋模块。**

### 📦 模块指令：

#### 🌐 全球板块风向标
- 覆盖：人工智能🤖、军工装备⚔️、电池🔋、小金属/贵金属💎、银行🏦、多元金融📈。
- 格式：每板块独立一行，点出核心逻辑影响。

#### 🧬 医学博士学术精要
- 内容：综述 2 篇顶刊，每篇约 180 字。
- 包含：研究背景、[药物通用名]、方法突破、转化价值。
- 样式：使用背景色 #f0fdf4，圆角 12px，无竖条。

#### 📊 资产四维精读 (标的: {', '.join(STOCKS)})
- 内容：每只标的约 100 字。含核心逻辑、支撑/压力位、操作建议。
- 样式：使用背景色 #f8fafc，圆角 12px，边框 1px #e2e8f0。
"""

# ==========================================
# 3. 运行逻辑 (增加 429 容错处理)
# ==========================================
def run_task():
    # 鉴于配额紧张，将配额较多的 Flash 放在首位
    model_candidates = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-2.5-pro']
    content = None
    
    for model_id in model_candidates:
        for attempt in range(2): # 每个模型尝试 2 次
            log(f"📡 正在请求 {model_id} (第 {attempt+1} 次)...")
            try:
                response = client.models.generate_content(model=model_id, contents=PROMPT)
                content = response.text
                if content:
                    log(f"✅ {model_id} 生成成功")
                    return re.sub(r'```html|```', '', content).strip()
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg:
                    log(f"⚠️ 触发配额限制 (429)。由于每日请求数接近上限，请稍后再试或检查面板。")
                    if attempt == 0:
                        log("⏳ 等待 60 秒后进行最后一次规避重试...")
                        time.sleep(60)
                else:
                    log(f"❌ 错误: {err_msg}")
                    break # 非 429 错误直接跳过该模型
    return None

def send_mail(html_body):
    log("📧 打包推送到邮箱...")
    msg = MIMEMultipart()
    msg['Subject'] = f"✨ {today_str} 资产周报 × 🧬 博士雷达 (Gemini稳定版)"
    msg['From'], msg['To'] = SENDER_EMAIL, RECEIVER_EMAIL
    
    final_html = f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: sans-serif; line-height: 1.6; color: #334155; max-width: 750px; margin: 0 auto; padding: 15px;">
        <div style="text-align: center; margin-bottom: 25px;">
            <h2 style="color: #1e40af;">🌤️ Daily Intelligence</h2>
            <p style="color: #94a3b8; font-size: 12px;">QUANT + MEDICINE INSIGHTS</p>
        </div>
        {html_body}
        <p style="text-align: center; color: #cbd5e1; font-size: 11px; margin-top: 30px;">&copy; 2026 SJTU Captain's Desk</p>
    </body>
    </html>
    """
    msg.attach(MIMEText(final_html, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL, CC_EMAIL], msg.as_string())
        log("🎉 邮件发送成功！")
    except Exception as e:
        log(f"❌ 发信异常: {str(e)}")

if __name__ == '__main__':
    log("🎬 脚本启动 (抗压稳定版)...")
    report = run_task()
    if report:
        send_mail(report)
    else:
        log("❌ 任务失败：配额已完全耗尽或 API 暂时不可用。")
        sys.exit(1)
