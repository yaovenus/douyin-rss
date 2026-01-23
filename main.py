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

# --- 核心功能：生成纯净文章 ---
def post_to_telegraph(url):
    try:
        t = TelegraphPoster(use_api=True, access_token=TELEGRAPH_TOKEN)
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')

        # === 第一步：结构化清洗 (删标签) ===
        # 删除网页里绝对不需要的标签
        for tag in soup(['script', 'style', 'iframe', 'noscript', 'nav', 'footer', 'aside', 'button', 'input']):
            tag.decompose()

        # === 第二步：定位正文 ===
        # 尝试找到正文容器
        content = soup.find('div', class_='post_content')
        if not content:
            content = soup.find('div', class_='entry-content')
        if not content:
            content = soup.find('article')
        if not content:
            # 兜底：如果没找到，就用 body，但后续会进行强力清洗
            content = soup.body

        # === 第三步：基于“截图证据”的强力清洗 (关键优化) ===
        # 定义我们在截图里看到的“垃圾”特征词
        # 只要一段话里包含这些词，就说明它不是正文，直接删掉
        garbage_patterns = [
            "Home", "RSS", "Telegram", "Twitter", # 顶部导航
            "点击纠错", "点击删除", # 功能链接
            "CN2", "GIA", "科学上网", "Shadowsocks", "V2ray", "每月仅需", # 底部广告
            "tags :", "tags:", # 标签列表
            "加入品葱精选", # 底部推广
            "Previous post", "Next post" # 翻页导航
        ]

        # 遍历所有段落、列表、div，进行“内容审查”
        # 我们使用 list(content.find_all...) 是为了在遍历时安全地删除元素
        for tag in list(content.find_all(['p', 'div', 'ul', 'li', 'h3', 'h4', 'span', 'a'])):
            text = tag.get_text().strip()
            
            # 1. 删除过短的导航词 (比如 "Home", "RSS")
            if len(text) < 20 and any(w in text for w in ["Home", "RSS", "Telegram", "Twitter"]):
                tag.decompose()
                continue

            # 2. 删除包含特定广告词的段落
            if any(pattern in text for pattern in garbage_patterns):
                tag.decompose()
                continue
            
            # 3. 删除看起来像元数据的行 (例如: "by XXX at 2026...")
            if re.search(r'by .* at .* \d{4}', text, re.IGNORECASE):
                tag.decompose()
                continue

        # === 第四步：获取标题 ===
        real_title = ""
        # 优先找 H1
        h1 = content.find('h1') or soup.find('h1')
        if h1:
            real_title = h1.get_text().strip()
        
        # 没找到就找 Title
        if not real_title and soup.title:
            real_title = soup.title.string.strip()
            
        # 标题清洗
        if real_title:
            real_title = real_title.split(' - ')[0].split(' | ')[0]
        else:
            real_title = "精选文章"

        # === 第五步：发布 ===
        # 检查一下还剩多少内容，太短则报错
        if len(content.get_text()) < 20: 
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

# --- 发送消息 ---
def send_msg(text):
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
            msg_text = f"<a href='{iv_link}'>&#8203;</a><b><a href='{iv_link}'>{real_title}</a></b>"
        else:
            msg_text = article_url

        send_msg(msg_text)

        with open(DB_FILE, "w") as f:
            f.write(latest_id)
        print("完成")
    else:
        print("无更新")

if __name__ == "__main__":
    main()
