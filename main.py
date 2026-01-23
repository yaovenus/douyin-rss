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
# 新增：从 Secrets 获取 Telegraph Token
TELEGRAPH_TOKEN = os.environ["TELEGRAPH_TOKEN"] 
DB_FILE = "last_processed_id.txt"

# --- 功能函数：发布到 Telegraph ---
def post_to_telegraph(url, title):
    try:
        # 初始化发布器
        t = TelegraphPoster(use_api=True, access_token=TELEGRAPH_TOKEN)
        
        # 1. 抓取原网页内容
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        # 2. 清洗 HTML (只保留 body)
        # 这一步很重要，Telegraph 不喜欢复杂的 script 和 header
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 尝试找到正文区域 (针对 Project Gutenberg / Pincong 的结构)
        # 如果找不到特定 class，就用 body
        content = soup.find('div', class_='post_content') 
        if not content:
            content = soup.body

        # 移除可能导致报错的标签
        for tag in content(['script', 'style', 'iframe', 'button', 'input']):
            tag.decompose()

        # 3. 发布
        # html_telegraph_poster 会自动把 HTML 转换成 Telegraph 格式
        result = t.post(
            title=title,
            author='品葱精选',
            author_url=url,
            text=str(content)
        )
        return result['url'] # 返回生成的 Telegraph 链接

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
        "disable_web_page_preview": False # 开启预览！因为我们要展示 Telegraph 的大图
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
    # 在这个 RSS 源里，标题就是文章链接
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

        # 2. 生成 Telegraph 即时预览页面
        print("正在生成 Telegraph 页面...")
        iv_link = post_to_telegraph(article_url, real_title)
        
        if iv_link:
            # 成功生成！
            # 构造消息：
            # 这里的 <a href='{iv_link}'>&#8203;</a> 是隐形链接，用于强制显示预览图
            # 标题点击跳转到 Telegraph 页面
            msg_text = (
                f"<a href='{iv_link}'>&#8203;</a>"
                f"⚡️ <b><a href='{iv_link}'>{real_title}</a></b>\n\n"
                f"👇 原文链接 (点击复制)：\n"
                f"<code>{article_url}</code>"
            )
            # 按钮：也指向 Telegraph
            keyboard = {
                "inline_keyboard": [[
                    {"text": "📖 阅读即时预览", "url": iv_link},
                    {"text": "🔗 原网页", "url": article_url}
                ]]
            }
        else:
            # 失败兜底：回退到 V1.0 逻辑
            msg_text = (
                f"📢 <b><a href='{article_url}'>{real_title}</a></b>\n\n"
                f"👇 点下方灰框复制链接：\n"
                f"<code>{article_url}</code>"
            )
            keyboard = None

        # 3. 发送
        send_msg(msg_text, reply_markup=keyboard)

        # 4. 更新记录
        with open(DB_FILE, "w") as f:
            f.write(latest_id)
        print("完成")
    else:
        print("无更新")

if __name__ == "__main__":
    main()
