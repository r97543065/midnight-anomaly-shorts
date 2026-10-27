# 每日故事選品與無配音片尾廣告

中文故事全部結束後，接上獨立 8 秒產品卡（可設 5–12 秒）。廣告不呼叫 TTS，音軌為靜音；不覆蓋故事反轉。英文故事和既有英文課程推廣維持原流程。中文影片加廣告後仍須在 60–90 秒內，超長會失敗並要求縮短故事。

## 已實作與待接通部分

- 已實作：依故事自動查詢已授權的商品資料轉接服務、篩選有效台灣分潤商品、依故事關鍵字排名、從已核實商品資料產生每日文案／slogan、產生圖片卡、FFmpeg 接片、靜音 QA、YouTube 說明連結與廣告揭露。
- 待接通：台灣蝦皮分潤 API 帳號權限、官方文件與認證方式，以及對應的商品搜尋轉接服務。本專案沒有宣稱已能直接搜尋蝦皮後台，也沒有猜測台灣 API 網址或借用其他國家 API。
- 公開搜尋出來的普通蝦皮商品不能當成已確認的分潤商品；只靠網址格式也不能證明分潤資格。`affiliate_eligible` 等欄位必須由你授權的資料服務依官方回應填入，不能從一般爬蟲推定。
- 在資料來源接通前，不會假造商品、佣金、價格或分潤網址，也不會自動把 stories/today.json 既有的未確認候選商品寫進影片。

## 接通與啟用

1. 向蝦皮分潤後台／官方客服確認你的台灣帳號可否申請 Affiliate Open API，以及商品搜尋、追蹤連結的官方文件。賣家 Open Platform 的 AMS API 是賣家活動管理服務，不能直接當成創作者分潤商品搜尋服務。
2. 依取得的官方文件建立你授權的轉接服務，回傳以下 JSON。這個 feed contract 是本專案定義的介面，**不是蝦皮原生 API 格式**。轉接服務需要即時搜尋、確認可分潤與可購買，並產生屬於你的追蹤連結。只有可信任的服務能設定為來源；檢查格式本身無法獨立證明服務提供的資料是真的。
3. 在 GitHub Actions Secrets 設定 `SHOPEE_AFFILIATE_FEED_URL`（HTTPS，無查詢字串）及選用的 `SHOPEE_AFFILIATE_FEED_TOKEN`。不要把密鑰放進程式碼、JSON 或聊天。服務不能重新導向到其他網址。
4. 設定 Repository Variable `PRODUCT_ADS_ENABLED=true`，讓每次影片建置先選品並附加廣告。預設關閉，避免現有影片生成流程因尚未設定來源而失敗。啟用後查詢失敗或沒有合格商品，會停止該次建置，不會沿用昨天商品。
5. 合併到 default branch 並啟用 `PRODUCT_ADS_ENABLED=true` 後，`daily-product-ads.yml` 每天台灣時間 08:00 產生商品廣告 JSON、文案、預覽卡 artifact；GitHub 可能延遲排程。尚未啟用時排程會跳過，手動執行仍可檢查來源設定。它讀取當下 `stories/today.json`，不生成新故事、不提交商品資料到公開分支、不自動上傳 YouTube。影片建置會針對當次故事重新查詢。可先手動執行測試。

## 授權商品來源介面

GET `$SHOPEE_AFFILIATE_FEED_URL?market=TW&story_id=...&q=故事標題&limit=30`

如有 token，送出 `Authorization: Bearer ...`。來源應回傳：

```json
{
  "products": [{
    "id": "來源商品識別碼",
    "name": "反光吊牌",
    "market": "TW",
    "available": true,
    "affiliate_eligible": true,
    "affiliate_url": "由官方分潤資料服務回傳的真實 HTTPS 追蹤連結",
    "source": "你的授權來源識別／官方回應識別碼",
    "verified_at": "含時區的實際驗證時間",
    "expires_at": "含時區的實際到期時間",
    "keywords": ["末班車", "深夜", "路邊"],
    "benefit_zh": "來源已核實的簡短商品特色",
    "commission_rate": 0.01
  }]
}
```

時間使用 ISO 8601 並包含時區。驗證時間不得超過 24 小時，不能已過期或超前現在超過 5 分鐘。`commission_rate` 可省略，使用 0–1 小數；不會把它印成固定獲利承諾。選品以故事相關度為主，不以佣金最高為主。文案採用固定故事結束語與商品事實組合，不會改動故事或自動生成未經核實的產品效能。

支援本機的授權匯出檔測試（需要定期更新，並非即時搜尋）：

```sh
python scripts/product_ads.py --feed /private/verified-offers.json --render-preview
PRODUCT_AD_FILE=output/product-ad.json python scripts/make_video.py
PRODUCT_AD_FILE=output/product-ad.json python scripts/production_qa.py
```

`product-ad.json` 綁定 `story_id` 和商品 ID。QA 會驗證片尾中段音量低於 -80 dBFS，影片與上傳說明的商品 ID 也必須一致。上傳說明使用 story 中 `youtube.description_zh/en`，不再以簡短固定文案取代。影片資訊與片尾卡都會清楚標記商品推廣；連結只放說明欄，沒有發明的折扣或安全保證。

## 離線驗證

需要 Python Pillow、fonttools、FFmpeg 及完整繁體中文字型（Ubuntu: `fonts-noto-cjk`）。也可用 `PRODUCT_AD_FONT` 指定完整中文字型。倉庫內既有 `assets/common/NotoSansTC.ttf` 僅含故事用字子集，不適合任意商品文案；程式會檢查每個字的字形，遇到缺字直接停止而不是輸出方框字。

```sh
python -m unittest discover -s tests -v
python tests/smoke_product_ad.py
```

smoke 使用合成的「測試商品」、短測試音和當次時間戳，驗證真實 MP4 拼接、保留前段聲音、後段靜音、長度增加及影像卡。測試素材不會發布到 YouTube，也不代表已有真實可分潤商品。
