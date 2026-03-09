import requests
from bs4 import BeautifulSoup
import time
import threading
from flask import Flask
import os

# ================= 參數設定區 =================
# 這裡改用 os.environ.get，讓程式去 Render 的環境變數中讀取，保護資安
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# 設定要監聽的看板與關鍵字 (大小寫視為不同)
TARGETS = [
#    {'board': 'Stock', 'keyword': '散熱'},
#    {'board': 'Stock', 'keyword': '晶圓'},
    {'board': 'Lifeismoney', 'keyword': 'goshare'},
    {'board': 'Lifeismoney', 'keyword': '情報'}
]

# 檢查頻率 (秒)
CHECK_INTERVAL = 300  # 5分鐘檢查一次
# ==============================================

# 用來記錄已經通知過的文章網址，避免重複通知
seen_articles = set()

# 建立 Flask 網頁伺服器
app = Flask(__name__)

# 這個簡單的網頁路由是為了讓 Render 保持服務運作，以及讓 UptimeRobot 來 ping
@app.route('/')
def home():
    return "PTT Alarm Bot 正常運作中！"

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

def fetch_ptt_board(board):
    """爬取 PTT 指定看板的最新文章"""
    url = f"https://www.ptt.cc/bbs/{board}/index.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    # 加入 over18=1 的 cookie，以繞過八卦板等滿 18 歲的確認頁面
    cookies = {'over18': '1'}
    
    try:
        response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        articles = []
        for div in soup.find_all('div', class_='r-ent'):
            title_element = div.find('div', class_='title').find('a')
            if title_element:
                title = title_element.text.strip()
                link = "https://www.ptt.cc" + title_element['href']
                articles.append({'title': title, 'link': link})
        return articles
    except Exception as e:
        print(f"爬取看板 {board} 失敗: {e}")
        return []

def run_bot():
    """機器人主要運作邏輯"""
    print("啟動 PTT 關鍵字監聽機器人...")
    send_telegram_message("🤖 PTT 雲端監聽機器人已啟動，不分大小寫比對模式上線！")
    
    while True:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 開始檢查最新文章...")
        
        for target in TARGETS:
            board = target['board']
            keyword = target['keyword']
            
            articles = fetch_ptt_board(board)
            
            for article in articles:
                # 【修改這裡】將關鍵字與標題都轉成小寫後再比對
                if keyword.lower() in article['title'].lower() and article['link'] not in seen_articles:
                    seen_articles.add(article['link'])
                    
                    message = (
                        f"🔔 PTT 關鍵字通知\n"
                        f"看板：{board}\n"
                        f"關鍵字：{keyword}\n"
                        f"標題：{article['title']}\n"
                        f"連結：{article['link']}"
                    )
                    send_telegram_message(message)
                    print(f"發現符合文章並已通知: {article['title']}")
                    
            # 避免對 PTT 伺服器發送請求過快，每個板中間稍微暫停 2 秒
            time.sleep(2)
            
        print(f"檢查完畢，休息 {CHECK_INTERVAL} 秒。")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    # 使用背景執行緒來執行 PTT 爬蟲，才不會卡住網頁伺服器
    bot_thread = threading.Thread(target=run_bot)
    # 將執行緒設為 daemon，這樣主程式結束時它也會跟著結束
    bot_thread.daemon = True 
    bot_thread.start()
    
    # 啟動 Flask 網頁伺服器 (Render 預設會尋找 port 10000 左右，0.0.0.0 代表對外開放)
    # 這裡抓取 Render 自動分配的 PORT 環境變數，若無則預設為 10000
    port = int(os.environ.get('PORT', 10000))

    app.run(host='0.0.0.0', port=port)

