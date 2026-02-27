import feedparser
import requests
import os
from datetime import datetime
import re

# ================= 1. 获取云端环境的密码 =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

# ================= 2. 新闻源抓取 =================
print("☀️ 正在抓取早报新闻...")
rss_sources = {
    "宏观大局": ["https://www.caixin.com/rss/"],
    "市场风向": ["https://xueqiu.com/statuses/hot.rss"],
    "全球视野": ["https://cn.reuters.com/rss"]
}

news_data = []
for category, urls in rss_sources.items():
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]: # 每个源抓取前5条最重要的
                news_data.append(f"板块：{category} | 标题：{entry.title}")
        except Exception as e:
            print(f"抓取 {url} 失败: {e}")

raw_news = "\n".join(news_data)

# ================= 3. 呼叫 Gemini 整理排版 =================
print("🧠 正在请 Gemini 撰写早报...")
prompt = f"""
你是一位贴心的财经播报员。请根据以下抓取的新闻标题，整理一份《今日财经早报》。
要求：
1. 面向中老年长辈，语言大白话，不讲复杂术语，直接说结论。
2. 使用 Markdown 格式，多用 Emoji 表情（比如 📈, 💰, 🚨, 💡）让版面生动。
3. 结构分为：【🌅 早安问候】、【🔥 今日最重要三件事】、【📊 市场在关注什么】。
4. 整体字数控制在 500 字左右，确保排版极其清晰，不需要大段文字，用短句。

今日新闻素材：
{raw_news}
"""

gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
headers = {'Content-Type': 'application/json'}
payload = {
    "contents": [{"parts": [{"text": prompt}]}]
}

response = requests.post(gemini_url, headers=headers, json=payload)
result = response.json()
morning_report = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "抱歉，今天的新闻整理小助手睡过头了...")

# ================= 4. 推送到微信 =================
print("📲 正在推送到微信...")
today_date = datetime.now().strftime("%Y年%m月%d日")

push_url = "http://www.pushplus.plus/send"
push_data = {
    "token": PUSHPLUS_TOKEN,
    "title": f"☕ {today_date} 财经早报，请查收！",
    "content": morning_report,
    "template": "markdown" # 使用 markdown 模板，微信里渲染出来排版会很好看
}

push_res = requests.post(push_url, json=push_data)
if push_res.status_code == 200:
    print("✅ 微信推送成功！")
else:
    print("❌ 推送失败：", push_res.text)