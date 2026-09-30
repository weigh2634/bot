import os
import sys
import time
from datetime import datetime, timezone, timedelta
import cloudscraper
from bs4 import BeautifulSoup

# ================= 參數設定區 =================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

TARGETS = [
    {'board': 'Gamesale', 'keyword': '狂熱'},
    {'board': 'Lifeismoney', 'keyword': 'go share'},
    {'board': 'Lifeismoney', 'keyword': 'goshare'}
]

CHECK_PAGES = 2
SEEN_FILE = 'seen_articles.txt'
# ==============================================

def is_sleep_time():
    """判斷目前台灣時間是否處於勿擾時段 (23:00 - 06:00)"""
    tz_taiwan = timezone(timedelta(hours=8))
    now = datetime.now(tz_taiwan)
    current_hour = now.hour

    # 跨日區間判斷：23:00 至隔日 05:59
    if current_hour >= 15 or current_hour < 6:
        print(f"目前台灣時間為 {now.strftime('%Y-%m-%d %H:%M:%S')}，處於勿擾時段 (23:00 - 06:00)，跳過本次執行。")
        return True
    return False

def load_seen_articles():
    """讀取已經發布過通知的文章連結"""
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_seen_articles(seen):
    """保存看過的文章，只保留最新 500 筆避免檔案過大"""
    lines = list(seen)[-500:]
    with open(SEEN_FILE, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(f"{line}\n")

def send_telegram_message(message):
    """發送 Telegram 訊息"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("未設定 Token 或 Chat ID！")
        return

    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'disable_web_page_preview': False
    }
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"發送 Telegram 失敗: {e}")

def fetch_ptt_board(board, pages=CHECK_PAGES):
    """使用 cloudscraper 穿透防護爬取看板文章"""
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    url = f"https://www.ptt.cc/bbs/{board}/index.html"
    cookies = {'over18': '1'}
    articles = []
    
    for i in range(pages):
        try:
            response = scraper.get(url, cookies=cookies, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for div in soup.find_all('div', class_='r-ent'):
                title_elem = div.find('div', class_='title').find('a')
                if title_elem:
                    title = title_elem.text.strip()
                    link = "https://www.ptt.cc" + title_elem['href']
                    articles.append({'title': title, 'link': link})
            
            prev_link = soup.find('a', string=lambda text: text and '上頁' in text)
            if prev_link:
                url = "https://www.ptt.cc" + prev_link['href']
                time.sleep(1)
            else:
                break
        except Exception as e:
            print(f"爬取看板 {board} 第 {i+1} 頁失敗: {e}")
            break
            
    return articles

def main():
    seen_articles = load_seen_articles()
    new_found = False

    for target in TARGETS:
        board = target['board']
        keyword = target['keyword']
        articles = fetch_ptt_board(board)
        print(f"[{board}] 成功抓取到 {len(articles)} 篇文章")
        
        for article in articles:
            if keyword.lower() in article['title'].lower() and article['link'] not in seen_articles:
                seen_articles.add(article['link'])
                new_found = True
                
                message = (
                    f"🔔 PTT 關鍵字通知\n"
                    f"看板：{board}\n"
                    f"關鍵字：{keyword}\n"
                    f"標題：{article['title']}\n"
                    f"連結：{article['link']}"
                )
                send_telegram_message(message)
                print(f"發現文章並推播: {article['title']}")
                
        time.sleep(1)

    if new_found:
        save_seen_articles(seen_articles)
        print("已更新文章歷史紀錄檔。")
    else:
        print("本次未發現新關鍵字文章。")

if __name__ == '__main__':
    # 執行前檢查是否處於睡覺勿擾時段
    if is_sleep_time():
        sys.exit(0)
        
    main()
