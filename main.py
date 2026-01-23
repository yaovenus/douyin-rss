import feedparser
import requests
import os
import sys
import json
from urllib.parse import quote 

# --- 配置区域 ---
RSS_URL = "http://129.150.45.187:120/telegram/channel/featuredofpincong"
BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
CHAT_ID = os.environ["TG_CHAT_ID"]
DB_FILE = "last_processed_id.txt"

def send_msg(text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID, 
        "text": text, 
        "parse_mode": "HTML",
        "disable_web_page_preview": True 
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
        
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"发送失败: {e}")

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

    latest_entry = feed.entries[0]
    latest_id = latest_entry.get("id", latest_entry.get("link", ""))
    latest_title = latest_entry.title
    latest_link = latest_entry.link

    last_id = ""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            last_id = f.read().strip()

    if latest_id != last_id:
        print(f"发现更新: {latest_title}")
        
        # --- 改进 1：增加“点击复制”体验 ---
        # 链接放在 <code> 标签里，手机上一部分用户点击该区域可直接复制
        msg_text = (
            f"📢 <b>{latest_title}</b>\n\n"
            f"👇 点击下方按钮转发转换，或点击链接复制：\n"
            f"<code>{latest_link}</code>"
        )

        encoded_link = quote(latest_link)
        
        keyboard = {
            "inline_keyboard": [
                [
                    # --- 改进 2：使用 Share URL 机制 ---
                    # 点击后会弹出“选择聊天对象”，选中 CorsaBot 后链接自动填入
                    {
                        "text": "🚀 转发给 CorsaBot 转换", 
                        "url": f"https://t.me/share/url?url={encoded_link}"
                    }
                ],
                [
                    {
                        "text": "🔗 查看原网页",
                        "url": latest_link
                    }
                ]
            ]
        }

        send_msg(msg_text, reply_markup=keyboard)

        with open(DB_FILE, "w") as f:
            f.write(latest_id)
        print("发送成功，记录已更新")
    else:
        print("暂无新文章")

if __name__ == "__main__":
    main()
