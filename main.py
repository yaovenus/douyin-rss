import feedparser
import requests
import os
import sys
import json
# 引入 url编码工具，处理链接中的特殊字符
from urllib.parse import quote 

# --- 配置区域 ---
RSS_URL = "http://129.150.45.187:120/telegram/channel/featuredofpincong"
BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
CHAT_ID = os.environ["TG_CHAT_ID"]
DB_FILE = "last_processed_id.txt"

# --- 发送消息的函数 ---
def send_msg(text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID, 
        "text": text, 
        "parse_mode": "HTML",
        # 禁用网页预览，保持界面清爽，因为我们要引导用户去点按钮
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
    latest_title = latest_entry.title
    latest_link = latest_entry.link

    # 读取本地记录
    last_id = ""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            last_id = f.read().strip()

    # --- 发现新文章 ---
    if latest_id != last_id:
        print(f"发现更新: {latest_title}")
        
        # 1. 构造消息文本 (只有标题，干净利落)
        # 点击标题也可以直接跳转原网页
        msg_text = f"📢 <b><a href='{latest_link}'>{latest_title}</a></b>"

        # 2. 构造按钮 (Inline Keyboard)
        # 这里的 deep_link 原理是：https://t.me/CorsaBot?start=链接
        # 对链接进行 URL 编码，防止网址里的符号导致跳转失败
        encoded_link = quote(latest_link)
        
        keyboard = {
            "inline_keyboard": [
                [
                    # 这是核心：点击后直接跳转 CorsaBot 并准备好链接
                    {
                        "text": "⚡️ 使用 CorsaBot 转换", 
                        "url": f"https://t.me/CorsaBot?start={encoded_link}"
                    }
                ],
                [
                     # 备用按钮：直接访问原网页
                    {
                        "text": "🔗 查看原网页",
                        "url": latest_link
                    }
                ]
            ]
        }

        # 3. 发送
        send_msg(msg_text, reply_markup=keyboard)

        # 4. 更新记录
        with open(DB_FILE, "w") as f:
            f.write(latest_id)
        print("发送成功，记录已更新")
    else:
        print("暂无新文章")

if __name__ == "__main__":
    main()
