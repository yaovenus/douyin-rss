import feedparser
import requests
import os
import sys

# 从环境变量获取配置
RSS_URL = "http://129.150.45.187:120/telegram/channel/featuredofpincong"
BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
CHAT_ID = os.environ["TG_CHAT_ID"]
DB_FILE = "last_processed_id.txt"

def send_msg(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"发送失败: {e}")

def main():
    # 1. 解析 RSS
    print(f"正在检查: {RSS_URL}")
    try:
        feed = feedparser.parse(RSS_URL)
    except Exception as e:
        print(f"RSS 解析出错: {e}")
        return

    if not feed.entries:
        print("未发现文章")
        return

    # 获取最新一篇文章的唯一标识 (ID 或 Link)
    latest_entry = feed.entries[0]
    latest_id = latest_entry.get("id", latest_entry.get("link", ""))
    latest_title = latest_entry.title
    latest_link = latest_entry.link

    print(f"最新文章: {latest_title}")

    # 2. 读取上次处理的 ID
    last_id = ""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            last_id = f.read().strip()

    # 3. 对比：如果是新文章
        if latest_id != last_id:
        # 使用 rhash (Telegram 的即时预览模板 ID)
        # 下面这个 rhash 是通用的或者你需要去找一个针对该网站好用的 rhash
        # 这里用一个示例，如果 CorsaBot 有公开的 rhash 更好
        rhash = "你的_RHASH_值" 
        iv_url = f"https://t.me/iv?url={latest_link}&rhash={rhash}"

        # 直接把 IV 链接发出去，Telegram 会自动显示预览
        msg = f"<a href='{iv_url}'>&#8203;</a><b>{latest_title}</b>\n\n原链：{latest_link}"
          
        # 发送 Telegram (支持 HTML 格式)
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID, 
            "text": msg, 
            "parse_mode": "HTML"
        }
        requests.post(url, data=data)

        # 4. 更新本地记录文件
        with open(DB_FILE, "w") as f:
            f.write(latest_id)
        print("记录已更新")
    else:
        print("暂无新文章")

if __name__ == "__main__":
    main()