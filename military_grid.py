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
# 2. 【全维度投研 + 拓展优选 + 科研浪漫 指令】
# ==========================================
SEARCH_PROMPT = f"""
今天是 {today_str}。请你作为资深A股买方研究员兼医学情报分析师，执行定向任务。

【绝对硬性指令 - 严禁交白卷】：
1. 🏭【行业精要】（2-4条）：搜索“国防军工”、“智能电网”与“新能源”的重大产业政策。
2. ⚖️【板块仓位建议】：给出上述核心板块的初步投资建议（加仓/减仓/观望）。
3. 🧬【学术级医药前沿】（2-4条）：搜索过去48小时内全球前沿医学突破或顶级医学期刊的重磅研究。
   - 核心摘要要求（极度重要）：用一段连续的话（4-6句话）介绍该研究，必须包含以下信息，并严格按以下带有序号的顺序表达：
     ① 研究团队：写出具体研究机构或团队名称（如某大学、研究所或医院），并简要说明该团队的研究方向。不允许使用“某研究团队”“研究人员”等模糊表述。
     ② 研究问题：说明该研究试图解决什么具体的科学或临床问题。
     ③ 技术方法：说明研究采用的核心技术、实验方法或治疗策略。
     ④ 核心突破：说明相比既有研究，这项工作的核心创新点。要求：绝对避免空泛表述（如“提供新思路”“带来希望”）。
     ⑤ 潜在意义：说明该研究的潜在医学价值或未来应用场景。
4. 🌟【优选自选股雷达】（1-2只）：从医药、军工、电网、新能源板块中，精选近期基本面极佳或资金抢筹的优质个股推荐加入自选。
5. 🎯【核心金股量价追踪】：必须且只能分析【航发科技、航天动力、航发控制、奥瑞德、长江电力、多氟多、英维克】。
   - 【资金面】：复盘主力资金动向。
   - 【关键点位】：测算近期【支撑位】与【压力位】。
   - 【历史长线】：简述目前处于历史的什么阶段。
   - 【操作建议】：给出加/减仓建议及理由。
6. 💌【专属浪漫彩蛋】：原创一句文艺、深情、极具美感且每天绝对不重样的浪漫情话。

🚨【强制 JSON 输出格式】（必须严格按以下 JSON 输出，不要有 markdown 嵌套）：
{{
    "sector_news": [
        {{"title": "标题", "summary": "摘要。🎯 逻辑：一句话利好逻辑"}}
    ],
    "sector_advice": "综合建议...",
    "medical_news": [
        {{"title": "文献标题", "journal": "期刊来源", "summary": "核心机制或临床意义"}}
    ],
    "watchlist_recommendations": [
        {{"name": "股票名称", "ticker": "代码", "sector": "所属板块", "logic": "基本面与资金面推荐逻辑"}}
    ],
    "focus_stocks": [
        {{
            "name": "航发科技", 
            "fund_flow": "主力/机构资金动向",
            "key_levels": "支撑位X元，压力位Y元",
            "history_trend": "长线位置", 
            "advice": "加减仓建议", 
            "reason": "理由"
        }}
        // ... 其他5只股票严格遵循此结构填入
    ],
    "romantic_quote": "原创不重样文艺情话"
}}
"""

# ==========================================
# 3. 抓取逻辑与防抖重试
# ==========================================
def fetch_news_from_coze(max_retries=3):
    print(f"🕵️‍♂️ 正在执行全维度投研侦察...")
    headers = {'Authorization': f'Bearer {coze_token}', 'Content-Type': 'application/json'}
    payload = {
        "bot_id": coze_bot_id, "user_id": "quant_master", "stream": False,
        "additional_messages": [{"role": "user", "content": SEARCH_PROMPT, "content_type": "text"}]
    }

    for attempt in range(max_retries):
        try:
            res = requests.post('https://api.coze.cn/v3/chat', headers=headers, json=payload).json()
            if res.get('code') != 0: 
                time.sleep(5)
                continue
                
            chat_id, conversation_id = res['data']['id'], res['data']['conversation_id']
            
            while True:
                ret = requests.get(f'https://api.coze.cn/v3/chat/retrieve?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers).json()
                status = ret.get('data', {}).get('status')
                if status == 'completed': break
                elif status in ['failed', 'canceled']: raise Exception("抓取异常中断")
                time.sleep(2)
                
            msgs = requests.get(f'https://api.coze.cn/v3/chat/message/list?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers).json()
            content = next((msg.get('content') for msg in msgs.get('data', []) if msg.get('type') == 'answer'), "")
            
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                raise Exception("JSON 解析失败")
                
        except Exception as e:
            print(f"❌ 第 {attempt+1} 次失败: {e}")
            time.sleep(5)
            
    return None

# ==========================================
# 4. 金融终端级 HTML 排版引擎
# ==========================================
def format_html_for_email(data):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body style="margin: 0; padding: 15px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f3f4f6;">
        <div style="max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.05);">
            
            <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 25px 20px; border-bottom: 3px solid #38bdf8;">
                <h2 style="margin: 0; font-size: 22px; font-weight: 600; letter-spacing: 0.5px;">⚡ 私董会级 | 全维度研报与前沿雷达</h2>
                <p style="margin: 8px 0 0 0; font-size: 13px; color: #94a3b8;">{today_str} · 量价寻道 × 医学前沿</p>
            </div>

            <div style="padding: 24px 20px;">
    """

    # --- 🧬 医学科研雷达 ---
    html += """<div style="display: flex; align-items: center; margin-bottom: 15px;"><span style="font-size: 20px; margin-right: 8px;">🧬</span><h3 style="margin: 0; color: #0f172a; font-size: 18px;">全球医药前沿雷达</h3></div>"""
    medical_items = data.get('medical_news', [])
    if not medical_items:
        html += "<p style='color: #64748b; font-size: 14px;'>今日暂无重磅医学前沿资讯更新。</p>"
    else:
        for item in medical_items:
            html += f"""
                    <div style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 16px; margin-bottom: 16px; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
                        <h4 style="margin: 0 0 8px 0; color: #065f46; font-size: 15px; line-height: 1.5;">{item.get('title', '')}</h4>
                        <div style="display: inline-block; background: #d1fae5; color: #047857; font-size: 11px; padding: 3px 8px; border-radius: 12px; font-weight: 600; margin-bottom: 8px;">来源: {item.get('journal', '')}</div>
                        <p style="margin: 0; font-size: 14px; color: #064e3b; line-height: 1.6;">{item.get('summary', '')}</p>
                    </div>
            """

    # --- 🌟 优选自选股推荐 ---
    html += """<div style="display: flex; align-items: center; margin-top: 35px; margin-bottom: 15px;"><span style="font-size: 20px; margin-right: 8px;">🌟</span><h3 style="margin: 0; color: #0f172a; font-size: 18px;">优选自选股拓源</h3></div>"""
    recommendations = data.get('watchlist_recommendations', [])
    if not recommendations:
        html += "<p style='color: #64748b; font-size: 14px;'>今日盘面分化，暂无高确定性新标的推荐。</p>"
    else:
        for rec in recommendations:
            html += f"""
                <div style="background: linear-gradient(to right, #fffbeb, #fef3c7); border: 1px solid #fde68a; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                    <div style="margin-bottom: 8px;">
                        <span style="font-size: 16px; font-weight: bold; color: #b45309;">{rec.get('name', '')}</span>
                        <span style="font-size: 13px; color: #d97706; margin-left: 6px;">({rec.get('ticker', '')})</span>
                        <span style="float: right; font-size: 12px; background: #fef08a; color: #854d0e; padding: 2px 8px; border-radius: 4px;">{rec.get('sector', '')}</span>
                    </div>
                    <p style="margin: 0; font-size: 14px; color: #92400e; line-height: 1.6;"><b>💡 入选逻辑：</b>{rec.get('logic', '')}</p>
                </div>
            """

    # --- 🎯 核心金股量价追踪 ---
    html += """<div style="display: flex; align-items: center; margin-top: 35px; margin-bottom: 15px;"><span style="font-size: 20px; margin-right: 8px;">🎯</span><h3 style="margin: 0; color: #0f172a; font-size: 18px;">核心资产深度量价追踪</h3></div>"""
    focus_stocks = data.get('focus_stocks', [])
    if not focus_stocks:
         html += "<p style='color: #64748b; font-size: 14px;'>数据解析延迟，请稍后重试。</p>"
    else:
        for stock in focus_stocks:
            name = stock.get('name', '未知')
            advice = stock.get('advice', '观望')
            
            advice_color, bg_color, border_color = "#f97316", "#fff7ed", "#ffedd5" # 默认橙色观望
            if "加" in advice or "多" in advice: 
                advice_color, bg_color, border_color = "#ef4444", "#fef2f2", "#fee2e2" # 红色看多
            elif "减" in advice or "空" in advice: 
                advice_color, bg_color, border_color = "#10b981", "#ecfdf5", "#d1fae5" # 绿色看空
            
            html += f"""
                    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.02); overflow: hidden;">
                        
                        <div style="background: {bg_color}; border-bottom: 1px solid {border_color}; padding: 12px 16px; display: table; width: 100%; box-sizing: border-box;">
                            <div style="display: table-cell; vertical-align: middle;">
                                <span style="font-size: 16px; font-weight: bold; color: #1e293b;">{name}</span>
                            </div>
                            <div style="display: table-cell; text-align: right; vertical-align: middle;">
                                <span style="background: {advice_color}; color: #ffffff; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: bold;">{advice}</span>
                            </div>
                        </div>

                        <div style="padding: 16px;">
                            <table width="100%" style="border-collapse: collapse; margin-bottom: 12px; font-size: 13px;">
                                <tr>
                                    <td width="50%" style="padding: 8px; background: #f8fafc; border-right: 2px solid #ffffff; border-radius: 6px 0 0 6px;">
                                        <div style="color: #64748b; margin-bottom: 4px;">📊 关键点位</div>
                                        <div style="color: #0f172a; font-weight: 500;">{stock.get('key_levels', '暂无测算')}</div>
                                    </td>
                                    <td width="50%" style="padding: 8px; background: #f8fafc; border-radius: 0 6px 6px 0;">
                                        <div style="color: #64748b; margin-bottom: 4px;">🌊 资金面动向</div>
                                        <div style="color: #0f172a; font-weight: 500;">{stock.get('fund_flow', '暂无数据')}</div>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0 0 8px 0; font-size: 13.5px; color: #475569; line-height: 1.6;">
                                <span style="color: #64748b; font-weight: 600;">📈 长线锚定：</span>{stock.get('history_trend', '')}
                            </p>
                            <p style="margin: 0; font-size: 13.5px; color: {advice_color}; font-weight: bold; line-height: 1.5; padding-top: 6px; border-top: 1px dashed #e2e8f0;">
                                💡 操盘理由：{stock.get('reason', '')}
                            </p>
                        </div>
                    </div>
            """

    # --- 🏭 宏观与行业精要 ---
    html += """<div style="display: flex; align-items: center; margin-top: 35px; margin-bottom: 15px;"><span style="font-size: 20px; margin-right: 8px;">🏭</span><h3 style="margin: 0; color: #0f172a; font-size: 18px;">行业政策与大盘环境</h3></div>"""
    sector_items = data.get('sector_news', [])
    for item in sector_items:
        summary = item.get('summary', '').replace('🎯 逻辑：', '<br><span style="color: #0284c7; font-weight: bold;">🎯 逻辑：</span>')
        html += f"""
                <div style="margin-bottom: 12px; padding-left: 12px; border-left: 3px solid #cbd5e1;">
                    <h4 style="margin: 0 0 4px 0; color: #334155; font-size: 15px;">{item.get('title', '')}</h4>
                    <p style="margin: 0; font-size: 13.5px; color: #475569; line-height: 1.6;">{summary}</p>
                </div>
        """

    # --- 💌 专属浪漫情话模块 ---
    romantic_quote = data.get('romantic_quote', '今天也要开心呀。')
    html += f"""
            </div>
            
            <div style="background: linear-gradient(135deg, #fff0f3 0%, #ffe4e6 100%); padding: 30px 20px; text-align: center; border-top: 1px dashed #fda4af;">
                <div style="font-size: 26px; margin-bottom: 12px;">💌</div>
                <p style="margin: 0; font-size: 15px; color: #be123c; line-height: 1.8; font-family: 'Kaiti', 'STKaiti', serif; font-style: italic; letter-spacing: 1px;">
                    "{romantic_quote}"
                </p>
            </div>

            <div style="background-color: #f8fafc; text-align: center; padding: 16px; color: #94a3b8; font-size: 11px; border-top: 1px solid #e2e8f0;">
                ⚠ AI 模型测算支撑压力位及个股推荐仅供复盘参考，绝不构成投资建议。
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
    print("📧 正在发送终极双轨定制邮件...")
    if not all([smtp_server, sender_email, sender_password, receiver_email]):
        print("❌ 邮件配置不全！")
        return

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Cc'] = cc_email
    msg['Subject'] = f"⚡ {today_str} 核心资产与优选雷达 × 🧬 医学前沿"
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
    data = fetch_news_from_coze(max_retries=3)
    if not data: 
        print("❌ 抓取失败，停止发送。")
        return
    html_content = format_html_for_email(data)
    send_email(html_content)

if __name__ == '__main__':
    main()
