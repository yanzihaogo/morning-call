import os
import requests
import json
import re
import time  # 新增了时间模块，用来等待 AI 抓取

# ==========================================
# 1. 读取我们的“通行证”
# ==========================================
coze_token = os.getenv('COZE_API_TOKEN')
coze_bot_id = os.getenv('COZE_BOT_ID')
pushplus_token = os.getenv('PUSHPLUS_TOKEN')

# ==========================================
# 2. 定义你想抓取的主题
# ==========================================
SEARCH_PROMPT = """
请帮我抓取今天关于以下几个主题的最新重要新闻，总共精选 5-8 条即可：
1. 半导体与芯片行业动态
2. 航空航天板块及相关个股消息
3. A股市场重磅宏观消息

请务必使用插件进行全网搜索。
严格输出纯 JSON 数组格式，不要有任何多余的开场白。
JSON字段需包含：title(标题), summary(摘要,50字左右), url(链接), time(时间)。
"""

def fetch_news_from_coze():
    print("🕵️‍♂️ 正在派出 Coze 特工潜入全网搜集情报...")
    
    headers = {
        'Authorization': f'Bearer {coze_token}',
        'Content-Type': 'application/json'
    }
    
    # 【第一步】下达指令，发起对话任务
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
        print("✅ 任务已下达，等待特工抓取数据 (这可能需要十几秒，请耐心等待)...")
        
        # 【第二步】轮询查岗：问 AI 抓完没有
        retrieve_url = f'https://api.coze.cn/v3/chat/retrieve?chat_id={chat_id}&conversation_id={conversation_id}'
        while True:
            ret = requests.get(retrieve_url, headers=headers).json()
            status = ret.get('data', {}).get('status')
            
            if status == 'completed':
                print("✅ 抓取完成！")
                break
            elif status in ['failed', 'canceled', 'requires_action']:
                print(f"❌ 抓取任务异常中断，状态: {status}")
                return None
            
            # 没完成的话，等 2 秒再查一遍
            time.sleep(2)
            
        # 【第三步】任务确认完成后，去收发室取信件（提取最终结果）
        msg_url = f'https://api.coze.cn/v3/chat/message/list?chat_id={chat_id}&conversation_id={conversation_id}'
        msgs_res = requests.get(msg_url, headers=headers).json()
        
        content = ""
        for msg in msgs_res.get('data', []):
            if msg.get('type') == 'answer':
                content = msg.get('content')
                break
        
        print("📥 收到情报，正在解码...")
        
        # 提取真正的 JSON 数据
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            print("❌ 解码失败，AI 返回的内容不是标准 JSON。返回原文看一眼：")
            print(content)
            return None
            
    except Exception as e:
        print(f"❌ 抓取过程中遭遇未知阻击: {e}")
        return None

def push_to_wechat(news_list):
    if not news_list:
        print("⚠️ 报告老板，今天没有获取到有效新闻，放弃推送。")
        return

    print(f"✅ 成功解析 {len(news_list)} 条新闻，正在排版发往微信...")
    
    # 组装漂亮的 Markdown 推文
    msg_content = "## 📈 您的专属财经与科技早报\n\n"
    for idx, item in enumerate(news_list, 1):
        title = item.get('title', '未知标题')
        summary = item.get('summary', '无摘要内容')
        url = item.get('url', '#')
        time_str = item.get('time', '刚刚')
        
        msg_content += f"### {idx}. {title}\n"
        msg_content += f"⏱ **时间**: {time_str}\n\n"
        msg_content += f"📝 **摘要**: {summary}\n\n"
        msg_content += f"🔗 [点击阅读原文]({url})\n\n"
        msg_content += "---\n"

    url = 'http://www.pushplus.plus/send'
    data = {
        "token": pushplus_token,
        "title": "📰 今日核心情报已送达",
        "content": msg_content,
        "template": "markdown"
    }
    
    res = requests.post(url, json=data)
    if res.json().get('code') == 200:
        print("🚀 推送成功！请查收微信！")
    else:
        print(f"❌ 推送失败：{res.json()}")

if __name__ == '__main__':
    news_data = fetch_news_from_coze()
    if news_data:
        push_to_wechat(news_data)
    else:
        print("流程异常结束。")
