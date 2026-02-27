import os
import requests
import feedparser
from datetime import datetime

# ================= 1. 配置信息 =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

# ================= 2. 抓取新闻 (换回你原本稳定好用的源) =================
def get_news():
    # 增加更多权威且对程序友好的数据源，保证信息交叉印证
    rss_sources = {
        "宏观与国内": [
            "https://www.caixin.com/rss/",
            "https://www.21jingji.com/rss/"
        ],
        "全球市场与大宗商品": [
            "https://rss.eastmoney.com/EM_StockNews.aspx",
            "https://rss.sina.com.cn/roll/finance/hot_roll.xml" # 新浪财经滚动要闻
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
    你是一名资深的金融电台播音员。请根据以下抓取到的新闻素材，撰写一份《每日金融内参》的口播讲稿。
    
    【核心要求】
    1. 篇幅与语调：字数控制在 1000-1200 字左右（约5分钟的正常语速）。语调要极其沉稳、客观、专业，适合中老年高端投资者收听。
    2. 内容容错：如果素材中缺少某项具体数据（例如具体的收盘点位），请根据整体宏观素材进行定性的趋势分析，绝对不可胡编乱造具体数值。
    
    【结构必须严格按照以下顺序排列】
    一、[开篇要闻]：在最开头，直接提炼今日最核心的 3 条重磅宏观或政策消息，作为低成本获取高价值信息的渠道。
    二、[盘面解析]：分别简述过去一天 沪深A股、港股 和 美股 的整体表现及背后的核心驱动因素。
    三、[大宗商品观察]：简要分析 金价、银价 和 原油期货 的最新动向及避险/需求逻辑。
    四、[市场情绪与趋势]：归纳当前资金的整体情绪状态（如观望、贪婪、避险），并指出后续潜在的趋势方向。
    
    今日可用素材如下：
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

