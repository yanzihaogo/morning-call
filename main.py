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
# 1. 配置中心 
# ==========================================
coze_token = os.getenv('COZE_API_TOKEN')
coze_bot_id = os.getenv('COZE_BOT_ID')

smtp_server = os.getenv('SMTP_SERVER')       
sender_email = os.getenv('SENDER_EMAIL')     
sender_password = os.getenv('SENDER_PASSWORD') 
receiver_email = os.getenv('RECEIVER_EMAIL')   

cc_email = "15757699818@163.com"     
monitor_email = "779825335@qq.com"  

# ==========================================
# 2. 动态生成时间与【记忆账本】
# ==========================================
tz_bj = timezone(timedelta(hours=8))
now_bj = datetime.now(tz_bj)
today_str = now_bj.strftime('%Y年%m月%d日')
yesterday_str = (now_bj - timedelta(days=1)).strftime('%Y年%m月%d日')

HISTORY_FILE = "macro_news_history.txt"

def get_past_news():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return "".join([f"- {line}" for line in lines])
    return "暂无历史记录"

def save_new_history(data):
    # 提取今天的新闻标题和简报内容
    new_titles = []
    for item in data.get('top_news', []):
        if item.get('title'): new_titles.append(item.get('title'))
    for b in data.get('briefings', []):
        if b.get('content'): new_titles.append(b.get('content')[:20]) # 取简报前20个字作为特征
            
    if not new_titles: return

    # 读取旧记录并保留最近40条
    lines = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

    lines.extend(new_titles)
    lines = lines[-40:]

    # 存入小本本
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    print("✅ 宏观记忆账本已更新。")

# ==========================================
# 3. 抓取指令 (引入黑名单机制)
# ==========================================
past_news_list = get_past_news()

SEARCH_PROMPT = f"""
今天是 {today_str}。请执行每日全球宏观与产业资讯深度抓取。

🚨【绝对去重黑名单】（最高优先级指令）：
以下是我们过去几天已经报道过的新闻标题或事件。你【绝对不能】再次报道相同或高度相似的事件（无论媒体今天怎么重新解读）：
{past_news_list}

【投研级采编与极简字数指令】（必须严格遵守）：
1. 📌【今日核心要闻】（3-5条）：
   - 必须避开黑名单！
   - 字数极限压缩：每条要闻的摘要部分（含数据对比和逻辑推演）必须严格控制在 60-80 字以内！
   - 数据强制对比：遇到宏观数据或财报，只写“预期X，实际Y”。
   - 资产推演：在摘要末尾加上“🎯 逻辑：”，用一句话点透利好/利空哪个具体板块。
2. 📰【市场脉搏简报】（6-8条）：
   - 必须避开黑名单！
   - 字数极限压缩：每条简报总计不超过 50 字。
   - 末尾加上“💡 短评：”，点透资金博弈或产业链影响。
3. 严格按预设 JSON 格式返回。
"""

def fetch_news_from_coze(max_retries=3):
    print(f"🕵️‍♂️ 正在为 {today_str} 的长辈专版采编素材 (携带防重复账本)...")
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
                if ret.get('data', {}).get('status') == 'completed': break
                elif ret.get('data', {}).get('status') in ['failed', 'canceled']: raise Exception("中断")
                time.sleep(2)
                
            msgs = requests.get(f'https://api.coze.cn/v3/chat/message/list?chat_id={chat_id}&conversation_id={conversation_id}', headers=headers).json()
            content = next((msg.get('content') for msg in msgs.get('data', []) if msg.get('type') == 'answer'), "")
            
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match: return json.loads(json_match.group())
            else: raise Exception("JSON失败")
        except Exception as e:
            print(f"❌ 抓取重试 {attempt+1}: {e}")
            time.sleep(5)
    return None

# ==========================================
# 4. 生成专供语音朗读的清洗版台本
# ==========================================
def clean_for_speech(text):
    if not text: return "无内容"
    text = re.sub(r'http[s]?://\S+', '', text)
    text = re.sub(r'\[.*?\]\(.*?\)', '', text)
    return text.strip()

def format_text_for_audio(data):
    script = f"早上好！今天是{today_str}。欢迎收听今日全球宏观与市场详报。\n\n"
    script += "首先为您播报今日核心要闻。\n"
    for idx, item in enumerate(data.get('top_news', []), 1):
        script += f"第{idx}条，{clean_for_speech(item.get('title'))}。{clean_for_speech(item.get('summary'))}\n\n"
    
    script += "接下来是主要行情与焦点观察。\n"
    script += f"{clean_for_speech(data.get('market_focus'))}\n\n"
    
    indices = data.get('market_indices', {})
    script += f"A股：{clean_for_speech(indices.get('A_shares'))}。美股：{clean_for_speech(indices.get('US_shares'))}。\n\n"
    
    script += "最后为您带来市场脉搏简报。\n"
    for b in data.get('briefings', []):
        script += f"{clean_for_speech(b.get('category'))}：{clean_for_speech(b.get('content'))}\n"
    
    script += "\n以上就是今天的全部内容，祝您交易顺利。"
    return script

# ==========================================
# 5. 生成极其炫酷的 HTML 邮件排版 (原汁原味)
# ==========================================
def format_html_for_email(data):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 20px; font-family: 'Helvetica Neue', Helvetica, Arial, 'Microsoft Yahei', sans-serif; background-color: #f4f6f9;">
        <div style="max-width: 650px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
            
            <div style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); color: #ffffff; padding: 25px 20px; text-align: center;">
                <h2 style="margin: 0; font-size: 24px; letter-spacing: 1px;">🎙️ 全球宏观与市场晨报</h2>
                <p style="margin: 8px 0 0 0; font-size: 14px; color: #d1e0ff;">{today_str} · 机构级投研视野</p>
            </div>

            <div style="background-color: #fff8e1; border-left: 4px solid #ffc107; padding: 12px 20px; margin: 20px 20px 0 20px; border-radius: 4px; font-size: 14px; color: #5d4000;">
                <b>🎧 温馨提示：</b> 本期晨报语音版已作为 <b>邮件附件 (.mp3)</b> 发送，请点击底部附件直接收听。
            </div>

            <div style="padding: 20px;">
    """

    html += """<h3 style="color: #1e3c72; border-bottom: 2px solid #e1e4e8; padding-bottom: 8px; font-size: 18px; margin-top: 10px;">📌 今日核心要闻</h3>"""
    for idx, item in enumerate(data.get('top_news', []), 1):
        summary = item.get('summary', '无摘要')
        summary_html = summary.replace('🎯 逻辑：', '<br><span style="color: #e53935; font-weight: bold; font-size: 13px;">🎯 逻辑：</span><span style="color: #d32f2f; font-size: 13px;">') + ('</span>' if '🎯 逻辑：' in summary else '')
        html += f"""
                <div style="margin-bottom: 18px; padding: 15px; background-color: #f8fafc; border-radius: 8px; border-left: 4px solid #2a5298;">
                    <h4 style="margin: 0 0 8px 0; color: #0f172a; font-size: 16px;">{idx}. {item.get('title', '无标题')}</h4>
                    <p style="margin: 0; font-size: 14.5px; line-height: 1.6; color: #334155;">{summary_html}</p>
                </div>
        """

    indices = data.get('market_indices', {})
    commodities = data.get('commodities', {})
    html += f"""
                <h3 style="color: #1e3c72; border-bottom: 2px solid #e1e4e8; padding-bottom: 8px; font-size: 18px; margin-top: 30px;">🌐 市场情绪与关键行情</h3>
                <p style="font-size: 14.5px; line-height: 1.6; color: #334155; margin-bottom: 15px;">
                    <b>👁️ 焦点观察：</b>{data.get('market_focus', '暂无观察数据')}
                </p>
                <table width="100%" style="border-collapse: collapse; margin-bottom: 20px; font-size: 14px;">
                    <tr>
                        <td width="50%" style="padding: 10px; background: #f1f5f9; border-radius: 6px 0 0 6px;"><b>🇨🇳 A股：</b><br><span style="color: #475569;">{indices.get('A_shares', '暂无数据')}</span></td>
                        <td width="50%" style="padding: 10px; background: #e2e8f0; border-radius: 0 6px 6px 0;"><b>🇺🇸 美股：</b><br><span style="color: #475569;">{indices.get('US_shares', '暂无数据')}</span></td>
                    </tr>
                    <tr><td colspan="2" style="height: 10px;"></td></tr>
                    <tr>
                        <td width="50%" style="padding: 10px; background: #fffbeb; border-radius: 6px 0 0 6px;"><b>🥇 黄金：</b><br><span style="color: #475569;">{commodities.get('gold', '暂无数据')}</span></td>
                        <td width="50%" style="padding: 10px; background: #fef3c7; border-radius: 0 6px 6px 0;"><b>🛢️ 原油：</b><br><span style="color: #475569;">{commodities.get('crude_oil', '暂无数据')}</span></td>
                    </tr>
                </table>
    """

    html += """<h3 style="color: #1e3c72; border-bottom: 2px solid #e1e4e8; padding-bottom: 8px; font-size: 18px; margin-top: 30px;">📰 市场脉搏简报</h3>
                <ul style="padding-left: 20px; margin: 0; color: #334155; font-size: 14.5px; line-height: 1.7;">"""
    briefings = data.get('briefings', [])
    if briefings:
        for b in briefings:
            content = b.get('content', '无内容')
            content_html = content.replace('💡 短评：', '<br><span style="color: #ea580c; font-weight: bold; font-size: 13px;">💡 短评：</span><span style="color: #c2410c; font-size: 13px;">') + ('</span>' if '💡 短评：' in content else '')
            html += f"""<li style="margin-bottom: 12px;"><b>[{b.get('category', '简报')}]</b> {content_html}</li>"""
    else:
        html += "<li>暂无异动或重大投资简报</li>"

    html += """
                </ul>
            </div>
            <div style="background-color: #f8fafc; text-align: center; padding: 15px; color: #94a3b8; font-size: 12px; border-top: 1px solid #e2e8f0;">
                ⚠ 记账防重复系统已启用。本早报由 AI 自动化采编生成，所有推演仅供复盘参考。
            </div>
        </div>
    </body>
    </html>
    """
    return html

# ==========================================
# 6. 合成语音 MP3
# ==========================================
async def generate_audio(audio_script):
    print("🎙️ 正在召唤 AI 播音员 (晓晓) 录制新闻音频...")
    voice = "zh-CN-XiaoxiaoNeural"
    output_file = "daily_news.mp3"
    try:
        communicate = edge_tts.Communicate(audio_script, voice, rate="+5%")
        await communicate.save(output_file)
        print(f"✅ 音频录制完成！成功生成文件：{output_file}")
        return output_file
    except Exception as e:
        print(f"❌ 音频生成失败: {e}")
        return None

# ==========================================
# 7. 发送包含 HTML 的邮件
# ==========================================
def send_email_with_attachment(html_body, attachment_path):
    print("📧 正在打包 HTML 邮件并发送...")
    if not all([smtp_server, sender_email, sender_password, receiver_email]):
        print("❌ 邮件配置不全！")
        return

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Cc'] = f"{cc_email}, {monitor_email}"  
    msg['Subject'] = f"🎙️ {today_str} 全球宏观与市场详报"
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    if attachment_path and os.path.exists(attachment_path):
        try:
            with open(attachment_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
            part['Content-Disposition'] = f'attachment; filename="Morning_Call_{today_str}.mp3"'
            msg.attach(part)
        except Exception as e:
            print(f"❌ 挂载附件时发生错误: {e}")

    try:
        server = smtplib.SMTP_SSL(smtp_server, 465)
        server.login(sender_email, sender_password)
        to_addrs = [receiver_email, cc_email, monitor_email]
        server.sendmail(sender_email, to_addrs, msg.as_string())
        server.quit()
        print(f"✅ HTML 邮件已成功包含 MP3 附件发送至父亲，并抄送至女朋友和你自己的邮箱！")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

# ==========================================
# 🚀 主运行控制台
# ==========================================
async def main():
    report_data = fetch_news_from_coze(max_retries=3)
    if not report_data:
        print("❌ 严重错误：今天未获取到有效新闻数据，脚本已终止。")
        return

    audio_script = format_text_for_audio(report_data)
    audio_file_path = await generate_audio(audio_script)
    email_html = format_html_for_email(report_data)
    send_email_with_attachment(email_html, audio_file_path)
    
    # 【最后一步】：把今天发送的新闻写入宏观账本
    save_new_history(report_data)

if __name__ == '__main__':
    asyncio.run(main())
