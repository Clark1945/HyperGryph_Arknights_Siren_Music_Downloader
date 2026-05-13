import requests
import random
import time
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import os
import re
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import Tk, Label, Button, Frame, PhotoImage, Canvas, Scrollbar, VERTICAL, RIGHT, LEFT, Y, BOTH
from PIL import Image, ImageTk
import threading
import queue


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
DEFAULT_DELAY_TIME = 3
DEFAULT_MAX_RETRIES = 5

# 設定最大重試次數與回退時間
session = requests.Session()  # 1️⃣ 建立 Session
retries = Retry(
    total=DEFAULT_MAX_RETRIES,               # 2️⃣ 最多重試 5 次
    backoff_factor=2,      # 3️⃣ 指數退避策略 (2, 4, 8, 16, 32 秒)
    status_forcelist=[429, 500, 502, 503, 504]  # 4️⃣ 只對這些 HTTP 狀態碼進行重試
)
session.mount("https://", HTTPAdapter(max_retries=retries))  # 5️⃣ 為所有 HTTPS 請求設定重試策略

# 設定下載目錄
DOWNLOAD_DIR = "music_downloads"

COVER_DIR = "covers"


# 確保下載目錄存在
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def ensure_image_folder():
    '''確保專輯路徑存在'''
    os.makedirs("covers", exist_ok=True)

def fetch_album_ids():
    '''取得所有專輯的cid'''
    url = "https://monster-siren.hypergryph.com/api/albums"
    response = fetch_with_retry(url)

    data = response.json()
    if data.get("code") == 0:
        return [(album["cid"], sanitize_filename(album["name"])) for album in data["data"]]
    return []

def create_album_entry(root, cid, name):
    '''渲染專輯與下載功能'''
    frame = Frame(root, bd=1,padx=10,pady=10)
    frame.pack(fill="x",padx=10,pady=5,anchor="w")

    if is_cover_downloaded(cid):
        local_path = os.path.join("covers",  cid + ".jpg")
    else:
        detail = fetch_album_detail(cid)
        if not detail:
            return
        cover_url = detail["coverUrl"]
        filename = f"{cid}.jpg"
        local_path = download_image(cover_url, filename)
        
    img = load_image(local_path)
    img_label = Label(frame, image=img)
    img_label.image = img  # keep reference
    img_label.pack(side=LEFT)

    # 專輯名稱 + 按鈕
    right_frame = Frame(frame)
    right_frame.pack(side=LEFT, padx=10)

    name_label = Label(right_frame, text=name, font=("Arial", 16))
    name_label.pack(anchor="w")

    btn = Button(right_frame, text="下載封面", command=lambda: download_now(cid))
    btn.pack(anchor="w")

def is_cover_downloaded(album_cid, folder="covers"):
    '''判斷專輯圖片是否已存在'''
    local_path = os.path.join(folder, f"{album_cid}.jpg")
    return os.path.exists(local_path)

def fetch_album_detail(cid):
    '''根據cid取得所有專輯封面'''
    url = f"https://monster-siren.hypergryph.com/api/album/{cid}/detail"
    response = requests.get(url)
    return response.json().get("data")

def download_image(url, filename):
    '''下載圖片'''
    filepath = os.path.join("covers", filename)
    if not os.path.exists(filepath):
        response = requests.get(url)
        with open(filepath, 'wb') as f:
            f.write(response.content)
    return filepath

def load_image(path, size=(150, 150)):

    with Image.open(path) as image:

        image = image.convert("RGB")

        image = image.resize(size)

        copied = image.copy()

    return ImageTk.PhotoImage(copied)

def download_now(cid):
    
    data = fetch_album_detail(cid)
    for song in data["songs"]:
        source_url, song_name = fetch_song_info(song["cid"])
        download_song(source_url, song_name)

def fetch_song_info(cid):
    '''取得音樂下載 URL'''
    url = f"https://monster-siren.hypergryph.com/api/song/{cid}"
    response = fetch_with_retry(url)

    data = response.json()
    if data.get("code") == 0:
        return data["data"].get("sourceUrl"), sanitize_filename(data["data"].get("name"))
    return None, None

def download_song(url, name):
    '''下載音樂文件'''
    if not url:
        print(f"❌ 無法下載 {name}，找不到音樂 URL")
        return

    response = fetch_with_retry(url,True)
    response.raise_for_status()

    file_name = os.path.join(DOWNLOAD_DIR, f"{name}.{url.split(".")[-1]}")  # 存放在資料夾內
    with open(file_name, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)

    print(f"✅ 已下載: {file_name}")

def fetch_with_retry(url,stream=False):
    try:
        response = session.get(url,headers=HEADERS,stream=stream)
        response.raise_for_status()  # 檢查 HTTP 狀態碼
        return response
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None


def create_random_delay():
    '''避免短時間內大量請求，隨機延遲 3~6 秒'''
    delay = random.uniform(DEFAULT_DELAY_TIME, DEFAULT_DELAY_TIME*2)
    print(f"Waiting {delay:.2f} seconds before next request...")
    time.sleep(delay)

def fetch_song_ids():
    '''取得所有音樂的 ID'''
    url = "https://monster-siren.hypergryph.com/api/songs"
    response = fetch_with_retry(url)

    data = response.json()
    if data.get("code") == 0:
        return [(song["cid"], sanitize_filename(song["name"])) for song in data["data"]["list"]]
    return []

def sanitize_filename(name):
    """移除 Windows 不允許的特殊字元"""
    return re.sub(r'[<>:"/\\|?*\']', '_', name)



if __name__ == "__main__":

    ensure_image_folder()

    root = Tk()
    ui_queue = queue.Queue()
    image_refs = []
    root.title("賽壬唱片下載器")
    root.geometry("600x800")
    # 建立 Canvas + Scrollbar
    canvas = Canvas(root)
    scrollbar = Scrollbar(root, orient="vertical", command=canvas.yview)
    scroll_frame = Frame(canvas)

    # 當 scroll_frame 內容變化時，更新捲動範圍
    scroll_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

    # 當 canvas 大小改變時，讓 scroll_frame 寬度跟著變
    def _on_canvas_configure(event):
        canvas.itemconfig(canvas_window, width=event.width)

    canvas.bind("<Configure>", _on_canvas_configure)
    canvas.configure(yscrollcommand=scrollbar.set)

    # 綁定滑鼠滾輪捲動
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    # 先 pack scrollbar 再 pack canvas，確保 scrollbar 不會被擠掉
    scrollbar.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)


    def load_albums_async():
        album_list = fetch_album_ids()

        for cid, name in album_list:
            try:
                if not is_cover_downloaded(cid):
                    detail = fetch_album_detail(cid)

                    if not detail:
                        continue

                    download_image(
                        detail["coverUrl"],
                        f"{cid}.jpg"
                    )

                local_path = os.path.join(
                    "covers",
                    cid + ".jpg"
                )

                ui_queue.put(
                    (cid, name, local_path)
                )

            except Exception as e:
                print(f"⚠️ 跳過 {name} ({cid})：{e}")


    def render_album_ui(root, cid, name, local_path):

        img = load_image(local_path)
        image_refs.append(img)

        frame = Frame(
            root,
            bd=1,
            padx=10,
            pady=10
        )

        frame.pack(
            fill="x",
            padx=10,
            pady=5,
            anchor="n"
        )


        img_label = Label(frame, image=img)
        img_label.image = img
        img_label.pack(side="left")

        right_frame = Frame(frame)
        right_frame.pack(
            side="left",
            anchor="n",
            padx=10,
            pady=10
        )

        name_label = Label(
            right_frame,
            text=name,
            font=("Arial", 16)
        )

        name_label.pack(anchor="w")

        download_btn = Button(
            right_frame,
            text="下載音樂",
            command=lambda: threading.Thread(
                target=download_now,
                args=(cid,),
                daemon=True
            ).start()
        )

        download_btn.pack(anchor="w", pady=(10, 0))


    def process_ui_queue():

        processed = 0

        while not ui_queue.empty() and processed < 5:

            try:
                cid, name, local_path = ui_queue.get_nowait()

                render_album_ui(
                    scroll_frame,
                    cid,
                    name,
                    local_path
                )

                processed += 1

            except queue.Empty:
                break

        canvas.configure(
            scrollregion=canvas.bbox("all")
        )

        root.after(50, process_ui_queue)

    # 用背景執行緒載入，不阻塞 UI
    threading.Thread(target=load_albums_async).start()
    process_ui_queue()

    # 所有內容加載完後，強制更新佈局並重新計算捲動範圍
    root.update_idletasks()
    canvas.configure(scrollregion=canvas.bbox("all"))

    root.mainloop()