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

# --- 辅助函数：获取网页 Meta 信息 ---
def get_meta_content(soup, property_name):
    # 尝试查找 <meta property="og:xxx">
    tag = soup.find('meta', property=property_name)
    if not tag:
        # 尝试查找 <meta name="xxx">
        tag = soup.find('meta', attrs={'name': property_name})
    if tag and tag.get('content'):
        return tag['content']
    return None

# --- 核心功能：精准提取并发布 ---
def post_to_telegraph(url):
    try:
        t = TelegraphPoster(use_api=True, access_token=TELEGRAPH_TOKEN)
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. 【修复标题】优先抓取 og:title，其次抓取 h1
        real_title = get_meta_content(soup, 'og:title')
        if not real_title:
            h1 = soup.find('h1')
            if h1:
                real_title = h1.get_text().strip()
            else:
                real_title = soup.title.string.strip() if soup.title else "未命名文章"
        
        # 移除标题中常见的后缀 (如果有)
        real_title = real_title.split(' - ')[0].split(' | ')[0]

        # 2. 【修复图片】获取封面图
        cover_image_url = get_meta_content(soup, 'og:image')

        # 3. 【精准定位正文】
        # 针对该类网站，通常内容在 class="post_content" 或 "entry-content"
        content = soup.find('div', class_='post_content')
        if not content:
            content = soup.find('div', class_='entry-content')
        if not content:
            content = soup.find('article')
        if not content:
            # 最后的兜底，但要小心不要抓到 footer
            content = soup.body

        # 4. 【温柔清洗】只删除绝对的垃圾，不再按关键词误杀
        # 删除脚本、样式、iframe
        for tag in content(['script', 'style', 'iframe', 'noscript', 'button', 'input']):
            tag.decompose()
            
        # 删除明确的垃圾块 (广告、分享栏、评论区)
        # 这里只删除包含特定 class 的 div，防止误删正文
        bad_classes = ['share', 'comment', 'ads', 'related', 'recommend', 'footer', 'sidebar']
        for tag in content.find_all('div'):
            classes = tag.get('class', [])
            if any(bad in str(c).lower() for c in classes for bad in bad_classes):
                tag.decompose()
        
        # 删除底部的“上一篇/下一篇”导航 (通常在 ul 或 nav 里)
        for tag in content.find_all(['nav', 'ul', 'li']):
             if 'pager' in str(tag.get('class', [])) or 'pagination' in str(tag.get('class', [])):
                 tag.decompose()

        # 5. 发布到 Telegraph
        # 注意：这里我们手动把封面图插入到正文最前面，确保预览一定有图
        html_content = str(content)
        if cover_image_url:
            # 这一步是为了让 Telegraph 识别到封面图
            html_content = f'<img src="{cover_image_url}"><br>' + html_content

        result = t.post(
            title=real_title,
            author='品葱精选',
            author_url=url,
            text=html_content
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
    article_url = entry.title # 原始 RSS 链接
    latest_id = entry.get("id", entry.get("link", ""))

    last_id = ""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            last_id = f.read().strip()

    if latest_id != last_id:
        print(f"处理新文章: {article_url}")
        
        # 生成 Telegraph 页面
        iv_link, real_title = post_to_telegraph(article_url)
        
        if iv_link and real_title:
            # 【最终优化外观】
            # 1. 隐形链接：<a href='iv_link'>&#8203;</a> 用于强制显示大图预览
            # 2. 显示文本：文章的真实标题 (real_title)，链接指向 Telegraph
            msg_text = f"<a href='{iv_link}'>&#8203;</a><b><a href='{iv_link}'>{real_title}</a></b>"
        else:
            # 失败兜底
            msg_text = article_url

        # 发送
        send_msg(msg_text)

        # 更新记录
        with open(DB_FILE, "w") as f:
            f.write(latest_id)
        print("完成")
    else:
        print("无更新")

if __name__ == "__main__":
    main()
