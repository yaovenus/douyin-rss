import feedparser
import requests
import os
import sys
import json
import re
from bs4 import BeautifulSoup
from html_telegraph_poster import TelegraphPoster

# --- 配置区域 ---
RSS_URL = "http://129.150.45.187:120/telegram/channel/featuredofpincong"
BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
CHAT_ID = os.environ["TG_CHAT_ID"]
TELEGRAPH_TOKEN = os.environ["TELEGRAPH_TOKEN"] 
DB_FILE = "last_processed_id.txt"

# --- 功能函数：发布到 Telegraph ---
def post_to_telegraph(url, title):
    try:
        t = TelegraphPoster(use_api=True, access_token=TELEGRAPH_TOKEN)
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 定位正文
        content = soup.find('div', class_='post_content') 
        if not content:
            content = soup.body

        # 移除干扰标签
        for tag in content(['script', 'style', 'iframe', 'button', 'input']):
            tag.decompose()

        # 发布
        result = t.post(
            title=title,
            author='品葱精选',
            author_url=url,
            text=str(content)
        )
        return result['url']

    except Exception as e:
        print(f"Telegraph 发布失败: {e}")
        return None

# --- 功能函数：获取真实标题 ---
def get_website_title(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.encoding = 'utf-8'
        match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    except:
        pass
    return "未命名文章"

# --- 发送 Telegram 消息 ---
def send_msg(text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID, 
        "text": text, 
        "parse_mode": "HTML",
        "disable_web_page_preview": False 
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, data=data)

# --- 主程序 ---
def main():
    print(f"正在检查: {RSS_URL}")
    try:
        feed = feedparser.parse(RSS_URL)
    except Exception as e:
        print(f"RSS 解析出错: {e}")
        return

    if not feed.entries:
        print("未发现文章")
        return

    entry = feed.entries[0]
    article_url = entry.title
    latest_id = entry.get("id", entry.get("link", ""))

    # 读取记录
    last_id = ""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            last_id = f.read().strip()

    if latest_id != last_id:
        print(f"发现新文章，正在处理: {article_url}")
        
        # 1. 获取真实标题
        real_title = get_website_title(article_url)
        print(f"标题: {real_title}")

        # 2. 生成 Telegraph 页面
        print("正在生成 Telegraph 页面...")
        iv_link = post_to_telegraph(article_url, real_title)
        
        if iv_link:
            # 成功生成！
            # 构造消息文本 (保留①标题，②复制框，④预览图)
            msg_text = (
                f"<a href='{iv_link}'>&#8203;</a>"
                f"⚡️ <b><a href='{iv_link}'>{real_title}</a></b>\n\n"
                f"👇 原文链接 (点击复制)：\n"
                f"<code>{article_url}</code>"
            )
        else:
            # 失败兜底
            msg_text = (
                f"📢 <b><a href='{article_url}'>{real_title}</a></b>\n\n"
                f"👇 点下方灰框复制链接：\n"
                f"<code>{article_url}</code>"
            )

        # 3. 发送 (不再传递 keyboard 参数，即删除了③)
        send_msg(msg_text)

        # 4. 更新记录
        with open(DB_FILE, "w") as f:
            f.write(latest_id)
        print("完成")
    else:
        print("无更新")

if __name__ == "__main__":
    main()
