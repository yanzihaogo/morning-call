import os
import smtplib
import sys
import re
import time
import google.generativeai as genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone

# 【日志函数】用于在 GitHub Actions 日志中显示进度，方便排查卡在哪里
def log(message):
    bj_time = datetime.now(timezone(timedelta(hours=8))).strftime('%H:%M:%S')
    print(f"[{bj_time}] {message}")
    sys.stdout.flush()

# ==========================================
# 1. 基础配置与安全检查
# ==========================================
# 从环境变量读取敏感信息（GitHub Secrets）
API_KEY = os.getenv('GOOGLE_API_KEY')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')
RECEIVER_EMAIL = "779825335@qq.com"
CC_EMAIL = "15757699818@163.com"

# 检查环境变量是否完整，防止脚本空转
if not all([API_KEY, SMTP_SERVER, SENDER_EMAIL, SENDER_PASSWORD]):
    log("❌ 错误：环境变量配置不全，请检查 GitHub Secrets。")
    sys.exit(1)

# 初始化 Gemini 引擎
try:
    genai.configure(api_key=API_KEY)
    # 使用 1.5 Pro 模型，它的逻辑推理和学术理解力远超 Flash
    model = genai.GenerativeModel('gemini-1.5-pro')
    log("✅ Gemini 引擎初始化成功")
except Exception as e:
    log(f"❌ Gemini 初始化失败：{str(e)}")
    sys.exit(1)

# 获取北京时间字符串
bj_tz = timezone(timedelta(hours=8))
today_str = datetime.now(bj_tz).strftime('%Y年%m月%d日')

# ==========================================
# 2. 定义【博士级】蒸馏指令 (Prompt)
# ==========================================
# 标的名单：航发、电力、多氟多、英维克、中国能建、中国船舶、云南锗业
STOCKS = ["航发科技", "航天动力", "航发控制", "长江电力", "多氟多", "英维克", "中国能建", "中国船舶", "云南锗业"]

PROMPT = f"""
今天是 {today_str}。你现在是一名服务于医学博士与量化交易员的高级助理。
你的任务是进行[逻辑蒸馏]，严禁输出“里程碑意义”、“前景广阔”等万金油废话。

### 模块一：🧬 医学博士学术雷达 (受众: 医学博士)
- **来源**：检索并综述 NEJM, Lancet, Cell, Nature 等顶刊最新研究。
- **强制约束**：若涉及药物，必须在括号内标注具体的【药物通用名 (Generic Name)】。
- **结构**：每篇综述不少于 250 字，必须包含：
    ① 研究团队及核心方向；
    ② 科学痛点（标注药物通用名）；
    ③ 技术方法与实验模型（如 in vivo/single-cell）；
    ④ 核心突破（具体的通路、指标提升数据）；
    ⑤ 未来转化临床意义。
- **排版样式**：使用 <div style="background-color: #f0fdf4; border-left: 5px solid #10b981; padding: 15px; border-radius: 8px; margin-bottom: 20px;">。

### 模块二：🎯 核心资产四维复盘 (标的: {', '.join(STOCKS)})
- **要求**：针对这 9 只股票进行深度分析，每只不少于 180 字。
- **分析维度**：[量价筹码]、[资金面异动]、[基本面核心逻辑]、[确定性策略建议]。
- **宏观对冲**：需关联当日造船板价格、锗/镓出口景气度、人民币汇率对标的的定价影响。
- **排版样式**：使用 <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 10px; margin-bottom: 15px;">。

### 模块三：💌 浪漫彩蛋
- **禁令**：严禁出现任何金融、交易、医学术语。文学性要强。
- **排版样式**：使用 <div style="background: linear-gradient(135deg, #fff1f2 0%, #fae8ff 100%); padding: 25px; text-align: center; border-radius: 15px;">。

请直接返回可用于 HTML 邮件的正文代码。
"""

# ==========================================
# 3. 任务执行逻辑
# ==========================================
def run_task():
    log("📡 正在向 Gemini 发起深度采编请求...")
    try:
        # generation_config 用于控制生成质量，设置较小的温度值增加确定性
        response = model.generate_content(
            PROMPT,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=8000  # 确保字数足够长
            )
        )
        
        content = response.text
        # 处理可能带有的 Markdown 代码块标签
        if "```html" in content:
            content = re.search(r"```html(.*?)```", content, re.DOTALL).group(1)
        elif "```" in content:
            content = re.search(r"```(.*?)```", content, re.DOTALL).group(1)
            
        log("✅ 报告内容生成成功")
        return content.strip()
    except Exception as e:
        log(f"❌ Gemini 生成内容时发生异常：{str(e)}")
        return None

def send_mail(html_body):
    log("📧 正在准备发送邮件...")
    msg = MIMEMultipart()
    msg['Subject'] = f"⚡ {today_str} 核心资产追踪 × 🧬 医学博士学术雷达"
    msg['From'], msg['To'] = SENDER_EMAIL, RECEIVER_EMAIL
    
    # 注入全局 CSS 确保在手机阅读时文字大小适中，不局促
    final_html = f"""
    <html>
    <body style="font-family: -apple-system, system-ui, BlinkMacSystemFont, 'Segoe UI', Roboto; line-height: 1.6; color: #334155; padding: 10px;">
        {html_body}
    </body>
    </html>
    """
    
    msg.attach(MIMEText(final_html, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL, CC_EMAIL], msg.as_string())
        log("🎉 邮件已成功送达目标邮箱。")
    except Exception as e:
        log(f"❌ 邮件发送失败：{str(e)}")

# ==========================================
# 🚀 启动入口
# ==========================================
if __name__ == '__main__':
    log("🎬 脚本已启动")
    report_content = run_task()
    if report_content:
        send_mail(report_content)
        log("✨ 今日自动化流程顺利完成。")
    else:
        log("⚠️ 流程中断：未能获取到有效的 AI 生成内容。")
        sys.exit(1)
