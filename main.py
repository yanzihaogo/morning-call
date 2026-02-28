import os
import requests
import json
import re
import time

# ==========================================
# 1. 读取我们的“通行证”
# ==========================================
coze_token = os.getenv('COZE_API_TOKEN')
coze_bot_id = os.getenv('COZE_BOT_ID')
pushplus_token = os.getenv('PUSHPLUS_TOKEN')

SEARCH_PROMPT = "请立即执行每日宏观市场与商品行情数据抓取，严格按预设 JSON 格式返回。"

def fetch_news_from_coze():
    print("🕵️‍♂️ 正在潜入全网搜集客观行情情报...")
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
        print("✅ 任务已下达，等待特工汇总数据...")
        
        # 轮询查岗：问 AI 抓完没有
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
            
        # 任务确认完成后，去收发室取信件（提取最终结果）
        msg_url = f'https://api.coze.cn/v3/chat/message/list?chat_id={chat_id}&conversation_id={conversation_id}'
        msgs_res = requests.get(msg_url, headers=headers).json()
        
        content = ""
        for msg in msgs_res.get('data', []):
            if msg.get('type') == 'answer':
                content = msg.get('content')
                break
        
        print("📥 收到情报，正在解码...")
        
        # 提取真正的 JSON 数据
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            print("❌ 解码失败，返回原文：\n", content)
            return None
            
    except Exception as e:
        print(f"❌ 抓取异常: {e}")
        return None
def push_to_wechat(data):
    if not data or not isinstance(data, dict):
        print("⚠️ 获取的数据格式不对，取消推送。")
        return

    print("✅ 数据解析成功，正在排版...")
    
    # 标题
    msg_content = "## 🎙️ 全球宏观与市场行情详报\n\n---\n"
    
    # 1. 宏观要闻 (放到最前，并扩充数量)
    msg_content += "### 📌 【今日核心要闻】\n"
    top_news = data.get('top_news', [])
    for idx, item in enumerate(top_news, 1):
        msg_content += f"**{idx}. {item.get('title', '无标题')}**\n"
        msg_content += f"> {item.get('summary', '无摘要')}\n"
        msg_content += f"[🔗 来源链接]({item.get('url', '#')})\n\n"
        
    msg_content += "---\n"
    
    # 2. 市场情绪与焦点
    msg_content += "### 👁️ 【市场情绪与焦点观察】\n"
    msg_content += f"{data.get('market_focus', '暂无观察数据')}\n\n---\n"

    # 3. 股市速览
    msg_content += "### 🌐 【主要市场行情综述】\n"
    indices = data.get('market_indices', {})
    msg_content += f"- **🇨🇳 沪深 A 股**\n  {indices.get('A_shares', '暂无数据')}\n\n"
    msg_content += f"- **🇭🇰 港股市场**\n  {indices.get('HK_shares', '暂无数据')}\n\n"
    msg_content += f"- **🇺🇸 美股市场**\n  {indices.get('US_shares', '暂无数据')}\n\n---\n"

    # 4. 商品速览
    msg_content += "### 🛢️ 【大宗商品期货综述】\n"
    commodities = data.get('commodities', {})
    msg_content += f"- **🥇 黄金**\n  {commodities.get('gold', '暂无数据')}\n\n"
    msg_content += f"- **🥈 白银**\n  {commodities.get('silver', '暂无数据')}\n\n"
    msg_content += f"- **🛢️ 原油**\n  {commodities.get('crude_oil', '暂无数据')}\n\n---\n"
    
    # 5. 一句话简报 (新增板块)
    msg_content += "### 📰 【市场脉搏简报】\n"
    briefings = data.get('briefings', [])
    if briefings:
        for b in briefings:
            msg_content += f"- **[{b.get('category', '简报')}]** {b.get('content', '无内容')}\n\n"
    else:
        msg_content += "- 暂无异动或重大投资简报\n\n"

    url = '[http://www.pushplus.plus/send](http://www.pushplus.plus/send)'
    push_data = {
        "token": pushplus_token,
        "title": "🎙️ 今日全球宏观与市场详报已送达",
        "content": msg_content,
        "template": "markdown"
    }
    
    res = requests.post(url, json=push_data)
    if res.json().get('code') == 200:
        print("🚀 推送成功！请查收微信！")
    else:
        print(f"❌ 推送失败：{res.json()}")

 


if __name__ == '__main__':
    report_data = fetch_news_from_coze()
    if report_data:
        push_to_wechat(report_data)
    else:
        print("流程异常结束。")


