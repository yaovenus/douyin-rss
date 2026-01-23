import feedparser
import requests
import os
import json
import re
from bs4 import BeautifulSoup
from html_telegraph_poster import TelegraphPoster

# ================= 配置 =================
RSS_URL = "http://129.150.45.187:120/telegram/channel/featuredofpincong"

BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
CHAT_ID = os.environ["TG_CHAT_ID"]
TELEGRAPH_TOKEN = os.environ["TELEGRAPH_TOKEN"]

DB_FILE = "last_processed_id.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# ================= Telegraph 发布 =================
def post_to_telegraph(url, title):
    try:
        t = TelegraphPoster(use_api=True, access_token=TELEGRAPH_TOKEN)

        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.encoding = "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")

        # 1️⃣ 找正文
        content = soup.find("div", class_="post_content") or soup.body
        if not content:
            return None

        # 2️⃣ 清理垃圾标签
        for tag in content(["script", "style", "iframe", "button", "input", "noscript"]):
            tag.decompose()

        # 3️⃣ 强制正文第一张图片置顶（关键）
        first_img = content.find("img")
        if first_img and first_img.get("src"):
            img_src = first_img["src"]
            img_tag = BeautifulSoup(f"<img src='{img_src}'>", "html.parser")
            content.insert(0, img_tag)

        # 4️⃣ 发布到 Telegraph
        result = t.post(
            title=title,
            author="品葱精选",
            author_url=url,
            text=str(content)
        )

        return result["url"]

    except Exception as e:
        print("Telegraph 发布失败：", e)
        return None

# ================= 获取网页标题 =================
def get_website_title(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=5)
        r.encoding = "utf-8"
        m = re.search(r"<title>(.*?)</title>", r.text, re.I)
        if m:
            return m.group(1).strip()
    except:
        pass
    return "未命名文章"

# ================= 发送 Telegram =================
def send_msg(text):
    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    requests.post(api, data=data)

# ================= 主程序 =================
def main():
    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        print("无文章")
        return

    entry = feed.entries[0]

    article_url = entry.title
    article_id = entry.get("id", article_url)

    last_id = ""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            last_id = f.read().strip()

    if article_id == last_id:
        print("无更新")
        return

    print("发现新文章：", article_url)

    # 1️⃣ 标题
    title = get_website_title(article_url)
    print("标题：", title)

    # 2️⃣ 生成 Telegraph 即时预览
    iv_link = post_to_telegraph(article_url, title)
    if not iv_link:
        print("Telegraph 失败，终止")
        return

    # 3️⃣ Telegram 消息：只放一个“隐形链接”
    # 👉 没文字、没按钮、没标题
    msg_text = f"<a href='{iv_link}'>&#8203;</a>"
    send_msg(msg_text)

    # 4️⃣ 记录已处理
    with open(DB_FILE, "w") as f:
        f.write(article_id)

    print("完成")

if __name__ == "__main__":
    main()
