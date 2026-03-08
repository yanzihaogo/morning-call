import os
import requests
import json
import re
import time
import asyncio
import edge_tts
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta, timezone

# ==========================================
# 1. 配置中心 (直发你和女朋友的邮箱)
# ==========================================
coze_token = os.getenv('COZE_API_TOKEN')
coze_bot_id = os.getenv('COZE_BOT_ID')

smtp_server = os.getenv('SMTP_SERVER')       
sender_email = os.getenv('SENDER_EMAIL')     
sender_password = os.getenv('SENDER_PASSWORD') 

# 收件人直接设定为你，抄送女朋友
receiver_email = "779825335@qq.com"   
cc_email = "15757699818@163.com"     

tz_bj = timezone(timedelta(hours=8))
now_bj = datetime.now(tz_bj)
today_str = now_bj.strftime('%Y年%m月%d日')
yesterday_str = (now_bj - timedelta(days=1)).strftime('%Y年%m月%d日')

# ==========================================
# 2. 【行业与个股专属投研指令】
# ==========================================
SEARCH_PROMPT = f"""
今天是 {today_str}。请你作为资深A股军工与智能电网行业研究员，执行定向投研任务。

【定向采编与投研指令】（必须严格遵守）：
1. 🏭【行业精要】（2-4条）：重点搜索过去24-48小时内，A股“国防军工/航空航天”与“智能电网/特高压/电力设备”的重大产业政策、行业订单、突发事件。
2. ⚖️【板块仓位建议】：基于上述基本面与大盘资金情绪，分别对“军工板块”和“电网板块”给出明确的初步投资建议（强制输出：加仓、减仓、或 观望），并附带简短的15字核心逻辑。
3. 🎯【核心个股深度追踪】（极度重要）：必须单独搜索以下4只股票的最新公告、主力资金动向或相关题材催化：
   - 航发科技 (600391)
   - 航天动力 (600343)
   - 航发控制 (000738)
   - 奥瑞德 (600666)
   针对每一只股票，给出最新动态简述，并基于量价或基本面给出明确的【操作建议】（加仓/减仓/持有/观望）及一句话理由。
4. 严格按照预设的JSON格式返回数据，确保个股名称完全匹配。
"""

# ==========================================
# 3. 抓取逻辑
# ==========================================
def fetch_news_from_coze():
    print(f"🕵️‍♂️ 正在执行【军工/电网】行业及个股定向侦察...")
    headers = {'Authorization': f'Bearer {coze_token}', 'Content-Type': 'application/json'}
    payload = {
        "bot_id": coze_bot_id, "user_id": "quant_master", "stream": False,
        "additional_messages": [{"role": "user", "content": SEARCH_PROMPT, "content_type": "text"}]
    }

    try:
        res = requests.post('https://api.coze.cn/v3/chat', headers=headers, json=payload).json()
        if res.get('code') != 0: return None
        chat_id, conversation_id = res['data']['id'], res['data']['conversation_id']
        
        while True:
            ret = requests.get(f'https://api.coze.cn/v3/chat/retrieve?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers).json()
            if ret.get('data', {}).get('status') == 'completed': break
            time.sleep(2)
            
        msgs = requests.get(f'https://api.coze.cn/v3/chat/message/list?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers).json()
        content = next((msg.get('content') for msg in msgs.get('data', []) if msg.get('type') == 'answer'), "")
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        return json.loads(json_match.group()) if json_match else None
    except Exception as e:
        print(f"❌ 抓取异常: {e}"); return None

# ==========================================
# 4. 生成语音台本
# ==========================================
def clean_for_speech(text):
    if not text: return "无内容"
    return re.sub(r'http[s]?://\S+|\[.*?\]\(.*?\)', '', text).strip()

def format_text_for_audio(data):
    script = f"您好，今天是{today_str}。欢迎收听军工与电网行业专属定向研报。\n\n"
    
    script += "首先是行业精要与板块建议。\n"
    for item in data.get('sector_news', data.get('top_news', [])):
        script += f"{clean_for_speech(item.get('title'))}。{clean_for_speech(item.get('summary'))}\n"
    
    script += f"\n综合板块建议：\n{clean_for_speech(data.get('sector_advice', data.get('market_focus', '暂无板块综合建议')))}\n\n"
    
    script += "接下来是您特别关注的核心个股异动追踪。\n"
    # 兼容两种可能的 JSON 结构
    focus_stocks = data.get('focus_stocks', data.get('briefings', []))
    for stock in focus_stocks:
        name = clean_for_speech(stock.get('name', stock.get('category', '未知股票')))
        news = clean_for_speech(stock.get('news', stock.get('content', '暂无动态')))
        advice = clean_for_speech(stock.get('advice', '暂无建议'))
        script += f"{name}：{news}。操作建议：{advice}。\n\n"
        
    script += "本研报操作建议仅供参考，请结合盘面实际情况决策。祝您投资顺利。"
    return script

# ==========================================
# 5. 生成工业风 HTML 排版
# ==========================================
def format_html_for_email(data):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body style="margin: 0; padding: 20px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #eef2f6;">
        <div style="max-width: 650px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; border: 1px solid #cbd5e1; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            
            <div style="background: linear-gradient(90deg, #1e293b 0%, #334155 100%); color: #ffffff; padding: 20px; border-bottom: 4px solid #3b82f6;">
                <h2 style="margin: 0; font-size: 22px;">⚡ 电网 × 军工 | 定向行业研报</h2>
                <p style="margin: 5px 0 0 0; font-size: 13px; color: #94a3b8;">{today_str} · 专属个股追踪</p>
            </div>

            <div style="background-color: #f0fdf4; border-left: 4px solid #22c55e; padding: 12px 20px; margin: 20px 20px 0 20px; font-size: 14px; color: #166534;">
                <b>🎧 研报语音版：</b> 请点击邮件底部的 <b>.mp3 附件</b> 直接收听。
            </div>

            <div style="padding: 20px;">
    """

    # --- 行业精要 ---
    html += """<h3 style="color: #0f172a; border-bottom: 2px solid #cbd5e1; padding-bottom: 8px; font-size: 18px; margin-top: 5px;">🏭 行业精要与板块推演</h3>"""
    for item in data.get('sector_news', data.get('top_news', [])):
        title = item.get('title', '无标题')
        summary = item.get('summary', '无摘要')
        summary = summary.replace('🎯 逻辑：', '<br><span style="color: #2563eb; font-weight: bold;">🎯 逻辑：</span>')
        html += f"""
                <div style="margin-bottom: 15px;">
                    <h4 style="margin: 0 0 5px 0; color: #334155; font-size: 15.5px;">▪ {title}</h4>
                    <p style="margin: 0; font-size: 14px; color: #475569; line-height: 1.6;">{summary}</p>
                </div>
        """

    # --- 板块操作建议 ---
    html += f"""
                <div style="background-color: #fff1f2; border: 1px solid #fda4af; padding: 15px; border-radius: 6px; margin-top: 20px;">
                    <h4 style="margin: 0 0 8px 0; color: #be123c; font-size: 15px;">⚖️ 行业整体仓位建议</h4>
                    <p style="margin: 0; font-size: 14px; color: #881337; line-height: 1.6;">
                        {data.get('sector_advice', data.get('market_focus', '暂无建议'))}
                    </p>
                </div>
    """

    # --- 重点个股追踪 ---
    html += """<h3 style="color: #0f172a; border-bottom: 2px solid #cbd5e1; padding-bottom: 8px; font-size: 18px; margin-top: 35px;">🎯 专属个股深度追踪</h3>"""
    focus_stocks = data.get('focus_stocks', data.get('briefings', []))
    for stock in focus_stocks:
        name = stock.get('name', stock.get('category', '未知'))
        news = stock.get('news', stock.get('content', '无最新动态'))
        advice = stock.get('advice', '暂无')
        reason = stock.get('reason', '')
        
        # 动态颜色标识加减仓
        advice_color = "#ea580c" # 默认橙色 (观望)
        if "加" in advice or "多" in advice: advice_color = "#dc2626" # 红色
        elif "减" in advice or "空" in advice: advice_color = "#16a34a" # 绿色
        
        html += f"""
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 6px; margin-bottom: 15px; position: relative;">
                    <div style="position: absolute; top: 15px; right: 15px; background: {advice_color}; color: white; padding: 3px 10px; border-radius: 4px; font-size: 12px; font-weight: bold;">
                        建议：{advice}
                    </div>
                    <h4 style="margin: 0 0 8px 0; color: #1e293b; font-size: 16px;">🏢 {name}</h4>
                    <p style="margin: 0 0 8px 0; font-size: 14px; color: #475569; line-height: 1.6;"><b>最新动态：</b>{news}</p>
                    <p style="margin: 0; font-size: 13px; color: {advice_color}; font-weight: bold;">💡 操盘理由：{reason}</p>
                </div>
        """

    html += """
            </div>
            <div style="background-color: #f1f5f9; text-align: center; padding: 15px; color: #64748b; font-size: 11px; border-top: 1px solid #e2e8f0;">
                ⚠ AI 投研模型给出的加减仓建议仅基于公开资讯与量价基础推演，绝不构成任何直接投资建议。股市有风险，入市需谨慎。
            </div>
        </div>
    </body>
    </html>
    """
    return html

# ==========================================
# 6. 语音与发送流程
# ==========================================
async def generate_audio(audio_script):
    print("🎙️ 正在录制行业专属音频...")
    try:
        await edge_tts.Communicate(audio_script, "zh-CN-YunxiNeural", rate="+5%").save("sector_news.mp3")
        return "sector_news.mp3"
    except Exception as e:
        print(f"❌ 音频失败: {e}"); return None

def send_email_with_attachment(html_body, attachment_path):
    print("📧 正在发送定向研报邮件...")
    msg = MIMEMultipart()
    msg['From'], msg['To'], msg['Cc'] = sender_email, receiver_email, cc_email
    msg['Subject'] = f"⚡ {today_str} 军工与电网定向研报及个股追踪"
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    if attachment_path:
        with open(attachment_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
        part['Content-Disposition'] = f'attachment; filename="Sector_Report_{today_str}.mp3"'
        msg.attach(part)
    try:
        server = smtplib.SMTP_SSL(smtp_server, 465)
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, [receiver_email, cc_email], msg.as_string())
        server.quit()
        print(f"✅ 定向研报发送成功！")
    except Exception as e: print(f"❌ 邮件发送失败: {e}")

async def main():
    data = fetch_news_from_coze()
    if not data: return
    audio_path = await generate_audio(format_text_for_audio(data))
    send_email_with_attachment(format_html_for_email(data), audio_path)

if __name__ == '__main__':
    asyncio.run(main())
