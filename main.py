import os
import requests
import feedparser
from datetime import datetime

# ================= 1. 配置信息 =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

# ================= 2. 严肃新闻抓取 =================
def get_news():
    rss_sources = {
        "宏观政策": ["https://www.caixin.com/rss/"],
        "市场动态": ["https://xueqiu.com/statuses/hot.rss"],
        "全球资讯": ["https://cn.reuters.com/rss"]
    }
    news_items = []
    for cat, urls in rss_sources.items():
        for url in urls:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                news_items.append(f"【{cat}】{entry.title}")
    return "\n".join(news_items)

# ================= 3. Gemini 专业总结 =================
def get_gemini_report(raw_content):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""
    你是一名资深金融分析师。请根据以下素材撰写一份《每日金融内参》。
    要求：
    1. 风格：极其严肃、客观、书面化，严禁使用表情包或活泼语气。
    2. 结构：
       - [今日头条]：选1条最重磅的消息进行深度解读。
       - [宏观要闻]：概括3-4条政策或经济数据变动。
       - [市场观察]：简述当前市场情绪与趋势。
    3. 格式：输出为纯文本，每个部分用明确的标题区分。
    
    素材：
    {raw_content}
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    res = requests.post(url, json=payload).json()
    return res['candidates'][0]['content']['parts'][0]['text']

# ================= 4. 构建 HTML 视觉模板 =================
def create_html(report_text):
    today = datetime.now().strftime("%Y-%m-%d")
    # 这里是一个精美的 HTML 模板，模拟纸质报纸的质感
    html_template = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'serif'; padding: 40px; background: #f4f4f4; color: #333; }}
            .container {{ background: white; padding: 40px; border-top: 8px solid #a00; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; border-bottom: 2px solid #333; margin-bottom: 30px; padding-bottom: 20px; }}
            h1 {{ margin: 0; font-size: 32px; letter-spacing: 2px; }}
            .date {{ color: #666; margin-top: 10px; }}
            .content {{ line-height: 1.8; font-size: 18px; white-space: pre-wrap; }}
            .section-title {{ font-weight: bold; color: #a00; border-left: 4px solid #a00; padding-left: 10px; margin: 30px 0 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>每日财经内参</h1>
                <div class="date">{today} | 首席分析师人工智选</div>
            </div>
            <div class="content">{report_text}</div>
        </div>
    </body>
    </html>
    """
    return html_template

# ================= 5. 执行与推送 =================
if __name__ == "__main__":
    # 1. 获取并总结
    news = get_news()
    report = get_gemini_report(news)
    html_content = create_html(report)
    
    # 2. 推送至 PushPlus (由于图片转换在 GitHub Actions 比较重，
    # 我们先用 PushPlus 的 HTML 模板实现类似图片的排版效果)
    # 这样无需生成实体图片，但在微信里看起来像是一张精美的长文。
    push_data = {
        "token": PUSHPLUS_TOKEN,
        "title": f"📈 {datetime.now().strftime('%m月%d日')} 财经内参",
        "content": html_content,
        "template": "html"
    }
    requests.post("http://www.pushplus.plus/send", json=push_data)
    print("✅ 内参已送达")
