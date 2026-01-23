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

# --- 核心功能：生成纯净文章 (V2.3 强力清洗版) ---
def post_to_telegraph(url):
    try:
        t = TelegraphPoster(use_api=True, access_token=TELEGRAPH_TOKEN)
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')

        # === 1. 全局大扫除 (防止抓错图片/内容) ===
        # 在找正文之前，先把页脚、推荐、侧边栏统统删掉
        for tag in soup(['footer', 'nav', 'aside', 'script', 'style', 'noscript', 'iframe']):
            tag.decompose()
            
        # 根据关键词删除干扰区块 (推荐阅读、评论、广告)
        garbage_classes = ['related', 'recommend', 'comment', 'share', 'sidebar', 'footer', 'bottom', 'ads', 'meta']
        for tag in soup.find_all('div'):
            classes = tag.get('class', [])
            if classes:
                class_str = " ".join(classes).lower()
                if any(bad in class_str for bad in garbage_classes):
                    tag.decompose()

        # === 2. 寻找正文 ===
        content = None
        # 尝试标准标签和常见ID/Class
        content = soup.find('main')
        if not content:
            content = soup.find('article')
        if not content:
            content = soup.find(id=re.compile(r'(post|entry|content|article)', re.I))
        if not content:
            content = soup.find('div', class_=re.compile(r'(post|entry|content|article)', re.I))
        if not content:
            content = soup.body

        # === 3. 获取标题 (智能提取) ===
        real_title = ""
        h1 = soup.find('h1')
        if h1:
            real_title = h1.get_text().strip()
        
        # 兜底：用网页 Title
        if not real_title and soup.title:
            real_title = soup.title.string.strip()
            
        # 清理标题后缀
        if real_title:
            real_title = real_title.split(' - ')[0].split(' | ')[0]
        else:
            real_title = "精选文章"

        # === 4. 发布 ===
        # 内容过短保护
        if content and len(content.get_text()) < 50:
            print("警告：抓取内容过短，放弃生成预览")
            return None, None

        result = t.post(
            title=real_title,
            author='品葱精选',
            author_url=url,
            text=str(content)
        )
        
        return result['url'], real_title

    except Exception as e:
        print(f"Telegraph 发布失败: {e}")
        return None, None

# --- 发送消息 (极简版) ---
def send_msg(text):
    # 注意：这里去掉了 reply_markup 参数，彻底删除了按钮
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID, 
        "text": text, 
        "parse_mode": "HTML",
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
    article_url = entry.title
    latest_id = entry.get("id", entry.get("link", ""))

    last_id = ""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            last_id = f.read().strip()

    if latest_id != last_id:
        print(f"处理新文章: {article_url}")
        
        iv_link, real_title = post_to_telegraph(article_url)
        
        if iv_link and real_title:
            # === 极简消息构造 ===
            # 我们删除了 ①(闪电标题行) ②(复制框) ③(按钮)
            # 只保留这一行：
            # 第一个 <a> 是隐形链接，用于强制显示预览大图
            # 第二个 <a> 是可见标题，用户点击它进入即时预览
            msg_text = f"<a href='{iv_link}'>&#8203;</a><a href='{iv_link}'>{real_title}</a>"
        else:
            # 失败兜底
            msg_text = article_url

        # 发送 (不带按钮)
        send_msg(msg_text)

        with open(DB_FILE, "w") as f:
            f.write(latest_id)
        print("完成")
    else:
        print("无更新")

if __name__ == "__main__":
    main()
