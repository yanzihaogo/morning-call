import os
import requests
import feedparser
from datetime import datetime

# ================= 1. 配置信息 =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

# ================= 2. 抓取新闻 (换回你原本稳定好用的源) =================
def get_news():
    # 使用你最初验证过能成功抓取的稳定源
    rss_sources = {
        "宏观与市场": [
            "https://www.caixin.com/rss/",
            "https://www.21jingji.com/rss/"
        ],
        "行业与公司": [
            "https://rss.eastmoney.com/EM_StockNews.aspx",
            "https://www.tmtpost.com/rss"
        ]
    }
    news_items = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for cat, urls in rss_sources.items():
        for url in urls:
            try:
                response = requests.get(url, headers=headers, timeout=10)
                feed = feedparser.parse(response.content)
                for entry in feed.entries[:4]: # 每个源抓取4条，确保素材充足
                    news_items.append(f"【{cat}】{entry.title}")
            except Exception as e:
                print(f"🚨 抓取 {url} 失败: {e}")
                
    return "\n".join(news_items)

# ================= 3. Gemini 专业总结 =================
def get_gemini_report(raw_content):
    if not raw_content.strip():
        return "今日新闻源抓取失败，素材为空，请检查网络或网站反爬策略。"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
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
    
    try:
        res = requests.post(url, headers=headers, json=payload).json()
        report = res.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        
        if not report:
            print("🚨 抓包到了！Gemini 返回异常：", res)
            return "早报生成失败，Gemini 未返回有效正文，请查看 Action 日志。"
            
        return report
    except Exception as e:
        print(f"🚨 请求过程中发生严重错误: {e}")
        return "早报请求失败，可能遭遇了网络波动。"

# ================= 4. 构建 HTML 视觉模板 =================
def create_html(report_text):
    today = datetime.now().strftime("%Y-%m-%d")
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
    print("☀️ 开始抓取新闻...")
    news = get_news()
    
    print("🧠 呼叫 Gemini 进行总结...")
    report = get_gemini_report(news)
    
    print("🎨 正在排版...")
    html_content = create_html(report)
    
    print("📲 正在推送到微信...")
    push_data = {
        "token": PUSHPLUS_TOKEN,
        "title": f"📈 {datetime.now().strftime('%m月%d日')} 财经内参",
        "content": html_content,
        "template": "html"
    }
    res = requests.post("http://www.pushplus.plus/send", json=push_data)
    
    if res.status_code == 200:
        print("✅ 内参已成功送达微信！")
    else:
        print("❌ 微信推送失败:", res.text)
