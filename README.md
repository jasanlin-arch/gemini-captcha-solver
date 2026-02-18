# 🚀 Gemini Captcha Solver (驗證碼 AI 破解神器)

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://streamlit.io)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Gemini API](https://img.shields.io/badge/Google-Gemini%20API-orange)](https://ai.google.dev/)

一個基於 **Google Gemini Vision API** 與 **Streamlit** 的智慧型驗證碼辨識工具。
本專案不只是一個單純的辨識器，它具備 **「自我進化 (Self-Evolving)」** 機制——透過使用者的手動校正與正確回饋，動態建立 Few-shot 範本，讓 AI 越用越聰明！

## ✨ 核心功能 (Key Features)

* **🧠 多模型支援**：自由切換 `Gemini 2.5 Flash-Lite` (極速/省錢) 與 `Gemini 2.0 Flash` (高精確)。
* **📝 二階段推理 (CoT)**：採用「先視覺描述，後邏輯辨識」的 Prompt 策略，有效對抗噪點與扭曲背景。
* **🎯 自動化 Few-shot 學習**：
    * **即時回饋**：當你點擊「✅ 答對了」，該圖片自動成為下一次辨識的範本。
    * **手動校正**：當 AI 答錯時，手動輸入正確答案，立即教會 AI 辨識該類型的驗證碼。
* **📊 數據儀表板**：即時顯示測試總數與準確率統計。
* **🔒 隱私安全**：使用 Gemini Paid Tier (或免費版) API，數據處理符合 Google 隱私規範。

## 🛠️ 安裝與執行 (Installation)

### 1. 複製專案
```bash
git clone [https://github.com/您的帳號/gemini-captcha-solver.git](https://github.com/您的帳號/gemini-captcha-solver.git)
cd gemini-captcha-solver
2. 安裝依賴套件
Bash
pip install -r requirements.txt
注意： 請確保您的 requirements.txt 包含以下內容：

Plaintext
streamlit
google-generativeai
Pillow
3. 設定 API Key
在專案根目錄建立 .streamlit/secrets.toml 檔案（如果是在本機執行）：

Ini, TOML
# .streamlit/secrets.toml
GEMINI_API_KEY = "您的_GOOGLE_API_KEY"
(或者是設定環境變數 GEMINI_API_KEY)

4. 啟動應用程式
Bash
streamlit run app.py
☁️ 部署到 Streamlit Cloud
本專案已針對 Streamlit Cloud 最佳化，一鍵部署即可使用：

將程式碼推送到 GitHub。

登入 Streamlit Cloud 並連結您的 GitHub Repository。

在部署設定的 Advanced Settings -> Secrets 區塊中，貼上您的 API Key：

Ini, TOML
GEMINI_API_KEY = "AIzaSy......"
點擊 Deploy，完成！

💡 使用指南 (Usage)
上傳圖片：將驗證碼圖片拖曳至上傳區。

等待辨識：AI 會分析圖片特徵（顏色、線條、文字）。

給予回饋：

如果 AI 答對：點擊 ✅ 答對了。這張圖會被存入暫存記憶，作為下次辨識的「金牌範本」。

如果 AI 答錯：點擊 ❌ 答錯了，輸入正確文字並送出。AI 會立即學習這個案例。

觀察進化：隨著您累積的範本越多（進度條增長），辨識準確率將顯著提升。

🤝 貢獻 (Contributing)
歡迎提交 Pull Request 或 Issue！
目前的待辦事項 (To-Do)：

[ ] 支援將範本庫匯出為 JSON/CSV。

[ ] 串接 SQLite 資料庫以永久儲存學習紀錄。

[ ] 增加批次上傳功能。

📜 免責聲明 (Disclaimer)
本專案僅供技術研究與教育用途（AI 影像辨識測試），請勿用於非法破解或攻擊網站驗證機制。使用 Google Gemini API 時請遵守其 使用條款。

Created by [您的名字/GitHub ID]


### 💡 貼心小提醒：如何修改
1.  **專案連結**：請將 `git clone` 指令中的 URL 換成您自己的 GitHub 網址。
2.  **作者名稱**：文件最下方的 `[您的名字/GitHub ID]` 記得改成您的署名。
3.  **截圖 (Optional)**：如果您行有餘力，可以在 `## ✨ 核心功能` 下方放一張程式執行的截圖
