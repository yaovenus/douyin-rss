import feedparser
import requests
import os
import sys
import json
import re  # 引入正则库，用于提取网页标题

# --- 配置区域 ---
RSS_URL = "http://129.150.45.187:120/telegram/channel/featuredofpincong"
BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
CHAT_ID = os.environ["TG_CHAT_ID"]
DB_FILE = "last_processed_id.txt"

# --- 获取网页真实标题的函数 ---
def get_website_title(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        # 设置3秒超时，避免卡住
        response = requests.get(url, headers=headers, timeout=3)
        response.encoding = 'utf-8' # 强制utf-8，防止中文乱码
        
        # 使用正则表达式提取 <title> 标签中的内容
        match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # 如果标题太长，可以截取（可选）
            return title
    except Exception as e:
        print(f"获取标题失败: {e}")
    
    # 如果抓取失败，就回退显示 URL
    return url

# --- 发送消息的函数 ---
def send_msg(text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID, 
        "text": text, 
        "parse_mode": "HTML",
        # 【修改点2】设置为 True，彻底禁止显示下方的网页预览卡片
        "disable_web_page_preview": True 
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
        
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"发送失败: {e}")

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

    # 获取最新一篇文章
    latest_entry = feed.entries[0]
    latest_id = latest_entry.get("id", latest_entry.get("link", ""))
    
    # 原始 RSS 数据
    # 在这个源里，title 实际上是文章链接，link 是 Telegram 消息链接
    article_url = latest_entry.title
    telegram_post_link = latest_entry.link

    # 读取本地记录
    last_id = ""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            last_id = f.read().strip()

    # --- 发现新文章 ---
    if latest_id != last_id:
        print(f"发现更新，正在获取标题: {article_url}")
        
        # 【修改点1】调用函数获取真实的中文标题
        real_title = get_website_title(article_url)
        print(f"获取到的标题: {real_title}")

        # 构造消息文本
        # 蓝色标题：显示真实标题 (real_title)，链接指向文章地址 (article_url)
        # 灰色框：依旧保留文章链接，方便复制
        msg_text = (
            f"📢 <b><a href='{article_url}'>{real_title}</a></b>\n\n"
            f"👇 点下方灰框复制链接：\n"
            f"<code>{article_url}</code>"
        )

        # 构造按钮 (可选：查看原消息)
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "🔗 查看 Telegram 原文",
                        "url": telegram_post_link
                    }
                ]
            ]
        }

        # 发送
        send_msg(msg_text, reply_markup=keyboard)

        # 更新记录
        with open(DB_FILE, "w") as f:
            f.write(latest_id)
        print("发送成功，记录已更新")
    else:
        print("暂无新文章")

if __name__ == "__main__":
    main()
