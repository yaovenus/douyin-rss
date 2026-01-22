import asyncio
import os
import random
from datetime import datetime, timezone, timedelta
from playwright.async_api import async_playwright
# 这里改回了最原始的引用，配合 1.0.6 版本使用
from playwright_stealth import stealth_async
from feedgen.feed import FeedGenerator

# --- 配置区域 ---
DOUYIN_USER_URL = "https://www.douyin.com/user/MS4wLjABAAAAczcZgfDJtJ-MwClXIjPH_QRcUphk41pMDw6OpNnsRz1p4NYa9rzwQKORjWdCDUAc"
RSS_FILE = "feed.xml"
RSS_TITLE = "抖音博主更新 - 财经" 
# ----------------

async def run():
    async with async_playwright() as p:
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        
        # 启动浏览器
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent=random.choice(user_agents),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            viewport={"width": 1920, "height": 1080}
        )
        
        page = await context.new_page()
        # 开启隐身模式
        await stealth_async(page)

        print(f"正在访问: {DOUYIN_USER_URL}")
        try:
            await page.goto(DOUYIN_USER_URL, wait_until="domcontentloaded", timeout=60000)
            
            # 等待视频加载
            try:
                await page.wait_for_selector('a[href*="/video/"]', state="attached", timeout=40000)
            except Exception:
                print("等待超时，可能是反爬或网络慢，尝试直接抓取...")

            # 模拟滚动
            for _ in range(3):
                await page.mouse.wheel(0, random.randint(800, 1200))
                await asyncio.sleep(random.uniform(2, 4))

            # 提取数据
            video_data = await page.evaluate('''() => {
                const anchors = Array.from(document.querySelectorAll('a[href*="/video/"]'));
                const results = [];
                const seen = new Set();

                anchors.forEach(a => {
                    if (!a.href.includes('www.douyin.com/video/')) return;
                    if (seen.has(a.href)) return;

                    let title = "";
                    const img = a.querySelector('img');
                    if (img && img.alt) {
                        title = img.alt;
                    } else {
                        title = a.innerText.replace(/\\s+/g, ' ').trim();
                    }
                    
                    if (title && title.length > 0) {
                        results.push({ title, link: a.href });
                        seen.add(a.href);
                    }
                });
                return results.slice(0, 15);
            }''')

            print(f"抓取结果: {len(video_data)} 个视频")

            if len(video_data) > 0:
                fg = FeedGenerator()
                fg.id(DOUYIN_USER_URL)
                fg.title(RSS_TITLE)
                fg.author({'name': 'DouyinBot', 'email': 'bot@github.com'})
                fg.link(href=DOUYIN_USER_URL, rel='alternate')
                fg.subtitle('Douyin Updates')
                fg.language('zh-CN')

                for item in video_data:
                    fe = fg.add_entry()
                    fe.id(item['link'])
                    fe.title(item['title'])
                    fe.link(href=item['link'])
                    fe.published(datetime.now(timezone.utc))

                fg.rss_file(RSS_FILE)
                print("RSS 文件生成成功！")
            else:
                 print("未抓取到数据，跳过生成 RSS。")

        except Exception as e:
            print(f"运行出错: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
