import os
import requests
import json
import re
import time
import asyncio
import edge_tts
from datetime import datetime, timedelta, timezone

# ==========================================
# 1. 读取我们的“通行证”
# ==========================================
coze_token = os.getenv('COZE_API_TOKEN')
coze_bot_id = os.getenv('COZE_BOT_ID')
pushplus_token = os.getenv('PUSHPLUS_TOKEN')

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
# 4. 生成专供语音朗读的纯文本台本
# ==========================================
def format_text_for_audio(data):
    # 模拟电台主播口吻
    script = f"早上好！今天是{today_str}。欢迎收听今日全球宏观与市场详报。\n\n"
    
    script += "首先为您播报今日核心要闻。\n"
    for idx, item in enumerate(data.get('top_news', []), 1):
        script += f"第{idx}条，{item.get('title', '无标题')}。{item.get('summary', '无摘要')}\n\n"
    
    script += "接下来是市场情绪与焦点观察。\n"
    script += f"{data.get('market_focus', '暂无观察数据')}\n\n"

    script += "主要市场行情综述方面。\n"
    indices = data.get('market_indices', {})
    script += f"沪深A股：{indices.get('A_shares', '暂无数据')}\n"
    script += f"港股市场：{indices.get('HK_shares', '暂无数据')}\n"
    script += f"美股市场：{indices.get('US_shares', '暂无数据')}\n\n"

    script += "大宗商品期货方面。\n"
    commodities = data.get('commodities', {})
    script += f"黄金：{commodities.get('gold', '暂无数据')}\n"
    script += f"白银：{commodities.get('silver', '暂无数据')}\n"
    script += f"原油：{commodities.get('crude_oil', '暂无数据')}\n\n"
    
    script += "最后为您带来市场脉搏简报。\n"
    briefings = data.get('briefings', [])
    if briefings:
        for b in briefings:
            script += f"{b.get('category', '简报')}：{b.get('content', '无内容')}\n"
    
    script += "\n以上就是今天的全部内容，感谢您的收听，祝您生活愉快。"
    return script

# ==========================================
# 5. 合成语音 MP3
# ==========================================
async def generate_audio(audio_script):
    print("🎙️ 正在召唤 AI 播音员 (晓晓) 录制新闻音频...")
    voice = "zh-CN-XiaoxiaoNeural" # 微软晓晓，知性女声
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
# 6. 上传 MP3 到云端获取链接
# ==========================================
def upload_audio(file_path):
    print("☁️ 正在将音频上传至云端生成播放链接...")
    try:
        with open(file_path, 'rb') as f:
            # 使用 catbox 免费文件托管服务
            files = {'fileToUpload': f}
            data = {'reqtype': 'fileupload'}
            res = requests.post('https://catbox.moe/user/api.php', data=data, files=files, timeout=30)
            if res.status_code == 200:
                audio_url = res.text
                print(f"✅ 音频上传成功！链接: {audio_url}")
                return audio_url
            else:
                print(f"❌ 上传失败，状态码: {res.status_code}")
                return None
    except Exception as e:
        print(f"❌ 上传过程发生异常: {e}")
        return None

# ==========================================
# 7. 生成微信文字排版并推送 (带语音链接版)
# ==========================================
def format_and_push_wechat(data, audio_link):
    print("📲 正在排版并推送至微信...")
    
    # 【核心改动】：顶部的日期前缀与语音播报入口
    msg_content = f"## 📅 {today_str} - 🎙️ 您的专属宏观与市场早报\n\n"
    
    if audio_link:
        msg_content += f"### 👉 **[点击此处，直接收听今日早报语音版]({audio_link})** 👈\n\n---\n\n"
    else:
        msg_content += "*(⚠️ 今日音频生成或上传失败，请阅读以下文字版)*\n\n---\n\n"
    
    # 下方保留文字版，方便扫读
    msg_content += "### 📌 【今日核心要闻】\n"
    for idx, item in enumerate(data.get('top_news', []), 1):
        msg_content += f"**{idx}. {item.get('title', '无标题')}**\n"
        msg_content += f"> {item.get('summary', '无摘要')}\n"
        msg_content += f"[🔗 来源链接]({item.get('url', '#')})\n\n"
    msg_content += "---\n"
    
    msg_content += "### 👁️ 【市场情绪与焦点观察】\n"
    msg_content += f"{data.get('market_focus', '暂无观察数据')}\n\n---\n"

    indices = data.get('market_indices', {})
    msg_content += "### 🌐 【主要市场行情综述】\n"
    msg_content += f"- **🇨🇳 沪深 A 股**\n  {indices.get('A_shares', '暂无数据')}\n\n"
    msg_content += f"- **🇭🇰 港股市场**\n  {indices.get('HK_shares', '暂无数据')}\n\n"
    msg_content += f"- **🇺🇸 美股市场**\n  {indices.get('US_shares', '暂无数据')}\n\n---\n"

    commodities = data.get('commodities', {})
    msg_content += "### 🛢️ 【大宗商品期货综述】\n"
    msg_content += f"- **🥇 黄金**\n  {commodities.get('gold', '暂无数据')}\n\n"
    msg_content += f"- **🥈 白银**\n  {commodities.get('silver', '暂无数据')}\n\n"
    msg_content += f"- **🛢️ 原油**\n  {commodities.get('crude_oil', '暂无数据')}\n\n---\n"
    
    msg_content += "### 📰 【市场脉搏简报】\n"
    briefings = data.get('briefings', [])
    if briefings:
        for b in briefings:
            msg_content += f"- **[{b.get('category', '简报')}]** {b.get('content', '无内容')}\n\n"
    else:
        msg_content += "- 暂无异动或重大投资简报\n\n"

    # 推送请求
    url = 'http://www.pushplus.plus/send'
    push_data = {
        "token": pushplus_token,
        "title": f"🎙️ {today_str} 宏观市场早报已送达",
        "content": msg_content,
        "template": "markdown"
    }
    
    try:
        res = requests.post(url, json=push_data)
        if res.json().get('code') == 200:
            print("✅ 微信推送成功！请查收！")
        else:
            print(f"❌ 微信推送失败：{res.json()}")
    except Exception as e:
        print(f"❌ 推送请求异常: {e}")

# ==========================================
# 🚀 主运行控制台
# ==========================================
async def main():
    # 1. 抓取数据
    report_data = fetch_news_from_coze()
    if not report_data:
        print("流程异常结束：未获取到有效数据。")
        return

    # 2. 生成语音台本
    audio_script = format_text_for_audio(report_data)

    # 3. 合成 MP3 音频文件
    audio_file_path = await generate_audio(audio_script)
    
    # 4. 上传音频获取云端链接
    audio_link = None
    if audio_file_path:
        audio_link = upload_audio(audio_file_path)

    # 5. 生成图文排版并合并链接推送到微信
    format_and_push_wechat(report_data, audio_link)
    
    print("🎉 今日全部自动化任务圆满完成！")

if __name__ == '__main__':
    asyncio.run(main())
