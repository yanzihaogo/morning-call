import os
import requests
import json
import re

# ==========================================
# 1. 读取我们的“通行证”
# ==========================================
coze_token = os.getenv('COZE_API_TOKEN')
coze_bot_id = os.getenv('COZE_BOT_ID')
pushplus_token = os.getenv('PUSHPLUS_TOKEN')

# ==========================================
# 2. 定义你想抓取的主题（随时可以改！）
# ==========================================
# 你可以在这里写特定网址，也可以写全网搜索的关键词
SEARCH_PROMPT = """
请帮我抓取今天关于以下几个主题的最新重要新闻，总共精选 5-8 条即可：
1. 半导体与芯片行业动态
2. A股市场重磅宏观消息
3. AI人工智能最新进展

请务必使用插件进行全网搜索。
严格输出纯 JSON 数组格式，不要有任何多余的开场白。
JSON字段需包含：title(标题), summary(摘要,50字左右), url(链接), time(时间)。
"""

def fetch_news_from_coze():
    print("🕵️‍♂️ 正在派出 Coze 特工潜入全网搜集情报...")
    url = 'https://api.coze.cn/v3/chat'
    headers = {
        'Authorization': f'Bearer {coze_token}',
        'Content-Type': 'application/json'
    }
    payload = {
        "bot_id": coze_bot_id,
        "user_id": "quant_master", # 给你起个霸气的代号
        "stream": False,
        "additional_messages": [{"role": "user", "content": SEARCH_PROMPT, "content_type": "text"}]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        res_json = response.json()
        
        # 提取回答内容
        content = ""
        for msg in res_json.get('data', {}).get('messages', []):
            if msg.get('type') == 'answer':
                content = msg.get('content')
                break
        
        print("📥 收到情报，正在解码...")
        
        # 核心：用正则表达式把 JSON 抠出来，防止 AI 说废话导致报错
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            news_list = json.loads(json_match.group())
            return news_list
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
    
    # 将 JSON 数据组装成 Markdown 格式的漂亮推文
    msg_content = "## 📈 您的专属财经与科技早报\n\n"
    
    for idx, item in enumerate(news_list, 1):
        title = item.get('title', '未知标题')
        summary = item.get('summary', '无摘要内容')
        url = item.get('url', '#')
        time = item.get('time', '刚刚')
        
        msg_content += f"### {idx}. {title}\n"
        msg_content += f"⏱ **时间**: {time}\n\n"
        msg_content += f"📝 **摘要**: {summary}\n\n"
        msg_content += f"🔗 [点击阅读原文]({url})\n\n"
        msg_content += "---\n"

    url = 'http://www.pushplus.plus/send'
    data = {
        "token": pushplus_token,
        "title": "📰 今日核心情报已送达",
        "content": msg_content,
        "template": "markdown" # 使用 markdown 模板，微信里看非常清爽
    }
    
    res = requests.post(url, json=data)
    if res.json().get('code') == 200:
        print("🚀 推送成功！请查收微信！")
    else:
        print(f"❌ 推送失败：{res.json()}")

if __name__ == '__main__':
    # 1. 抓取新闻
    news_data = fetch_news_from_coze()
    
    # 2. 推送微信
    if news_data:
        push_to_wechat(news_data)
    else:
        print("流程异常结束。")
