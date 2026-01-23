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

# --- 核心功能：强力清洗并发布 ---
def post_to_telegraph(url, title):
    try:
        t = TelegraphPoster(use_api=True, access_token=TELEGRAPH_TOKEN)
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. 定位正文
        # 针对该网站结构，通常内容在 class="post_content" 或 "article" 中
        content = soup.find('div', class_='post_content')
        if not content:
            content = soup.find('article')
        if not content:
            content = soup.body

        # 2. 【深度净化】移除干扰元素
        # 定义要删除的关键词 (类名或ID包含这些词的元素会被删掉)
        garbage_keywords = [
            'related', 'recommend', 'footer', 'sidebar', 'nav', 'menu', 
            'comment', 'share', 'ads', 'promo', 'pager', 'pagination', 
            'next', 'prev', 'copyright'
        ]

        # 删除所有 <script>, <style>, <iframe... 等标签
        for tag in content(['script', 'style', 'iframe', 'button', 'input', 'form', 'noscript']):
            tag.decompose()

        # 针对 div, ul, section 等容器进行关键词扫描
        for tag in content.find_all(['div', 'ul', 'section', 'aside', 'footer', 'nav']):
            # 获取 class 和 id 属性
            classes = tag.get('class', [])
            ids = tag.get('id', [])
            # 组合成字符串方便检查
            check_str = " ".join(classes) + " " + str(ids)
            
            # 如果包含垃圾关键词，直接删除该区块
            if any(keyword in check_str.lower() for keyword in garbage_keywords):
                tag.decompose()
        
        # 额外清理：删除很多博客底部都会有的“空链接”或“标签列表”
        for tag in content.find_all('div', class_='tags'):
            tag.decompose()

        # 3. 发布到 Telegraph
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

# --- 获取标题 ---
def get_website_title(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.encoding = 'utf-8'
        match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE)
        if match:
            # 清理标题中的多余后缀 (比如 " - 品葱")
            clean_title = match.group(1).split('|')[0].split('-')[0].strip()
            return clean_title
    except:
        pass
    return "未命名文章"

# --- 发送消息 (极简版) ---
def send_msg(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID, 
        "text": text, 
        "parse_mode": "HTML",
        # 关键：开启预览，这样才会显示 Instant View 卡片
        "disable_web_page_preview": False 
    }
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
    article_url = entry.title # 原始 RSS 特性
    latest_id = entry.get("id", entry.get("link", ""))

    last_id = ""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            last_id = f.read().strip()

    if latest_id != last_id:
        print(f"处理新文章: {article_url}")
        
        # 1. 获取并净化标题
        real_title = get_website_title(article_url)
        
        # 2. 生成纯净版 IV 页面
        iv_link = post_to_telegraph(article_url, real_title)
        
        if iv_link:
            # 【极简外观】
            # 只发送一个超链接标题。
            # Telegram 会检测到这个链接是 telegra.ph，自动展示 IV 按钮。
            # 这里的 href 是 Telegraph 的链接，显示的文字是文章标题。
            msg_text = f"<a href='{iv_link}'>{real_title}</a>"
        else:
            # 失败兜底：发送原链接
            msg_text = article_url

        # 3. 发送
        send_msg(msg_text)

        # 4. 更新记录
        with open(DB_FILE, "w") as f:
            f.write(latest_id)
        print("完成")
    else:
        print("无更新")

if __name__ == "__main__":
    main()
