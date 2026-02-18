# 🚀 Gemini Captcha Labeler (驗證碼標註與訓練神器)

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://streamlit.io)
[![SQLite](https://img.shields.io/badge/Database-SQLite-blue)](https://www.sqlite.org/)
[![Gemini API](https://img.shields.io/badge/Google-Gemini%20API-orange)](https://ai.google.dev/)

一個整合 **AI 辨識**、**人工標註** 與 **資料庫管理** 的全方位驗證碼工具。
不僅能破解驗證碼，還能將您的修正紀錄自動存入 **SQLite** 資料庫，並作為 Few-shot 範本反哺給 AI，實現真正的「越用越聰明」。

## ✨ 核心功能 (Key Features)

* **🧠 自我進化 AI**：自動從 SQLite 資料庫讀取最新的正確案例，動態生成 Few-shot Prompt，大幅提升辨識率。
* **💾 本地資料庫 (SQLite)**：
    * 每一筆「✅ 正確」或「❌ 修正」的紀錄（包含原始圖片 BLOB）都會被永久儲存。
    * 支援數萬筆級別的標註資料管理。
* **📥 數據匯出 (Export)**：
    * **CSV / JSON** 一鍵下載功能。
    * 方便將標註好的資料匯出，用於微調 (Fine-tuning) 其他模型。
* **📝 二階段推理**：採用「視覺描述 -> 邏輯判斷」機制，對抗複雜干擾線。

## 🛠️ 安裝與執行

### 1. 複製專案與安裝
```bash
git clone [https://github.com/您的帳號/gemini-captcha-solver.git](https://github.com/您的帳號/gemini-captcha-solver.git)
cd gemini-captcha-solver
pip install -r requirements.txt
2. 設定 API Key請在 .streamlit/secrets.toml 中設定：Ini, TOMLGEMINI_API_KEY = "您的API_KEY"
3. 啟動Bashstreamlit run app.py
啟動後，系統會自動在目錄下建立 captcha_learning.db 資料庫檔案。📂 資料庫結構 (Database Schema)本工具使用 records 資料表儲存所有紀錄：欄位名稱類型說明idINTEGER自動編號image_dataBLOB驗證碼原始圖片 (Binary)correct_textTEXT正確的驗證碼文字model_usedTEXT辨識時使用的模型timestampDATETIME建檔時間⚠️ Streamlit Cloud 部署注意事項若您部署於 Streamlit Cloud，由於雲端環境的暫存特性，SQLite 資料庫檔案可能會在應用程式重啟或休眠後重置。建議：請善用側邊欄的 「下載 CSV 報表」 功能，定期備份您的標註資料。🤝 貢獻歡迎提交 PR！[ ] 支援外部資料庫連接 (如 PostgreSQL / Google Sheets) 以解決雲端儲存問題。[ ] 增加圖表分析 (每日辨識率趨勢)。Powered by Google Gemini & Streamlit
### 💡 重要提示：依賴套件更新
由於我們引入了 `pandas` 來處理匯出功能，請記得更新您的 `requirements.txt`，確保包含以下內容：

```text
streamlit
google-generativeai
Pillow
pandas
