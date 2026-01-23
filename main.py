import feedparser
import requests
import os
import sys
import json

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
        "disable_web_page_preview": False 
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
        
        # 1. 构造消息文本
        # 技巧：使用 <code> 标签包裹链接，在 Telegram 手机端点击即可自动复制
        msg_text = (
            f"📢 <b><a href='{latest_link}'>{latest_title}</a></b>\n\n"
            f"👇 点下方灰框复制链接：\n"
            f"<code>{latest_link}</code>"
        )

        # 2. 构造按钮 (只保留一个查看原网页)
        keyboard = {
            "inline_keyboard": [
                [
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
