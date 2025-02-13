import requests
import random
import time
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import os
import re

user_agents = [ # 隨機Header 避免被偵測為機器人
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0"
]

HEADERS = { # 設定請求標頭
    "referer": "https://monster-siren.hypergryph.com/music",
    "sec-ch-ua": '"Not A(Brand";v="8", "Chromium";v="132", "Microsoft Edge";v="132"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "user-agent": random.choice(user_agents)
}

LAST_INTERRUPTED_INDEX = 0

# 設定最大重試次數與回退時間
session = requests.Session()  # 1️⃣ 建立 Session
retries = Retry(
    total=5,               # 2️⃣ 最多重試 5 次
    backoff_factor=2,      # 3️⃣ 指數退避策略 (2, 4, 8, 16, 32 秒)
    status_forcelist=[429, 500, 502, 503, 504]  # 4️⃣ 只對這些 HTTP 狀態碼進行重試
)
session.mount("https://", HTTPAdapter(max_retries=retries))  # 5️⃣ 為所有 HTTPS 請求設定重試策略

# 設定下載目錄
DOWNLOAD_DIR = "music_downloads"

# 確保下載目錄存在
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def fetch_with_retry(url,stream=False):
    try:
        response = session.get(url,headers=HEADERS,stream=stream)
        response.raise_for_status()  # 檢查 HTTP 狀態碼
        return response
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

# 避免短時間內大量請求，隨機延遲 3~6 秒
def create_random_delay():
    delay = random.uniform(3, 6)
    print(f"Waiting {delay:.2f} seconds before next request...")
    time.sleep(delay)

# 取得所有音樂的 ID
def fetch_song_ids():
    url = "https://monster-siren.hypergryph.com/api/songs"
    response = fetch_with_retry(url)

    data = response.json()
    if data.get("code") == 0:
        return [(song["cid"], sanitize_filename(song["name"])) for song in data["data"]["list"]]
    return []

def sanitize_filename(name):
    """移除 Windows 不允許的特殊字元"""
    return re.sub(r'[<>:"/\\|?*\']', '_', name)

# 取得音樂下載 URL
def fetch_song_info(cid):
    url = f"https://monster-siren.hypergryph.com/api/song/{cid}"
    response = fetch_with_retry(url)

    create_random_delay()

    data = response.json()
    if data.get("code") == 0:
        return data["data"].get("sourceUrl"), sanitize_filename(data["data"].get("name"))
    return None, None


# 下載音樂文件
def download_song(url, name):
    if not url:
        print(f"❌ 無法下載 {name}，找不到音樂 URL")
        return

    response = fetch_with_retry(url,True)
    response.raise_for_status()

    create_random_delay()

    file_name = os.path.join(DOWNLOAD_DIR, f"{name}.{url.split(".")[-1]}")  # 存放在資料夾內
    with open(file_name, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)

    print(f"✅ 已下載: {file_name}")


# 主程式
if __name__ == "__main__":
    song_list = fetch_song_ids()

    for index,(cid, name) in enumerate(song_list):
        print(f"🎵 取得 {name} 的下載連結({index}...")
        if (index >= LAST_INTERRUPTED_INDEX):
            source_url, song_name = fetch_song_info(cid)
            download_song(source_url, song_name)