import streamlit as st
import google.generativeai as genai
from PIL import Image
import os

# --- 頁面設定 ---
st.set_page_config(page_title="Gemini 驗證碼破解神器", page_icon="⚡", layout="centered")

# --- 從 Streamlit Secrets 讀取 API Key ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = os.environ.get("GEMINI_API_KEY", "")

# --- 初始化 Session State ---
if 'stats' not in st.session_state: st.session_state.stats = {'total': 0, 'correct': 0}
if 'history' not in st.session_state: st.session_state.history = []
if 'last_processed_file' not in st.session_state: st.session_state.last_processed_file = None
if 'current_result' not in st.session_state: st.session_state.current_result = None
if 'is_rated' not in st.session_state: st.session_state.is_rated = False
if 'quota_exceeded_models' not in st.session_state: st.session_state.quota_exceeded_models = set()

# --- 主標題 ---
st.title("⚡ Gemini 驗證碼破解神器 (Lite版)")

# --- 檢查 API Key ---
if not api_key:
    st.warning("⚠️ 尚未設定 API Key！請在 Streamlit Cloud 的 Settings -> Secrets 設定 `GEMINI_API_KEY`。")
    st.stop()

genai.configure(api_key=api_key)

# ==========================================
# 🎛️ 模型選擇器 (更新：2.5-flash-lite 為預設)
# ==========================================
raw_model_list = [
    "gemini-2.5-flash-lite",    # 👑 (預設) 最新輕量極速版
    "gemini-2.0-flash",         # (穩定) 舊版主力
    "gemini-2.5-flash",         # (強大) 最新標準版
    "gemini-2.0-flash-lite",    # (備用) 舊版輕量
    "gemini-3-flash-preview",   # (測試) 每日限20次
]

def format_model_name(model_id):
    # 如果是預設模型，加個標記讓它顯眼一點
    if model_id == "gemini-2.5-flash-lite":
        prefix = "✨ (預設) "
    else:
        prefix = ""
        
    if model_id in st.session_state.quota_exceeded_models:
        return f"🚫 (額度已滿) {model_id}"
        
    return f"{prefix}{model_id}"

# 這裡預設會選第一個 (index 0)，也就是 2.5-flash-lite
selected_model = st.selectbox("🤖 選擇模型", raw_model_list, format_func=format_model_name)

st.divider()

# ==========================================
# 📊 數據儀表板
# ==========================================
col1, col2, col3 = st.columns(3)
total = st.session_state.stats['total']
correct = st.session_state.stats['correct']
rate = (correct / total * 100) if total > 0 else 0.0
col1.metric("測試總數", f"{total}")
col2.metric("正確次數", f"{correct}")
col3.metric("準確率", f"{rate:.1f}%")

# ==========================================
# 📂 上傳與辨識
# ==========================================
st.markdown("### 📂 上傳圖片 (自動辨識)")
uploaded_file = st.file_uploader("拖曳圖片到這裡...", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="預覽圖片", width=200)

    if uploaded_file.name != st.session_state.last_processed_file:
        if selected_model in st.session_state.quota_exceeded_models:
            st.error("🛑 此模型今日額度已滿，請切換！")
        else:
            with st.spinner(f"正在使用 {selected_model} 極速辨識中..."):
                try:
                    model = genai.GenerativeModel(selected_model)
                    prompt = "這是一個驗證碼圖片。請忽略背景線條與噪點，直接輸出圖片中的文字（含大小寫英文與數字）。不要有空格，不要解釋。"
                    
                    response = model.generate_content([prompt, image])
                    
                    # --- 防崩潰檢查 ---
                    if response.candidates and response.candidates[0].content.parts:
                        result = response.text.strip()
                    else:
                        result = "⚠️ 無法辨識 (空回應)"
                    # -----------------
                    
                    st.session_state.current_result = result
                    st.session_state.last_processed_file = uploaded_file.name
                    st.session_state.is_rated = False
                    st.rerun()
                    
                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg:
                        st.session_state.quota_exceeded_models.add(selected_model)
                        st.error(f"⚠️ 模型 `{selected_model}` 額度已滿！")
                        st.rerun() # 自動刷新以更新選單狀態
                    elif "404" in error_msg:
                        st.error(f"❌ 找不到模型 {selected_model}，請切換。")
                    else:
                        st.error(f"發生錯誤: {e}")

    if st.session_state.current_result:
        st.success(f"🤖 辨識結果： **{st.session_state.current_result}**")

        if not st.session_state.is_rated:
            st.markdown("👇 **結果正確嗎？**")
            b1, b2 = st.columns(2)
            if b1.button("✅ 正確", use_container_width=True):
                st.session_state.stats['total'] += 1
                st.session_state.stats['correct'] += 1
                st.session_state.history.insert(0, f"✅ [{selected_model}] {uploaded_file.name}: {st.session_state.current_result}")
                st.session_state.is_rated = True
                st.rerun()
            if b2.button("❌ 錯誤", use_container_width=True):
                st.session_state.stats['total'] += 1
                st.session_state.history.insert(0, f"❌ [{selected_model}] {uploaded_file.name}: {st.session_state.current_result}")
                st.session_state.is_rated = True
                st.rerun()

if st.session_state.history:
    with st.expander("📜 最近紀錄"):
        for h in st.session_state.history:
            st.text(h)