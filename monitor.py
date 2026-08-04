import os
import json
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from deep_translator import GoogleTranslator

# ------------------------------------------------------------------
# 1. 监控网站配置文件
# ------------------------------------------------------------------
SITES = [
    {
        "name": "界面新闻快报",
        "url": "https://www.jiemian.com/lists/48.html",
        "lang": "中文",
        "scroll_times": 3,
        "click_selector": None,
        "item_selector": ".news-view, .card, div[class*='item'], div.news-header",
        "title_selector": "a.title, h3, a",
        "link_selector": "a"
    },
    {
        "name": "科技日报",
        "url": "https://www.stdaily.com/web/gdxw/node_324.html",
        "lang": "中文",
        "scroll_times": 0,
        "click_selector": "a:has-text('下一页')",
        "item_selector": "ul.list li, .news_list li, div.list-item, li",
        "title_selector": "a",
        "link_selector": "a"
    },
    {
        "name": "俄罗斯卫星通讯社",
        "url": "https://sputniknews.cn/",
        "lang": "中文",
        "scroll_times": 3,
        "click_selector": ".b-more_btn, button:has-text('加载更多')",
        "item_selector": ".b-plainlist__item, .b-article, div[class*='item']",
        "title_selector": "a.b-plainlist__title, .b-article__title, a",
        "link_selector": "a"
    },
    {
        "name": "韩联社 (能源/资源)",
        "url": "https://www.yna.co.kr/industry/energy-resource",
        "lang": "韩语",
        "scroll_times": 1,
        "click_selector": ".btn-more, a:has-text('더보기')",
        "item_selector": "div.news-con, ul.list li, article, div.item-box",
        "title_selector": "strong.tit, .tit, a",
        "link_selector": "a"
    },
    {
        "name": "国际文传电讯 (Top Stories)",
        "url": "https://www.interfax.com/newsroom/top-stories/",
        "lang": "英语",
        "scroll_times": 0,
        "click_selector": ".pagination .next",
        "item_selector": ".news-item, .top-story, div.news, div[class*='item']",
        "title_selector": "h3, a.title, a",
        "link_selector": "a"
    },
    {
        "name": "白通社 (白俄罗斯通讯社)",
        "url": "https://chn.belta.by/all_news",
        "lang": "中文",
        "scroll_times": 0,
        "click_selector": ".pager_next",
        "item_selector": ".news_item, .news_list_item, div.news_item, li",
        "title_selector": "a.news_item_title, a",
        "link_selector": "a"
    },
    {
        "name": "哈通社",
        "url": "https://cn.inform.kz/lenta/",
        "lang": "中文",
        "scroll_times": 0,
        "click_selector": "a.next",
        "item_selector": ".lenta-item, .news-item, article, div[class*='item']",
        "title_selector": "a.title, h3, a",
        "link_selector": "a"
    },
    {
        "name": "马尼拉时报",
        "url": "https://www.manilatimes.net/news",
        "lang": "英语",
        "scroll_times": 2,
        "click_selector": None,
        "item_selector": ".article-item, .article-title-wrap, div.article, article",
        "title_selector": "a.article-title, h3 a, a",
        "link_selector": "a"
    },
    {
        "name": "Interesting Engineering (Energy)",
        "url": "https://interestingengineering.com/energy",
        "lang": "英语",
        "scroll_times": 3,
        "click_selector": "button:has-text('Load More')",
        "item_selector": "article, div[class*='Card'], div.flex",
        "title_selector": "h2, h3, a",
        "link_selector": "a"
    },
    {
        "name": "DOTmed 医疗设备新闻",
        "url": "https://www.dotmed.com/news/",
        "lang": "英语",
        "scroll_times": 2,
        "click_selector": None,
        "item_selector": ".news_item, .article, tr.news_row, div[class*='news']",
        "title_selector": "a.news_title, h3, a",
        "link_selector": "a"
    }
]

translator = GoogleTranslator(source='auto', target='zh-CN')

async def scrape_site(site, context):
    print(f"\n🚀 开始抓取: {site['name']} ({site['url']})")
    page = await context.new_page()
    
    try:
        # 设置请求头伪装真实电脑浏览器
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ru;q=0.7,fr;q=0.6"
        })

        # 打开页面并强制等待加载
        try:
            await page.goto(site['url'], timeout=45000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"[{site['name']}] 页面加载超时或部分阻止，尝试强行读取: {e}")
            
        await page.wait_for_timeout(4000) # 强制等待 4 秒让渲染完成

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
                        await page.wait_for_timeout(2500)
            except Exception as e:
                print(f"[{site['name']}] 点击加载按钮提示: {e}")

        # 尝试提取卡片列表
        elements = await page.query_selector_all(site['item_selector'])
        print(f"[{site['name']}] 匹配到 {len(elements)} 个可能的新闻块")

        # 备用方案：如果特定选择器匹配不到，退回使用通用 HTML 标签
        if len(elements) == 0:
            print(f"[{site['name']}] 启用通用备选选择器...")
            elements = await page.query_selector_all("article, h2, h3, div[class*='title']")

        results = []
        for el in elements:
            try:
                title_el = await el.query_selector(site['title_selector']) if site['title_selector'] else el
                link_el = await el.query_selector(site['link_selector']) if site['link_selector'] else el

                if not title_el: title_el = el
                if not link_el: link_el = el

                raw_title = (await title_el.inner_text()).strip() if title_el else ""
                link = await link_el.get_attribute("href") if link_el else ""

                # 清理脏数据与过短的无意义菜单项
                raw_title = raw_title.replace("\n", " ").strip()
                if len(raw_title) < 6:
                    continue

                if link and not link.startswith("http"):
                    from urllib.parse import urljoin
                    link = urljoin(site['url'], link)

                if raw_title and link:
                    # 翻译处理
                    zh_title = raw_title
                    if site['lang'] != "中文":
                        try:
                            zh_title = translator.translate(raw_title[:200]) # 限制长度防止翻译接口报错
                        except Exception as te:
                            print(f"[{site['name']}] 翻译跳过: {te}")
                            zh_title = raw_title

                    results.append({
                        "site_name": site['name'],
                        "lang": site['lang'],
                        "raw_title": raw_title,
                        "zh_title": zh_title,
                        "url": link,
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
            except Exception as item_err:
                continue

        # 按标题进行简单去重
        unique_results = []
        seen_titles = set()
        for item in results:
            if item['raw_title'] not in seen_titles:
                seen_titles.add(item['raw_title'])
                unique_results.append(item)

        print(f"✅ [{site['name']}] 成功获取到 {len(unique_results)} 条内容")
        await page.close()
        return unique_results[:10] # 每个网站只留前 10 条最新

    except Exception as e:
        print(f"❌ 抓取 {site['name']} 失败: {e}")
        try: await page.close()
        except: pass
        return []

def generate_html(all_data):
    """生成漂亮的 HTML 汇总网页"""
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
        .zh-title {{ font-size: 17px; font-weight: 600; margin: 10px 0 6px 0; color: #1e293b; line-height: 1.4; }}
        .raw-title {{ font-size: 13px; color: #64748b; margin-bottom: 12px; word-break: break-all; }}
        .btn {{ display: inline-block; padding: 6px 14px; background: var(--primary); color: white; text-decoration: none; border-radius: 6px; font-size: 13px; font-weight: 500; transition: background 0.2s; }}
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
    print("\n🎉 已成功重新生成 index.html 网页！")

async def main():
    async with async_playwright() as p:
        # 启动浏览器并配置全局伪装参数
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            device_scale_factor=1,
        )
        
        all_results = []
        for site in SITES:
            res = await scrape_site(site, context)
            all_results.extend(res)
            
        await browser.close()
        generate_html(all_results)

if __name__ == "__main__":
    asyncio.run(main())
