import streamlit as st
import google.generativeai as genai
from PIL import Image
import os
import sqlite3
import pandas as pd
import io
import datetime

# --- 1. 頁面與環境設定 ---
st.set_page_config(page_title="Gemini 驗證碼標註神器", page_icon="🧠", layout="wide")

try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = os.environ.get("GEMINI_API_KEY", "")

if not api_key:
    st.warning("⚠️ 請設定 `GEMINI_API_KEY`。")
    st.stop()

genai.configure(api_key=api_key)

# --- 2. SQLite 資料庫管理 ---
DB_FILE = "captcha_learning.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 建立表格：儲存 圖片(BLOB)、正確文字、模型、時間
    c.execute('''CREATE TABLE IF NOT EXISTS records
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  image_data BLOB,
                  correct_text TEXT,
                  model_used TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def save_to_db(image, text, model):
    try:
        # 將 PIL Image 轉為 Bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_blob = img_byte_arr.getvalue()
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO records (image_data, correct_text, model_used) VALUES (?, ?, ?)",
                  (img_blob, text, model))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"資料庫寫入失敗: {e}")
        return False

def load_gold_standard(limit=5):
    """從資料庫讀取最新的 N 筆資料作為 Few-shot 範本"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT image_data, correct_text FROM records ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    
    examples = []
    for img_blob, text in rows:
        image = Image.open(io.BytesIO(img_blob))
        examples.append({'image': image, 'text': text})
    # 因為是用 DESC 取出的，這裏反轉一下讓順序自然一點
    return examples[::-1]

# 初始化資料庫
init_db()

# --- 3. 初始化 Session State ---
if 'current_image' not in st.session_state: st.session_state.current_image = None
if 'current_result' not in st.session_state: st.session_state.current_result = None
if 'last_processed_file' not in st.session_state: st.session_state.last_processed_file = None

# --- 4. 側邊欄：資料管理與匯出 ---
with st.sidebar:
    st.header("📂 資料管理中心")
    
    # 讀取資料庫統計
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT id, correct_text, model_used, timestamp FROM records", conn)
    conn.close()
    
    st.metric("已標註樣本數", len(df))
    
    if not df.empty:
        st.write("### 📥 匯出資料")
        # CSV 下載
        csv = df.to_csv(index=False).encode('utf-8-sig') # utf-8-sig 避免 Excel 中文亂碼
        st.download_button(
            "下載 CSV 報表",
            csv,
            "captcha_records.csv",
            "text/csv",
            key='download-csv'
        )
        # JSON 下載
        json_str = df.to_json(orient="records", force_ascii=False)
        st.download_button(
            "下載 JSON 格式",
            json_str,
            "captcha_records.json",
            "application/json",
            key='download-json'
        )
        
        with st.expander("預覽最近 5 筆資料"):
            st.dataframe(df.tail(5))
    
    st.divider()
    st.info("💡 提示：若部署在 Streamlit Cloud，SQLite 檔案可能會在重啟後重置。建議定期下載 CSV 備份。")

# --- 5. 主介面邏輯 ---
st.title("🚀 Gemini 驗證碼標註神器")
st.caption("整合 SQLite 資料庫與 CSV 匯出功能")

model_option = st.selectbox("選擇模型", ["gemini-2.5-flash-lite", "gemini-2.0-flash"])

# 從資料庫自動載入 Few-shot 範本
gold_standard = load_gold_standard(limit=3)
st.progress(min(len(gold_standard) / 3, 1.0), 
            text=f"已載入 {len(gold_standard)}/3 個資料庫範本作為 AI 教材")

uploaded_file = st.file_uploader("上傳圖片", type=["png", "jpg", "jpeg"])

if uploaded_file:
    img = Image.open(uploaded_file)
    st.session_state.current_image = img
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(img, caption="待辨識圖片", width=200)

    if uploaded_file.name != st.session_state.last_processed_file:
        with st.spinner("AI 正在思考中..."):
            try:
                model = genai.GenerativeModel(model_option)
                
                # 建構 Prompt
                prompt = """你是一個驗證碼辨識專家。
1. 視覺分析：描述顏色、干擾線。
2. 輸出：直接輸出文字，無空格。
範例格式：[圖片] -> 描述：... 結果：A7b2"""
                
                content_payload = [prompt]
                # 注入資料庫中的真實範例
                for sample in gold_standard:
                    content_payload.extend([sample['image'], f"描述：資料庫範例。結果：{sample['text']}"])
                
                content_payload.append(st.session_state.current_image)
                
                response = model.generate_content(content_payload)
                if response.text:
                    st.session_state.current_result = response.text.split("結果：")[-1].strip()
                
                st.session_state.last_processed_file = uploaded_file.name
                st.rerun()
            except Exception as e:
                st.error(f"錯誤: {e}")

# --- 6. 標註與存檔 ---
if st.session_state.current_result:
    st.success(f"🤖 辨識結果：**{st.session_state.current_result}**")
    
    c1, c2 = st.columns(2)
    
    # 存入資料庫
    if c1.button("✅ 正確 (存入資料庫)", use_container_width=True):
        if save_to_db(st.session_state.current_image, st.session_state.current_result, model_option):
            st.toast("已儲存至 SQLite！")
            st.session_state.current_result = None
            st.rerun()

    with c2:
        with st.popover("❌ 錯誤 (修正並存檔)"):
            manual_ans = st.text_input("輸入正確答案：")
            if st.button("送出修正"):
                if manual_ans:
                    if save_to_db(st.session_state.current_image, manual_ans.strip(), model_option):
                        st.toast("修正並已儲存！")
                        st.session_state.current_result = None
                        st.rerun()
