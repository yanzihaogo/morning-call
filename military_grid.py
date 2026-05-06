name: 军工电网学术定向研报(Gemini版)

on:
  schedule:
    - cron: '00 23 * * *' # 北京时间早上 7:00 自动运行
  workflow_dispatch: # 支持手动点击运行

permissions:
  contents: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: 检出代码
        uses: actions/checkout@v4

      - name: 配置Python环境
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: 安装核心依赖
        run: |
          python -m pip install --upgrade pip
          # 必须安装 google-generativeai 才能调用 Gemini API
          pip install google-generativeai requests

      - name: 运行Gemini采编引擎
        env:
          # 请在 GitHub Secrets 中配置这两个变量
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
          SMTP_SERVER: ${{ secrets.SMTP_SERVER }}
          SENDER_EMAIL: ${{ secrets.SENDER_EMAIL }}
          SENDER_PASSWORD: ${{ secrets.SENDER_PASSWORD }}
        run: python military_grid.py
