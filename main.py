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
# 1. 读取我们的“通行证”与“邮箱配置”
# ==========================================
coze_token = os.getenv('COZE_API_TOKEN')
coze_bot_id = os.getenv('COZE_BOT_ID')

# 新增的邮件配置（稍后需要在 GitHub Secrets 里配置）
smtp_server = os.getenv('SMTP_SERVER')       # 例如: smtp.qq.com 或 smtp.163.com
sender_email = os.getenv('SENDER_EMAIL')     # 你的发件邮箱地址
sender_password = os.getenv('SENDER_PASSWORD') # 你的邮箱授权码（注意：不是登录密码）
receiver_email = os.getenv('RECEIVER_EMAIL')   # 你父亲的收件邮箱地址

# ==========================================
# 2. 动态生成时间，锁定24小时内的新闻
# ==========================================
tz_bj = timezone(timedelta(hours=8))
now_bj = datetime.now(tz_bj)
today_str = now_bj.strftime('%Y年%m月%d日')
yesterday_str = (now_bj - timedelta(days=1)).strftime('%Y年%m月%d日')

SEARCH_PROMPT = f"""
今天是 {today_str}。请立即执行每日宏观市场与商品行情数据深度抓取。

【防重复死命令】：
1. 搜索范围必须严格限定在 {yesterday_str} 到 {today_str} 这过去 24 小时内发生的新闻。
2. 绝对不要播报几天前已经发酵过的旧新闻，除非今天有重大的、实质性的最新进展。
3. 严格按预设 JSON 格式返回。
"""

# ==========================================
# 3. 抓取逻辑 (Coze 特工)
# ==========================================
def fetch_news_from_coze():
    print(f"🕵️‍♂️ 正在潜入全网搜集 {today_str} 的客观行情情报...")
    headers = {
        'Authorization': f'Bearer {coze_token}',
        'Content-Type': 'application/json'
    }
    
    chat_url = 'https://api.coze.cn/v3/chat'
    payload = {
        "bot_id": coze_bot_id,
        "user_id": "quant_master", 
        "stream": False,
        "additional_messages": [{"role": "user", "content": SEARCH_PROMPT, "content_type": "text"}]
    }

    try:
        res = requests.post(chat_url, headers=headers, json=payload).json()
        if res.get('code') != 0:
            print(f"❌ 发起任务失败: {res}")
            return None
            
        chat_id = res['data']['id']
        conversation_id = res['data']['conversation_id']
        print("✅ 任务已下达，特工正在深度检索全网数据 (约需十几秒)...")
        
        retrieve_url = f'https://api.coze.cn/v3/chat/retrieve?chat_id={chat_id}&conversation_id={conversation_id}'
        while True:
            ret = requests.get(retrieve_url, headers=headers).json()
            status = ret.get('data', {}).get('status')
            
            if status == 'completed':
                break
            elif status in ['failed', 'canceled', 'requires_action']:
                print(f"❌ 抓取任务异常中断，状态: {status}")
                return None
            time.sleep(2)
            
        msg_url = f'https://api.coze.cn/v3/chat/message/list?chat_id={chat_id}&conversation_id={conversation_id}'
        msgs_res = requests.get(msg_url, headers=headers).json()
        
        content = ""
        for msg in msgs_res.get('data', []):
            if msg.get('type') == 'answer':
                content = msg.get('content')
                break
        
        print("📥 收到情报，正在解码 JSON...")
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            print("❌ 解码失败，返回原文：\n", content)
            return None
            
    except Exception as e:
        print(f"❌ 抓取异常: {e}")
        return None

# ==========================================
# 4. 生成专供语音朗读的清洗版台本
# ==========================================
def clean_for_speech(text):
    if not text:
        return "无内容"
    text = re.sub(r'http[s]?://\S+', '', text)
    text = re.sub(r'来源链接[:：]?\s*', '', text)
    text = re.sub(r'数据来源[:：]?\s*', '', text)
    text = re.sub(r'\[.*?\]\(.*?\)', '', text)
    return text.strip()

def format_text_for_audio(data):
    script = f"早上好！今天是{today_str}。欢迎收听今日全球宏观与市场详报。\n\n"
    
    script += "首先为您播报今日核心要闻。\n"
    for idx, item in enumerate(data.get('top_news', []), 1):
        clean_title = clean_for_speech(item.get('title', '无标题'))
        clean_summary = clean_for_speech(item.get('summary', '无摘要'))
        script += f"第{idx}条，{clean_title}。{clean_summary}\n\n"
    
    script += "接下来是市场情绪与焦点观察。\n"
    script += f"{clean_for_speech(data.get('market_focus', '暂无观察数据'))}\n\n"

    script += "主要市场行情综述方面。\n"
    indices = data.get('market_indices', {})
    script += f"沪深A股：{clean_for_speech(indices.get('A_shares', '暂无数据'))}\n"
    script += f"港股市场：{clean_for_speech(indices.get('HK_shares', '暂无数据'))}\n"
    script += f"美股市场：{clean_for_speech(indices.get('US_shares', '暂无数据'))}\n\n"

    script += "大宗商品期货方面。\n"
    commodities = data.get('commodities', {})
    script += f"黄金：{clean_for_speech(commodities.get('gold', '暂无数据'))}\n"
    script += f"白银：{clean_for_speech(commodities.get('silver', '暂无数据'))}\n"
    script += f"原油：{clean_for_speech(commodities.get('crude_oil', '暂无数据'))}\n\n"
    
    script += "最后为您带来市场脉搏简报。\n"
    briefings = data.get('briefings', [])
    if briefings:
        for b in briefings:
            cat = clean_for_speech(b.get('category', '简报'))
            con = clean_for_speech(b.get('content', '无内容'))
            script += f"{cat}：{con}\n"
    
    script += "\n以上就是今天的全部内容，感谢您的收听，祝您生活愉快。"
    return script

# ==========================================
# 5. 生成供邮件阅读的图文排版
# ==========================================
def format_text_for_email(data):
    msg_content = f"【{today_str} - 您的专属宏观与市场早报】\n\n"
    msg_content += "🎧 语音播报已作为附件发送，请点击下方附件收听。\n\n"
    msg_content += "-" * 30 + "\n\n"
    
    msg_content += "📌 【今日核心要闻】\n"
    for idx, item in enumerate(data.get('top_news', []), 1):
        msg_content += f"{idx}. {item.get('title', '无标题')}\n"
        msg_content += f"   摘要：{item.get('summary', '无摘要')}\n"
        msg_content += f"   来源：{item.get('url', '无链接')}\n\n"
    
    msg_content += "👁️ 【市场情绪与焦点观察】\n"
    msg_content += f"{data.get('market_focus', '暂无观察数据')}\n\n"

    indices = data.get('market_indices', {})
    msg_content += "🌐 【主要市场行情综述】\n"
    msg_content += f"🇨🇳 沪深 A 股: {indices.get('A_shares', '暂无数据')}\n"
    msg_content += f"🇭🇰 港股市场: {indices.get('HK_shares', '暂无数据')}\n"
    msg_content += f"🇺🇸 美股市场: {indices.get('US_shares', '暂无数据')}\n\n"

    commodities = data.get('commodities', {})
    msg_content += "🛢️ 【大宗商品期货综述】\n"
    msg_content += f"🥇 黄金: {commodities.get('gold', '暂无数据')}\n"
    msg_content += f"🥈 白银: {commodities.get('silver', '暂无数据')}\n"
    msg_content += f"🛢️ 原油: {commodities.get('crude_oil', '暂无数据')}\n\n"
    
    msg_content += "📰 【市场脉搏简报】\n"
    briefings = data.get('briefings', [])
    if briefings:
        for b in briefings:
            msg_content += f"[{b.get('category', '简报')}] {b.get('content', '无内容')}\n"
    else:
        msg_content += "暂无异动或重大投资简报\n"

    return msg_content

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
# 7. 核心：发送带附件的邮件
# ==========================================
def send_email_with_attachment(email_body, attachment_path):
    print("📧 正在打包邮件并发送...")
    
    # 检查环境变量是否配置齐全
    if not all([smtp_server, sender_email, sender_password, receiver_email]):
        print("❌ 邮件配置不全！请检查 GitHub Secrets 中的 SMTP_SERVER, SENDER_EMAIL, SENDER_PASSWORD, RECEIVER_EMAIL。")
        return

    # 构建邮件主体
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = f"🎙️ {today_str} 全球宏观与市场详报"

    # 添加邮件正文
    msg.attach(MIMEText(email_body, 'plain', 'utf-8'))

    # 添加 MP3 附件
    if attachment_path and os.path.exists(attachment_path):
        try:
            with open(attachment_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
            part['Content-Disposition'] = f'attachment; filename="Morning_Call_{today_str}.mp3"'
            msg.attach(part)
            print("✅ 附件已成功挂载。")
        except Exception as e:
            print(f"❌ 挂载附件时发生错误: {e}")
    else:
        print("⚠️ 未找到音频文件，将仅发送纯文本邮件。")

    # 连接 SMTP 服务器并发送
    try:
        # 大多数主流邮箱使用 465 端口和 SSL
        server = smtplib.SMTP_SSL(smtp_server, 465)
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        print("🎉 邮件发送成功！请查收邮箱！")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

# ==========================================
# 🚀 主运行控制台
# ==========================================
async def main():
    report_data = fetch_news_from_coze()
    if not report_data:
        print("流程异常结束：未获取到有效数据。")
        return

    # 生成邮件图文排版
    email_text = format_text_for_email(report_data)

    # 语音台本清洗并录制
    audio_script = format_text_for_audio(report_data)
    audio_file_path = await generate_audio(audio_script)
    
    # 发送带附件的终极邮件
    send_email_with_attachment(email_text, audio_file_path)

if __name__ == '__main__':
    asyncio.run(main())
