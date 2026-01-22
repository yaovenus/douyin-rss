import asyncio
import os
import random
from datetime import datetime, timezone, timedelta
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from feedgen.feed import FeedGenerator

# --- 配置区域 ---
# 这里的链接已经为您转换好的电脑版链接
DOUYIN_USER_URL = "https://www.douyin.com/user/MS4wLjABAAAAczcZgfDJtJ-MwClXIjPH_QRcUphk41pMDw6OpNnsRz1p4NYa9rzwQKORjWdCDUAc"
RSS_FILE = "feed.xml"
RSS_TITLE = "抖音博主更新 - 这里的名字可以自己改" 
# ----------------

async def run():
    async with async_playwright() as p:
        # 准备 User-Agent 列表 (模拟不同的电脑浏览器)
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        
        # 启动浏览器 (必须用 headless=True 在 GitHub Actions 运行)
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        
        # 创建浏览器上下文
        context = await browser.new_context(
            user_agent=random.choice(user_agents),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            viewport={"width": 1920, "height": 1080}
        )
        
        page = await context.new_page()
        # 开启隐身模式，对抗反爬
        await stealth_async(page)

        print(f"正在访问博主主页: {DOUYIN_USER_URL}")
        try:
            # 访问页面
            await page.goto(DOUYIN_USER_URL, wait_until="domcontentloaded", timeout=60000)
            
            # 等待页面关键元素出现 (等待视频卡片)
            print("等待视频列表加载...")
            try:
                # 等待任意一个视频链接出现
                await page.wait_for_selector('a[href*="/video/"]', state="attached", timeout=40000)
            except Exception:
                print("警告：等待超时，可能是反爬验证码拦截，尝试继续执行...")

            # 模拟真人鼠标滚动 (滚动3次，每次间隔随机)
            print("正在模拟滚动...")
            for _ in range(3):
                await page.mouse.wheel(0, random.randint(800, 1200))
                await asyncio.sleep(random.uniform(2, 5))

            print("开始提取视频数据...")
            # 执行 JavaScript 提取数据
            video_data = await page.evaluate('''() => {
                // 选取所有包含 /video/ 的链接
                const anchors = Array.from(document.querySelectorAll('a[href*="/video/"]'));
                const results = [];
                const seen = new Set();

                anchors.forEach(a => {
                    // 必须是有效的视频链接
                    if (!a.href.includes('www.douyin.com/video/')) return;
                    if (seen.has(a.href)) return;

                    let title = "";
                    
                    // 尝试从 img 的 alt 获取标题 (通常最准确)
                    const img = a.querySelector('img');
                    if (img && img.alt) {
                        title = img.alt;
                    } 
                    // 备选：获取文本内容
                    else {
                        title = a.innerText.replace(/\\s+/g, ' ').trim();
                    }
                    
                    // 只有当找到了标题，才算有效数据
                    if (title && title.length > 0) {
                        results.push({ title, link: a.href });
                        seen.add(a.href);
                    }
                });
                return results.slice(0, 15); // 只取前15个
            }''')

            print(f"成功抓取到 {len(video_data)} 个视频")

            if len(video_data) > 0:
                # 生成 RSS
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
                 print("未抓取到数据。可能原因：1. IP被抖音屏蔽(出现验证码) 2. 页面结构变化")

        except Exception as e:
            print(f"运行出错: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
