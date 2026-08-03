import os
import json
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from deep_translator import GoogleTranslator

# ------------------------------------------------------------------
# 1. 监控网站配置文件（你可以随时修改/增加这里的网址和规则）
# ------------------------------------------------------------------
SITES = [
    {
        "name": "Le Monde (示例法语网)",
        "url": "https://www.lemonde.fr/",
        "lang": "法语",
        "scroll_times": 2,       # 自动向下滚动次数
        "click_selector": None,  # 如果有"加载更多"按钮，填写 CSS 选择器，例如 "#load-more"
        "item_selector": "section.teaser", # 文章卡片选择器
        "title_selector": "h3",
        "link_selector": "a"
    },
    # 你后续可以按上面的格式继续添加剩余 59 个网站
]

translator = GoogleTranslator(source='auto', target='zh-CN')

async def scrape_site(site, page):
    print(f"正在抓取: {site['name']}...")
    try:
        await page.goto(site['url'], timeout=60000, wait_until="domcontentloaded")
        
        # 处理滚动
        for _ in range(site.get('scroll_times', 0)):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)
            
        # 处理点击加载更多
        if site.get('click_selector'):
            try:
                for _ in range(2):
                    btn = await page.query_selector(site['click_selector'])
                    if btn and await btn.is_visible():
                        await btn.click()
                        await page.wait_for_timeout(2000)
            except Exception as e:
                print(f"点击加载按钮提示: {e}")

        # 提取数据
        elements = await page.query_selector_all(site['item_selector'])
        results = []
        for el in elements[:10]: # 每个网站只取前 10 条最新更新
            title_el = await el.query_selector(site['title_selector']) if site['title_selector'] else el
            link_el = await el.query_selector(site['link_selector']) if site['link_selector'] else el
            
            if title_el and link_el:
                raw_title = (await title_el.inner_text()).strip()
                link = await link_el.get_attribute("href")
                
                if link and not link.startswith("http"):
                    # 处理相对路径 URL
                    from urllib.parse import urljoin
                    link = urljoin(site['url'], link)
                
                if raw_title:
                    # 自动翻译标题为中文
                    try:
                        zh_title = translator.translate(raw_title)
                    except:
                        zh_title = raw_title
                        
                    results.append({
                        "site_name": site['name'],
                        "lang": site['lang'],
                        "raw_title": raw_title,
                        "zh_title": zh_title,
                        "url": link,
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
        return results
    except Exception as e:
        print(f"抓取 {site['name']} 失败: {e}")
        return []

def generate_html(all_data):
    """生成清爽的 HTML 汇总网页"""
    html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌐 每日情报汇总 Dashboard</title>
    <style>
        :root {{ --bg: #f8fafc; --card: #ffffff; --text: #0f172a; --primary: #2563eb; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 20px; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        header {{ background: var(--card); padding: 24px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 24px; }}
        h1 {{ margin: 0 0 8px 0; font-size: 24px; color: var(--primary); }}
        .meta {{ color: #64748b; font-size: 14px; }}
        .card {{ background: var(--card); padding: 20px; border-radius: 12px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }}
        .tag {{ display: inline-block; padding: 2px 8px; background: #e0f2fe; color: #0369a1; border-radius: 4px; font-size: 12px; font-weight: 600; margin-right: 8px; }}
        .site-name {{ font-weight: 600; color: #475569; font-size: 14px; }}
        .zh-title {{ font-size: 18px; font-weight: 600; margin: 10px 0 6px 0; color: #1e293b; line-height: 1.4; }}
        .raw-title {{ font-size: 14px; color: #64748b; margin-bottom: 12px; font-style: italic; }}
        .btn {{ display: inline-block; padding: 8px 16px; background: var(--primary); color: white; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: 500; transition: background 0.2s; }}
        .btn:hover {{ background: #1d4ed8; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🌐 每日多语言网页更新汇总</h1>
            <div class="meta">上次自动更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC) | 共抓取 {len(all_data)} 条最新内容</div>
        </header>
        <main>
    """
    for item in all_data:
        html_content += f"""
            <div class="card">
                <div>
                    <span class="tag">{item['lang']}</span>
                    <span class="site-name">{item['site_name']}</span>
                </div>
                <div class="zh-title">【译】{item['zh_title']}</div>
                <div class="raw-title">原文: {item['raw_title']}</div>
                <a href="{item['url']}" target="_blank" class="btn">🔗 点击跳转原文</a>
            </div>
        """
        
    html_content += """
        </main>
    </div>
</body>
</html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("已成功生成 index.html 网页！")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        all_results = []
        for site in SITES:
            res = await scrape_site(site, page)
            all_results.extend(res)
            
        await browser.close()
        
        # 生成网页
        generate_html(all_results)

if __name__ == "__main__":
    asyncio.run(main())
