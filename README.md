# HyperGryph_Arknights_Siren_Music_Downloader
年度最好的音樂遊戲，可下載全音樂。

### 使用方法
1. 安裝Python後本地執行即可，檔案存放於本機當前路徑的/music/download

### 注意事項
* 早期音樂格式為.mp3，後續的音樂格式為.wav
* 執行時如果連線關閉，紀錄Number並放在LAST_INTERRUPTED_INDEX，就可以繼續執行。
* 每次請求約隨機延遲3~6秒。若要調整則調整DEFAULT_DELAY_TIME
* 針對HTTP Code[429, 500, 502, 503, 504]進行重試，上限五次。

