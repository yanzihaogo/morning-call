import os
import requests

def test_secrets():
    print("🚀 开始执行 Secrets 体检...\n")

    # 1. 尝试从 GitHub 环境中读取变量
    coze_token = os.getenv('COZE_API_TOKEN')
    coze_bot_id = os.getenv('COZE_BOT_ID')
    pushplus_token = os.getenv('PUSHPLUS_TOKEN')

    # ==========================================
    # 第一关：检查变量是否成功读取
    # ==========================================
    print("--- 第一关：检查 GitHub Secrets 是否成功加载 ---")
    if coze_token:
        # 故意只打印长度，防止 Token 泄露在日志里
        print(f"✅ COZE_API_TOKEN: 已读取 (长度: {len(coze_token)})")
    else:
        print("❌ COZE_API_TOKEN: 未读取到！请检查 Secrets 名字是否拼写正确。")

    if coze_bot_id:
        print(f"✅ COZE_BOT_ID: 已读取 ({coze_bot_id})")
    else:
        print("❌ COZE_BOT_ID: 未读取到！")

    if pushplus_token:
        print("✅ PUSHPLUS_TOKEN: 已读取")
    else:
        print("⚠️ PUSHPLUS_TOKEN: 未读取到 (如果你暂时没配微信推送，可忽略此项)")
    print("\n")

    # ==========================================
    # 第二关：验证 Coze API 连通性
    # ==========================================
    print("--- 第二关：验证 扣子 (Coze) API 权限与 Bot ID ---")
    if coze_token and coze_bot_id:
        try:
            url = 'https://api.coze.cn/v3/chat'
            headers = {
                'Authorization': f'Bearer {coze_token}',
                'Content-Type': 'application/json'
            }
            # 发送一个极其简单的问候，只为了测试能不能接通
            payload = {
                "bot_id": coze_bot_id,
                "user_id": "test_runner",
                "stream": False,
                "additional_messages": [{"role": "user", "content": "hi", "content_type": "text"}]
            }
            
            print("正在向 Coze 发起握手请求...")
            response = requests.post(url, headers=headers, json=payload)
            res_json = response.json()
            
            # HTTP 状态码 200 且业务 code 为 0 代表完美成功
            if response.status_code == 200 and res_json.get("code") == 0:
                print("✅ Coze 接口测试通关！成功跨过反爬保安，与 Bot 建立连接。")
            else:
                print(f"❌ Coze 接口报错啦！\nHTTP状态码: {response.status_code}\n详细返回: {res_json}")
        except Exception as e:
            print(f"❌ 请求发生严重异常: {e}")
    else:
        print("⏭️ 因缺少 Coze Token 或 Bot ID，跳过接口验证。")
    print("\n")

    # ==========================================
    # 第三关：验证 PushPlus 微信推送 (可选)
    # ==========================================
    print("--- 第三关：验证 PushPlus 推送 ---")
    if pushplus_token:
        try:
            url = 'http://www.pushplus.plus/send'
            data = {
                "token": pushplus_token,
                "title": "✅ 自动化链路打通测试",
                "content": "恭喜！如果你在微信里看到了这条消息，说明你的 GitHub Secrets 配置完全正确，自动化工作流已经跑通了！",
                "template": "html"
            }
            response = requests.post(url, json=data)
            res_json = response.json()
            if res_json.get("code") == 200:
                print("✅ PushPlus 推送成功！请看一眼微信是否收到了消息。")
            else:
                print(f"❌ PushPlus 推送失败: {res_json}")
        except Exception as e:
            print(f"❌ PushPlus 请求异常: {e}")
    else:
        print("⏭️ 未配置 PushPlus Token，跳过测试。")

    print("\n🎉 体检结束！")

if __name__ == '__main__':
    test_secrets()
