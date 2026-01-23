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

        # 1. 【定位正文】
        content = soup.find('div', class_='post_content')
        if not content:
            content = soup.find('div', class_='entry-content')
        if not content:
            content = soup.find('article')
        if not content:
            content = soup.body

        # 2. 【智能标题提取】
        # 很多时候 H1 是栏目名，H2 才是文章名
        # 我们尝试把它们组合起来，或者优先取长的那个
        h1 = soup.find('h1')
        h2 = soup.find('h2')
        
        title_h1 = h1.get_text().strip() if h1 else ""
        title_h2 = h2.get_text().strip() if h2 else ""
        
        # 逻辑：如果 H2 存在且长度大于 H1，通常 H2 才是真标题
        if title_h2 and len(title_h2) > len(title_h1):
            real_title = title_h2
        elif title_h1 and title_h2:
            # 如果两个都有，拼起来：栏目 | 标题
            real_title = f"{title_h1} | {title_h2}"
        else:
            # 兜底：优先用 H1，没有就用网页 Title
            real_title = title_h1 if title_h1 else (soup.title.string.strip() if soup.title else "未命名文章")

        # 再次清理标题中的管道符后缀
        real_title = real_title.split(' - ')[0]

        # 3. 【精准清洗】
        # 删除脚本、样式、按钮
        for tag in content(['script', 'style', 'iframe', 'noscript', 'button', 'input', 'form']):
            tag.decompose()
            
        # 删除特定的垃圾 Class (广告、推荐、侧边栏)
        # 只要 class 名字里包含这些词，就删掉该区块
        garbage_words = ['share', 'comment', 'ads', 'related', 'recommend', 'footer', 'sidebar', 'meta', 'info']
        for tag in content.find_all(['div', 'ul', 'section', 'aside']):
            classes = tag.get('class', [])
            # 把 list 转成字符串匹配
            class_str = " ".join(classes).lower()
            if any(bad in class_str for bad in garbage_words):
                tag.decompose()

        # 4. 【发布】
        # 注意：这里不再手动插入 img 标签
        # 让 Telegraph 自动渲染 content 里原本存在的图片
        # 这样能确保图片和文字的顺序是正确的，绝不会张冠李戴
        
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
            # 极简模式：只发一个带标题的链接
            # 隐形链接 &#8203; 用于触发预览
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
