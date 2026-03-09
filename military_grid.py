import os
import requests
import json
import re
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone

# ==========================================
# 1. 配置中心 
# ==========================================
coze_token = os.getenv('COZE_API_TOKEN')
coze_bot_id = os.getenv('COZE_BOT_ID')

smtp_server = os.getenv('SMTP_SERVER')       
sender_email = os.getenv('SENDER_EMAIL')     
sender_password = os.getenv('SENDER_PASSWORD') 

receiver_email = "779825335@qq.com"   
cc_email = "15757699818@163.com"     

tz_bj = timezone(timedelta(hours=8))
now_bj = datetime.now(tz_bj)
today_str = now_bj.strftime('%Y年%m月%d日')

# ==========================================
# 2. 【投研与浪漫双核指令】
# ==========================================
SEARCH_PROMPT = f"""
今天是 {today_str}。请你作为资深A股军工与智能电网行业研究员，兼具文艺感，执行定向任务。

【绝对硬性指令 - 严禁交白卷】：
1. 🏭【行业精要】（2-4条）：搜索“国防军工”与“智能电网”的重大产业政策或订单。如果是周末，请复盘上周五资金异动。
2. ⚖️【板块仓位建议】：给出军工和电网板块的初步投资建议（加仓/减仓/观望）。
3. 🎯【四只金股长短线双轨追踪】（绝对硬性要求）：必须且只能分析【航发科技、航天动力、航发控制、奥瑞德】。
   - 【近期动态】：复盘其最新的基本面、公告或资金面。
   - 【历史长线位置】（新增要求）：结合其过去1-3年的走势，简述其目前处于历史的什么阶段（如：超跌底部潜伏区、历史高位震荡、主升浪突破等），辅助判断长线安全边际。
   - 【操作建议】：给出操作建议及具体理由。
4. 💌【专属浪漫彩蛋】：在所有硬核分析结束后，请你原创一句文艺、深情、极具美感且每天绝对不重样的浪漫情话（约30-50字），作为今天的早安彩蛋。

🚨【强制 JSON 输出格式】（不要输出任何额外的 markdown 符号，严格按以下 JSON 输出）：
{{
    "sector_news": [
        {{"title": "行业新闻标题", "summary": "新闻摘要。🎯 逻辑：一句话利好逻辑"}}
    ],
    "sector_advice": "综合建议：加仓/减仓/观望。理由：...",
    "focus_stocks": [
        {{"name": "航发科技", "news": "近期动态复盘", "history_trend": "长线历史位置分析及所处阶段", "advice": "加仓/减仓/持有/观望", "reason": "具体理由"}},
        {{"name": "航天动力", "news": "近期动态复盘", "history_trend": "长线历史位置分析及所处阶段", "advice": "加仓/减仓/持有/观望", "reason": "具体理由"}},
        {{"name": "航发控制", "news": "近期动态复盘", "history_trend": "长线历史位置分析及所处阶段", "advice": "加仓/减仓/持有/观望", "reason": "具体理由"}},
        {{"name": "奥瑞德", "news": "近期动态复盘", "history_trend": "长线历史位置分析及所处阶段", "advice": "加仓/减仓/持有/观望", "reason": "具体理由"}}
    ],
    "romantic_quote": "原创的不重样文艺情话"
}}
"""

# ==========================================
# 3. 抓取逻辑
# ==========================================
def fetch_news_from_coze():
    print(f"🕵️‍♂️ 正在执行【军工/电网】行业投研及情话生成...")
    headers = {'Authorization': f'Bearer {coze_token}', 'Content-Type': 'application/json'}
    payload = {
        "bot_id": coze_bot_id, "user_id": "quant_master", "stream": False,
        "additional_messages": [{"role": "user", "content": SEARCH_PROMPT, "content_type": "text"}]
    }

    try:
        res = requests.post('https://api.coze.cn/v3/chat', headers=headers, json=payload).json()
        if res.get('code') != 0: 
            print("❌ 任务发起失败")
            return None
        chat_id, conversation_id = res['data']['id'], res['data']['conversation_id']
        
        while True:
            ret = requests.get(f'https://api.coze.cn/v3/chat/retrieve?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers).json()
            if ret.get('data', {}).get('status') == 'completed': break
            elif ret.get('data', {}).get('status') in ['failed', 'canceled']: return None
            time.sleep(2)
            
        msgs = requests.get(f'https://api.coze.cn/v3/chat/message/list?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers).json()
        content = next((msg.get('content') for msg in msgs.get('data', []) if msg.get('type') == 'answer'), "")
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                print("❌ JSON 解析失败")
                return None
        return None
    except Exception as e:
        print(f"❌ 抓取异常: {e}"); return None

# ==========================================
# 4. 生成工业风与浪漫结合的 HTML 排版
# ==========================================
def format_html_for_email(data):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body style="margin: 0; padding: 20px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #eef2f6;">
        <div style="max-width: 650px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #cbd5e1; box-shadow: 0 8px 16px rgba(0,0,0,0.06);">
            
            <div style="background: linear-gradient(90deg, #1e293b 0%, #334155 100%); color: #ffffff; padding: 25px 20px; border-bottom: 4px solid #3b82f6;">
                <h2 style="margin: 0; font-size: 22px; letter-spacing: 1px;">⚡ 电网 × 军工 | 专属投研内参</h2>
                <p style="margin: 6px 0 0 0; font-size: 13px; color: #94a3b8;">{today_str} · 长线视角解码</p>
            </div>

            <div style="padding: 20px;">
    """

    # --- 行业精要 ---
    html += """<h3 style="color: #0f172a; border-bottom: 2px solid #cbd5e1; padding-bottom: 8px; font-size: 18px; margin-top: 5px;">🏭 行业精要与板块推演</h3>"""
    sector_items = data.get('sector_news', [])
    if not sector_items:
        html += "<p style='color: #64748b; font-size: 14px;'>暂无重大行业资讯。</p>"
    else:
        for item in sector_items:
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
                        {data.get('sector_advice', '暂无建议')}
                    </p>
                </div>
    """

    # --- 重点个股追踪 (新增历史长线模块) ---
    html += """<h3 style="color: #0f172a; border-bottom: 2px solid #cbd5e1; padding-bottom: 8px; font-size: 18px; margin-top: 35px;">🎯 专属个股长短线追踪</h3>"""
    focus_stocks = data.get('focus_stocks', [])
    if not focus_stocks:
         html += "<p style='color: #64748b; font-size: 14px;'>个股数据生成失败，请检查 AI 接口状态。</p>"
    else:
        for stock in focus_stocks:
            name = stock.get('name', '未知')
            news = stock.get('news', '无最新动态')
            history_trend = stock.get('history_trend', '长线位置评估暂无')
            advice = stock.get('advice', '暂无')
            reason = stock.get('reason', '')
            
            advice_color = "#ea580c"
            if "加" in advice or "多" in advice: advice_color = "#dc2626" 
            elif "减" in advice or "空" in advice: advice_color = "#16a34a" 
            
            html += f"""
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 18px; border-radius: 8px; margin-bottom: 20px; position: relative;">
                        <div style="position: absolute; top: 18px; right: 18px; background: {advice_color}; color: white; padding: 4px 12px; border-radius: 4px; font-size: 13px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            建议：{advice}
                        </div>
                        <h4 style="margin: 0 0 12px 0; color: #1e293b; font-size: 17px; border-left: 4px solid #3b82f6; padding-left: 8px;">{name}</h4>
                        
                        <p style="margin: 0 0 8px 0; font-size: 14px; color: #475569; line-height: 1.6;">
                            <b style="color: #334155;">📰 近期动态：</b>{news}
                        </p>
                        
                        <div style="background-color: #f1f5f9; padding: 10px 12px; border-radius: 6px; margin-bottom: 10px; border-left: 3px solid #64748b;">
                            <p style="margin: 0; font-size: 13.5px; color: #334155; line-height: 1.5;">
                                <b>📈 长线位置评估：</b><br>{history_trend}
                            </p>
                        </div>

                        <p style="margin: 0; font-size: 13.5px; color: {advice_color}; font-weight: bold;">
                            💡 操盘理由：{reason}
                        </p>
                    </div>
            """

    # --- 💌 专属浪漫情话模块 ---
    romantic_quote = data.get('romantic_quote', '今天也要开心呀。')
    html += f"""
            </div>
            
            <div style="background: linear-gradient(135deg, #fff0f3 0%, #ffe4e6 100%); padding: 25px 30px; text-align: center; border-top: 1px dashed #fda4af;">
                <div style="font-size: 24px; margin-bottom: 10px;">💌</div>
                <p style="margin: 0; font-size: 15px; color: #be123c; line-height: 1.8; font-family: 'Kaiti', 'STKaiti', serif; font-style: italic; letter-spacing: 1px;">
                    "{romantic_quote}"
                </p>
            </div>

            <div style="background-color: #f8fafc; text-align: center; padding: 15px; color: #94a3b8; font-size: 11px; border-top: 1px solid #e2e8f0;">
                ⚠ AI 模型加减仓建议及长线推演仅供复盘参考，不构成实质投资建议。
            </div>
        </div>
    </body>
    </html>
    """
    return html

# ==========================================
# 5. 发送纯 HTML 邮件
# ==========================================
def send_email(html_body):
    print("📧 正在发送终极浪漫投研邮件...")
    if not all([smtp_server, sender_email, sender_password, receiver_email]):
        print("❌ 邮件配置不全！")
        return

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Cc'] = cc_email
    msg['Subject'] = f"⚡ {today_str} 军工与电网定向研报及个股长线追踪"
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        server = smtplib.SMTP_SSL(smtp_server, 465)
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, [receiver_email, cc_email], msg.as_string())
        server.quit()
        print(f"✅ 定向研报发送成功！")
    except Exception as e: 
        print(f"❌ 邮件发送失败: {e}")

# ==========================================
# 🚀 主控制流程
# ==========================================
def main():
    data = fetch_news_from_coze()
    if not data: 
        print("❌ 获取数据为空或 JSON 格式异常，停止发送。")
        return
    html_content = format_html_for_email(data)
    send_email(html_content)

if __name__ == '__main__':
    main()
