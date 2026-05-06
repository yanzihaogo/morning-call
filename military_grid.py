import os
import smtplib
import sys
import re
import google.generativeai as genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone

# 实时日志
def log(message):
    print(f"[{datetime.now(timezone(timedelta(hours=8))).strftime('%H:%M:%S')}] {message}")
    sys.stdout.flush()

# ==========================================
# 1. 配置中心
# ==========================================
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')
RECEIVER_EMAIL = "779825335@qq.com"
CC_EMAIL = "15757699818@163.com"

# 标的名录
STOCKS = ["航发科技", "航天动力", "航发控制", "长江电力", "多氟多", "英维克", "中国能建", "中国船舶", "云南锗业"]

# 配置 Gemini
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro') # 追求深度建议用 Pro，追求速度可以用 flash

# 时区处理
tz_bj = timezone(timedelta(hours=8))
today_str = datetime.now(tz_bj).strftime('%Y年%m月%d日')

# ==========================================
# 2. 博士级蒸馏提示词
# ==========================================
PROMPT = f"""
今天是 {today_str}。你现在是一位资深量化研究员与医学博士学术助手。请根据最新的实时数据与知识库，为用户生成一份[蒸馏版]深度内参。

### 🚨 核心逻辑原则 (必读)：
1. **拒绝废话**：严禁使用“里程碑意义”、“严谨实验”、“仅供参考”等万金油词汇。
2. **逻辑蒸馏**：内容不在多而在精。将复杂数据转化为可执行的逻辑。
3. **事实审计**：严禁臆测未披露财报。重点分析量价、资金大宗异动及产业链景气度。

### 📦 模块要求：

#### 1. 🧬 医学学术雷达 (受众: 医学博士)
- **要求**：检索 NEJM, Lancet, Cell 或 Nature 体系最新研究。
- **内容**：产出 2-3 篇综述。必须包含：团队、研究锚点、干预药物(括号标通用名 Generic Name) 及对临床路径的实质性突破。
- **样式**：包裹在 <div style="background-color: #f0fdf4; border-left: 5px solid #10b981; padding: 15px; border-radius: 8px; margin-bottom: 20px;"> 中。

#### 2. 🎯 核心资产深度复盘 (名单: {', '.join(STOCKS)})
- **要求**：必须全部涵盖，不得遗漏。
- **内容**：采用[量价-资金-基本面-策略]四维模型。每只标的 180 字以上深度分析。
- **大宗锚点**：需结合造船板价格、锗/镓报价、美债收益率对标的的定价影响。
- **样式**：包裹在 <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 10px; margin-bottom: 15px;"> 中。

#### 3. 💌 浪漫彩蛋
- **样式**：包裹在 <div style="background: linear-gradient(135deg, #fff1f2 0%, #fae8ff 100%); padding: 25px; text-align: center; border-radius: 15px;"> 中。
- **禁令**：严禁出现金融或医学词汇。

请直接输出完整的 HTML 格式邮件正文。
"""

# ==========================================
# 3. 运行逻辑
# ==========================================
def generate_report():
    log("🚀 正在调用 Gemini 1.5 Pro 进行深度逻辑蒸馏...")
    try:
        response = model.generate_content(PROMPT)
        # 提取 HTML 内容（处理 Markdown 代码块）
        html_content = response.text
        if "```html" in html_content:
            html_content = re.search(r"```html(.*?)```", html_content, re.DOTALL).group(1)
        elif "```" in html_content:
            html_content = re.search(r"```(.*?)```", html_content, re.DOTALL).group(1)
        return html_content.strip()
    except Exception as e:
        log(f"❌ Gemini 调用失败: {e}")
        return None

def send_email(content):
    log("📧 正在发送美化版日报...")
    msg = MIMEMultipart()
    msg['Subject'] = f"⚡ {today_str} 核心资产追踪 × 🧬 医学博士雷达 (Gemini Pro 版)"
    msg['From'], msg['To'] = SENDER_EMAIL, RECEIVER_EMAIL
    
    # 注入全局 CSS 修正
    styled_content = f"""
    <html>
    <body style="font-family: sans-serif; line-height: 1.6; color: #334155; max-width: 800px; margin: 0 auto; padding: 20px;">
        {content}
    </body>
    </html>
    """
    
    msg.attach(MIMEText(styled_content, 'html', 'utf-8'))
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, 465) as s:
            s.login(SENDER_EMAIL, SENDER_PASSWORD)
            s.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL, CC_EMAIL], msg.as_string())
        log("✅ 邮件推送成功！")
    except Exception as e:
        log(f"❌ 邮件发送失败: {e}")

if __name__ == '__main__':
    log("🎬 脚本启动...")
    report = generate_report()
    if report:
        send_email(report)
        log("✨ 今日任务完成。")
    else:
        sys.exit(1)
