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

        # === 第一步：全局大扫除 (关键步骤) ===
        # 在找正文之前，先把页脚、推荐、侧边栏统统删掉
        # 这样可以防止脚本误把“下一篇文章”当成“正文”
        for tag in soup(['footer', 'nav', 'aside', 'script', 'style', 'noscript', 'iframe']):
            tag.decompose()
            
        # 根据关键词删除干扰区块 (推荐阅读、评论、广告)
        garbage_classes = ['related', 'recommend', 'comment', 'share', 'sidebar', 'footer', 'bottom', 'ads', 'meta']
        for tag in soup.find_all('div'):
            # 检查 class 是否包含垃圾关键词
            classes = tag.get('class', [])
            if classes:
                class_str = " ".join(classes).lower()
                if any(bad in class_str for bad in garbage_classes):
                    tag.decompose()

        # === 第二步：寻找幸存的正文 ===
        # 按照优先级尝试不同的容器
        content = None
        
        # 1. 尝试标准 HTML5 标签
        content = soup.find('main')
        if not content:
            content = soup.find('article')
            
        # 2. 尝试常见的 ID
        if not content:
            content = soup.find(id=re.compile(r'(post|entry|content|article)', re.I))
            
        # 3. 尝试常见的 Class (范围放宽)
        if not content:
            content = soup.find('div', class_=re.compile(r'(post|entry|content|article)', re.I))
            
        # 4. 最后的兜底：如果还没找到，且 body 还在，就用 body
        if not content:
            content = soup.body

        # === 第三步：获取标题 ===
        # 优先抓 H1 (通常是文章标题)
        real_title = ""
        h1 = soup.find('h1')
        if h1:
            real_title = h1.get_text().strip()
        
        # 如果没抓到 H1，用网页 Title
        if not real_title and soup.title:
            real_title = soup.title.string.strip()
            
        # 清理标题后缀
        if real_title:
            real_title = real_title.split(' - ')[0].split(' | ')[0]
        else:
            real_title = "精选文章"

        # === 第四步：安全检查 ===
        # 如果抓到的内容太短（少于50字），说明可能抓错了或者没抓到
        # 这时候宁愿不生成 IV，也不要发错误的内容
        if content and len(content.get_text()) < 50:
            print("警告：抓取到的正文过短，可能抓取失败")
            return None, None

        # === 第五步：发布 ===
        # 此时 content 里的图片和文字都是正文原本的，因为垃圾已经在第一步被删掉了
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
            # 成功：发送带有 Instant View 的标题链接
            msg_text = f"<a href='{iv_link}'>&#8203;</a><b><a href='{iv_link}'>{real_title}</a></b>"
        else:
            # 失败兜底：如果不幸抓取失败（比如内容太短），直接发原链接
            # 这样至少用户还能看，不会看到乱七八糟的“垃圾回收”文章
            msg_text = article_url

        send_msg(msg_text)

        with open(DB_FILE, "w") as f:
            f.write(latest_id)
        print("完成")
    else:
        print("无更新")

if __name__ == "__main__":
    main()
