import streamlit as st
import google.generativeai as genai
from PIL import Image
import os
import pandas as pd
import io
import base64
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. 頁面與環境設定 ---
st.set_page_config(page_title="Gemini 驗證碼雲端訓練營", page_icon="☁️", layout="wide")

# 讀取 Gemini API Key
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = os.environ.get("GEMINI_API_KEY", "")

if not api_key:
    st.warning("⚠️ 請設定 `GEMINI_API_KEY`。")
    st.stop()

genai.configure(api_key=api_key)

# --- 2. Google Sheets 連線設定 ---
SHEET_NAME = "captcha_learning_db"  # 請確保您的試算表名稱與此一致
SCOPE = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

@st.cache_resource
def get_gspread_client():
    try:
        # 從 Streamlit secrets 讀取 GCP 憑證
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ Google Sheets 連線失敗: {e}\n請檢查 secrets 設定。")
        return None

def init_sheet():
    """初始化試算表，如果沒有標題列則加上"""
    client = get_gspread_client()
    if not client: return None
    
    try:
        sheet = client.open(SHEET_NAME).sheet1
        # 檢查第一列是否為標題，如果不是則寫入
        if not sheet.row_values(1):
            sheet.append_row(["timestamp", "model_used", "correct_text", "image_base64"])
        return sheet
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ 找不到名為 `{SHEET_NAME}` 的試算表。請確認您已建立並分享給機器人。")
        return None
    except Exception as e:
        st.error(f"初始化錯誤: {e}")
        return None

# --- 3. 圖片處理 (Base64) ---
def image_to_base64(image, max_width=150):
    """將 PIL Image 轉為 Base64 字串，並限制大小以符合 Sheet 儲存格限制"""
    img_copy = image.copy()
    # 等比例縮放
    w_percent = (max_width / float(img_copy.size[0]))
    h_size = int((float(img_copy.size[1]) * float(w_percent)))
    img_copy = img_copy.resize((max_width, h_size), Image.Resampling.LANCZOS)
    
    buffered = io.BytesIO()
    img_copy.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return img_str

def base64_to_image(base64_str):
    """將 Base64 字串還原為 PIL Image"""
    try:
        img_data = base64.b64decode(base64_str)
        return Image.open(io.BytesIO(img_data))
    except:
        return None

# --- 4. 存取邏輯 ---
def save_to_sheet(image, text, model):
    sheet = init_sheet()
    if not sheet: return False
    
    try:
        img_b64 = image_to_base64(image)
        timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        # 寫入一行：時間, 模型, 答案, 圖片編碼
        sheet.append_row([timestamp, model, text, img_b64])
        return True
    except Exception as e:
        st.error(f"寫入失敗: {e}")
        return False

def load_gold_standard(limit=5):
    """從 Google Sheet 讀取最新的 N 筆資料"""
    sheet = init_sheet()
    if not sheet: return []
    
    try:
        # 讀取所有資料 (注意：若資料量過大需改用分頁讀取)
        all_values = sheet.get_all_records()
        df = pd.DataFrame(all_values)
        
        if df.empty: return []
        
        # 取最後 N 筆
        recent_records = df.tail(limit).iloc[::-1] # 反轉順序，最新的在前
        
        examples = []
        for index, row in recent_records.iterrows():
            img = base64_to_image(row['image_base64'])
            if img:
                examples.append({'image': img, 'text': row['correct_text']})
        return examples
    except Exception as e:
        st.warning(f"讀取範本時發生錯誤 (可能是空表): {e}")
        return []

# --- 5. Session State ---
if 'current_image' not in st.session_state: st.session_state.current_image = None
if 'current_result' not in st.session_state: st.session_state.current_result = None
if 'last_processed_file' not in st.session_state: st.session_state.last_processed_file = None

# --- 6. 側邊欄：雲端資料中心 ---
with st.sidebar:
    st.header("☁️ Google Sheets 資料中心")
    
    sheet = init_sheet()
    if sheet:
        # 簡單統計
        row_count = len(sheet.col_values(1)) - 1 # 扣除標題
        st.metric("雲端已標註樣本", row_count)
        
        st.divider()
        st.caption(f"連結至試算表: `{SHEET_NAME}`")
        st.info("💡 資料已永久儲存在您的 Google Drive 中，重啟也不會消失。")
    else:
        st.error("無法連接雲端資料庫")

# --- 7. 主介面邏輯 (Few-shot 注入) ---
st.title("🚀 Gemini 驗證碼雲端訓練營")
st.caption("使用 Google Sheets 作為永久記憶體")

model_option = st.selectbox("選擇模型", ["gemini-2.5-flash-lite", "gemini-2.0-flash"])

# 從雲端載入範本
with st.spinner("正在從 Google Sheets 下載最新教材..."):
    gold_standard = load_gold_standard(limit=3)

st.progress(min(len(gold_standard) / 3, 1.0), 
            text=f"已載入 {len(gold_standard)}/3 個雲端範本")

uploaded_file = st.file_uploader("上傳圖片", type=["png", "jpg", "jpeg"])

if uploaded_file:
    img = Image.open(uploaded_file)
    st.session_state.current_image = img
    st.image(img, caption="待辨識圖片", width=200)

    if uploaded_file.name != st.session_state.last_processed_file:
        with st.spinner("AI 正在思考中..."):
            try:
                model = genai.GenerativeModel(model_option)
                
                prompt = """你是一個驗證碼辨識專家。
1. 視覺分析：描述顏色、干擾線。
2. 輸出：直接輸出文字，無空格。
範例格式：[圖片] -> 描述：... 結果：A7b2"""
                
                content_payload = [prompt]
                
                # 注入雲端範本
                for sample in gold_standard:
                    content_payload.extend([sample['image'], f"描述：雲端範例。結果：{sample['text']}"])
                
                content_payload.append(st.session_state.current_image)
                
                response = model.generate_content(content_payload)
                if response.text:
                    st.session_state.current_result = response.text.split("結果：")[-1].strip()
                
                st.session_state.last_processed_file = uploaded_file.name
                st.rerun()
            except Exception as e:
                st.error(f"API 錯誤: {e}")

# --- 8. 標註與上傳 ---
if st.session_state.current_result:
    st.success(f"🤖 辨識結果：**{st.session_state.current_result}**")
    
    c1, c2 = st.columns(2)
    
    # 存入 Google Sheets
    if c1.button("✅ 正確 (上傳雲端)", use_container_width=True):
        with st.spinner("正在寫入 Google Sheets..."):
            if save_to_sheet(st.session_state.current_image, st.session_state.current_result, model_option):
                st.toast("已上傳至雲端資料庫！")
                st.session_state.current_result = None
                st.rerun()

    with c2:
        with st.popover("❌ 錯誤 (修正並上傳)"):
            manual_ans = st.text_input("輸入正確答案：")
            if st.button("送出修正"):
                if manual_ans:
                    with st.spinner("正在寫入 Google Sheets..."):
                        if save_to_sheet(st.session_state.current_image, manual_ans.strip(), model_option):
                            st.toast("修正並已上傳！")
                            st.session_state.current_result = None
                            st.rerun()
