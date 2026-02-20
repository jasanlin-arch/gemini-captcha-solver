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

try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = os.environ.get("GEMINI_API_KEY", "")

if not api_key:
    st.warning("⚠️ 尚未設定 API Key！請在 Streamlit Cloud 的 Settings -> Secrets 設定 `GEMINI_API_KEY`。")
    st.stop()

genai.configure(api_key=api_key)

# --- 2. Google Sheets 連線與資料庫邏輯 ---
SHEET_NAME = "captcha_learning_db"
SCOPE = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

@st.cache_resource
def get_gspread_client():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ Google Sheets 連線失敗: {e}\n請檢查 secrets 設定。")
        return None

def init_sheet():
    client = get_gspread_client()
    if not client: return None
    try:
        sheet = client.open(SHEET_NAME).sheet1
        # 若是全新的空白試算表，自動建立 5 個標題欄位
        if not sheet.row_values(1):
            sheet.append_row(["timestamp", "model_used", "correct_text", "image_base64", "status"])
        return sheet
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ 找不到名為 `{SHEET_NAME}` 的試算表。請確認名稱與權限。")
        return None
    except Exception as e:
        st.error(f"初始化錯誤: {e}")
        return None

def image_to_base64(image, max_width=150):
    img_copy = image.copy()
    w_percent = (max_width / float(img_copy.size[0]))
    h_size = int((float(img_copy.size[1]) * float(w_percent)))
    img_copy = img_copy.resize((max_width, h_size), Image.Resampling.LANCZOS)
    buffered = io.BytesIO()
    img_copy.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def base64_to_image(base64_str):
    try:
        img_data = base64.b64decode(base64_str)
        return Image.open(io.BytesIO(img_data))
    except: return None

# 核心修改點：寫入時加上 status 參數
def save_to_sheet(image, text, model, status):
    sheet = init_sheet()
    if not sheet: return False
    try:
        img_b64 = image_to_base64(image)
        timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, model, text, img_b64, status])
        return True
    except Exception as e:
        st.error(f"寫入失敗: {e}")
        return False

def load_gold_standard(limit=5):
    sheet = init_sheet()
    if not sheet: return []
    try:
        all_values = sheet.get_all_records()
        df = pd.DataFrame(all_values)
        if df.empty: return []
        recent_records = df.tail(limit).iloc[::-1]
        examples = []
        for index, row in recent_records.iterrows():
            img = base64_to_image(row['image_base64'])
            if img:
                examples.append({'image': img, 'text': row['correct_text']})
        return examples
    except: return []

# --- 3. 初始化 Session State ---
if 'stats' not in st.session_state: st.session_state.stats = {'total': 0, 'correct': 0}
if 'current_image' not in st.session_state: st.session_state.current_image = None
if 'current_result' not in st.session_state: st.session_state.current_result = None
if 'last_processed_file' not in st.session_state: st.session_state.last_processed_file = None
if 'quota_exceeded_models' not in st.session_state: st.session_state.quota_exceeded_models = set()

# --- 4. 側邊欄：雲端資料中心 (AI 成長儀表板) ---
with st.sidebar:
    st.header("☁️ Google Sheets 資料中心")
    sheet = init_sheet()
    if sheet:
        try:
            # 取得所有紀錄並轉為 DataFrame 進行運算
            all_records = sheet.get_all_records()
            df = pd.DataFrame(all_records)
            row_count = len(df)
            st.metric("雲端已標註樣本", row_count)
            
            # 確保 'status' 欄位存在才進行計算
            if row_count > 0 and 'status' in df.columns:
                # 總體準確率計算
                total_ai_correct = len(df[df['status'] == 'AI答對'])
                overall_acc = (total_ai_correct / row_count) * 100
                
                # 近 10 筆準確率計算
                recent_10 = df.tail(10)
                recent_correct = len(recent_10[recent_10['status'] == 'AI答對'])
                recent_acc = (recent_correct / len(recent_10)) * 100 if len(recent_10) > 0 else 0
                
                st.divider()
                st.write("### 📈 AI 成長指標")
                c1, c2 = st.columns(2)
                c1.metric("歷史總準確率", f"{overall_acc:.1f}%")
                
                # 計算進步幅度
                progress_diff = recent_acc - overall_acc
                c2.metric("近10筆準確率", f"{recent_acc:.1f}%", f"{progress_diff:.1f}%" if row_count >= 10 else None)
        except Exception as e:
            st.warning("目前尚無足夠資料計算準確率，或欄位設定有誤。")
            
        st.divider()
        st.caption(f"連結至試算表: `{SHEET_NAME}`")
    else:
        st.error("無法連接雲端資料庫")

# --- 5. 主介面邏輯 ---
st.title("🚀 Gemini 驗證碼雲端訓練營")

raw_model_list = [
    "gemini-1.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
]

def format_model_name(model_id):
    if model_id == "gemini-1.5-flash": prefix = "✨ (推薦/穩定) "
    elif "pro" in model_id: prefix = "🧠 (高難度用) "
    else: prefix = ""
        
    if model_id in st.session_state.quota_exceeded_models:
        return f"🚫 (額度已滿) {model_id}"
    return f"{prefix}{model_id}"

selected_model = st.selectbox("🤖 選擇模型", raw_model_list, format_func=format_model_name)

# 單次工作階段的數據統計
col1, col2, col3 = st.columns(3)
total = st.session_state.stats['total']
correct = st.session_state.stats['correct']
rate = (correct / total * 100) if total > 0 else 0.0
col1.metric("當前對話總測驗數", f"{total}")
col2.metric("當前對話正確數", f"{correct}")
col3.metric("當前對話準確率", f"{rate:.1f}%")

st.divider()

# --- 6. 辨識與 Few-shot 邏輯 ---
with st.spinner("正在從 Google Sheets 下載最新教材..."):
    gold_standard = load_gold_standard(limit=3)

st.progress(min(len(gold_standard) / 3, 1.0), text=f"已載入 {len(gold_standard)}/3 個雲端範本")

uploaded_file = st.file_uploader("上傳圖片", type=["png", "jpg", "jpeg"])

if uploaded_file:
    img = Image.open(uploaded_file)
    st.session_state.current_image = img
    st.image(img, caption="待辨識圖片", width=200)

    if uploaded_file.name != st.session_state.last_processed_file:
        if selected_model in st.session_state.quota_exceeded_models:
            st.error(f"🛑 模型 {selected_model} 今日額度已滿，請切換其他模型！")
        else:
            with st.spinner(f"正在使用 {selected_model} 思考中..."):
                try:
                    model = genai.GenerativeModel(selected_model)
                    prompt = "你是一個驗證碼辨識專家。\n1. 視覺分析：描述顏色、干擾線。\n2. 輸出：直接輸出文字，無空格。\n範例格式：[圖片] -> 描述：... 結果：A7b2"
                    
                    content_payload = [prompt]
                    for sample in gold_standard:
                        content_payload.extend([sample['image'], f"描述：雲端範例。結果：{sample['text']}"])
                    
                    content_payload.append(st.session_state.current_image)
                    
                    response = model.generate_content(content_payload)
                    if response.text:
                        st.session_state.current_result = response.text.split("結果：")[-1].strip()
                    else:
                        st.session_state.current_result = "⚠️ 無法辨識"
                    
                    st.session_state.last_processed_file = uploaded_file.name
                    st.rerun()

                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg:
                        st.session_state.quota_exceeded_models.add(selected_model)
                        st.error(f"⚠️ {selected_model} 額度已滿！已自動標記，請切換模型。")
                        st.rerun()
                    else:
                        st.error(f"API 錯誤: {e}")

# --- 7. 結果與回饋 (加入 status 紀錄) ---
if st.session_state.current_result:
    st.success(f"🤖 辨識結果：**{st.session_state.current_result}**")
    
    c1, c2 = st.columns(2)
    # 按鈕 A：AI 答對
    if c1.button("✅ 正確 (上傳雲端)", use_container_width=True):
        with st.spinner("正在寫入 Google Sheets..."):
            if save_to_sheet(st.session_state.current_image, st.session_state.current_result, selected_model, "AI答對"):
                st.session_state.stats['total'] += 1
                st.session_state.stats['correct'] += 1
                st.toast("已上傳至雲端資料庫！")
                st.session_state.current_result = None
                st.rerun()

    # 按鈕 B：人工修正
    with c2:
        with st.popover("❌ 錯誤 (修正並上傳)"):
            manual_ans = st.text_input("輸入正確答案：")
            if st.button("送出修正"):
                if manual_ans:
                    with st.spinner("正在寫入 Google Sheets..."):
                        if save_to_sheet(st.session_state.current_image, manual_ans.strip(), selected_model, "人工修正"):
                            st.session_state.stats['total'] += 1
                            st.toast("修正並已上傳！")
                            st.session_state.current_result = None
                            st.rerun()
