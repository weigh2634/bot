import requests
from bs4 import BeautifulSoup
import time
import threading
from flask import Flask
import os
from collections import deque  # 引入雙向佇列，用來做記憶體自動代謝

# ================= 參數設定區 =================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# 設定要監聽的看板與關鍵字 (目前已升級為不分大小寫)
TARGETS = [
#    {'board': 'Stock', 'keyword': '黃金'},
#    {'board': 'Stock', 'keyword': '晶圓'},
#    {'board': 'Stock', 'keyword': '散熱'},
#    {'board': 'Stock', 'keyword': 'PCB'},
    {'board': 'Gamesale', 'keyword': '世界'},
    {'board': 'Lifeismoney', 'keyword': 'go share'},
    {'board': 'Lifeismoney', 'keyword': 'goshare'}
]

# 檢查頻率 (秒)
CHECK_INTERVAL = 300  # 5分鐘檢查一次
# 每次檢查要往前翻幾頁 (預設 2 頁，防止熱門時段文章洗太快漏接)
CHECK_PAGES = 2
# ==============================================

# 設定最大記憶容量為 1000 筆網址，超過會自動把最舊的擠掉，永遠不會爆記憶體！
seen_articles = deque(maxlen=1000)

app = Flask(__name__)

@app.route('/')
def home():
    return "PTT Alarm Bot 終極版正常運作中！"

def send_telegram_message(message):
    """發送 Telegram 訊息"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("尚未設定 Token 或 Chat ID 環境變數！")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'disable_web_page_preview': False
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"發送 Telegram 失敗: {e}")

def fetch_ptt_board(board, pages=CHECK_PAGES):
    """爬取 PTT 指定看板的最新 N 頁文章"""
    url = f"https://www.ptt.cc/bbs/{board}/index.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    cookies = {'over18': '1'}
    articles = []
    
    for i in range(pages):
        try:
            response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 抓取當前頁面的文章
            for div in soup.find_all('div', class_='r-ent'):
                title_element = div.find('div', class_='title').find('a')
                if title_element:
                    title = title_element.text.strip()
                    link = "https://www.ptt.cc" + title_element['href']
                    articles.append({'title': title, 'link': link})
            
            # 尋找「上頁」的按鈕連結，準備抓下一輪
            prev_link = soup.find('a', string=lambda text: text and '上頁' in text)
            if prev_link:
                url = "https://www.ptt.cc" + prev_link['href']
                # 翻頁稍微停頓 1 秒，當個有禮貌的爬蟲，避免被 PTT 伺服器暫時封鎖
                time.sleep(1) 
            else:
                break # 找不到上頁就提早結束
                
        except Exception as e:
            print(f"爬取看板 {board} 第 {i+1} 頁失敗: {e}")
            break
            
    return articles

def run_bot():
    """機器人主要運作邏輯"""
    print("啟動 PTT 關鍵字監聽機器人 (終極版)...")
    send_telegram_message("🤖 PTT 雲端監聽機器人已啟動！\n✅ 啟用多頁巡邏\n✅ 啟用不分大小寫比對\n✅ 啟用自動代謝記憶體")
    
    while True:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 開始檢查最新 {CHECK_PAGES} 頁文章...")
        
        for target in TARGETS:
            board = target['board']
            keyword = target['keyword']
            
            articles = fetch_ptt_board(board)
            
            for article in articles:
                # 【防漏接與不分大小寫升級】將關鍵字與標題都轉成小寫比對
                if keyword.lower() in article['title'].lower() and article['link'] not in seen_articles:
                    # 【記憶體升級】改用 append 放進 deque
                    seen_articles.append(article['link'])
                    
                    message = (
                        f"🔔 PTT 關鍵字通知\n"
                        f"看板：{board}\n"
                        f"關鍵字：{keyword}\n"
                        f"標題：{article['title']}\n"
                        f"連結：{article['link']}"
                    )
                    send_telegram_message(message)
                    print(f"發現符合文章並已通知: {article['title']}")
                    
            # 每個板中間稍微暫停 2 秒
            time.sleep(2)
            
        print(f"檢查完畢，休息 {CHECK_INTERVAL} 秒。")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True 
    bot_thread.start()
    
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

