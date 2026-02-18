import streamlit as st
import google.generativeai as genai
from PIL import Image
import os

# --- 1. 頁面與環境設定 ---
st.set_page_config(page_title="Gemini 驗證碼進化版", page_icon="🧠", layout="centered")

try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = os.environ.get("GEMINI_API_KEY", "")

if not api_key:
    st.warning("⚠️ 請在 Streamlit Cloud 的 Secrets 設定 `GEMINI_API_KEY`。")
    st.stop()

genai.configure(api_key=api_key)

# --- 2. 初始化 Session State (記憶機制) ---
if 'stats' not in st.session_state: 
    st.session_state.stats = {'total': 0, 'correct': 0}
if 'gold_standard' not in st.session_state: 
    st.session_state.gold_standard = [] 
if 'current_image' not in st.session_state: 
    st.session_state.current_image = None
if 'current_result' not in st.session_state: 
    st.session_state.current_result = None
if 'last_processed_file' not in st.session_state: 
    st.session_state.last_processed_file = None

# --- 3. 核心 Prompt 設計 (二階段分析) ---
def get_advanced_prompt():
    return """
你是一個精準的驗證碼辨識專家。請依照以下步驟處理圖片：
1. **視覺分析**：簡要描述圖片中的文字顏色、有無扭曲以及背景干擾。
2. **最終輸出**：排除干擾後，直接輸出辨識出的文字（含大小寫），嚴禁任何空格。

範例格式：
[範例圖片] -> 描述：已校正範例。結果：A7b2
"""

# --- 4. UI 介面 ---
st.title("🚀 驗證碼 AI 進化實驗室")
st.caption("手動校正功能：您的回饋將成為 AI 的教材")

model_option = st.selectbox("選擇模型", ["gemini-2.5-flash-lite", "gemini-2.0-flash"])

# 顯示目前的 Few-shot 收集進度
st.progress(min(len(st.session_state.gold_standard) / 5, 1.0), 
            text=f"教材庫已收集 {len(st.session_state.gold_standard)}/5 個範例")

uploaded_file = st.file_uploader("上傳圖片", type=["png", "jpg", "jpeg"])

if uploaded_file:
    img = Image.open(uploaded_file)
    st.session_state.current_image = img
    st.image(img, caption="待辨識圖片", width=200)

    if uploaded_file.name != st.session_state.last_processed_file:
        with st.spinner("進行深度辨識中..."):
            try:
                model = genai.GenerativeModel(model_option)
                content_payload = [get_advanced_prompt()]
                # 注入金牌範例 (Few-shot)
                for sample in st.session_state.gold_standard[-3:]:
                    content_payload.extend([sample['image'], f"描述：已校正範例。結果：{sample['text']}"])
                
                content_payload.append(st.session_state.current_image)
                response = model.generate_content(content_payload)
                
                if response.text:
                    st.session_state.current_result = response.text.split("結果：")[-1].strip()
                
                st.session_state.last_processed_file = uploaded_file.name
                st.rerun()
            except Exception as e:
                st.error(f"辨識出錯: {e}")

# --- 5. 結果確認與「手動校正」機制 ---
if st.session_state.current_result:
    st.info(f"🤖 AI 辨識為：**{st.session_state.current_result}**")
    
    col1, col2 = st.columns(2)
    
    # 情況 A：答對了
    if col1.button("✅ 答對了！(存入範本)", use_container_width=True):
        st.session_state.gold_standard.append({'image': st.session_state.current_image, 'text': st.session_state.current_result})
        st.session_state.stats['total'] += 1
        st.session_state.stats['correct'] += 1
        st.session_state.current_result = None
        st.toast("AI 表現優異，已記錄範本！")
        st.rerun()

    # 情況 B：答錯了，手動修正
    with col2:
        with st.popover("❌ 答錯了 (手動校正)"):
            manual_answer = st.text_input("請輸入正確答案：")
            if st.button("送出並教學 AI"):
                if manual_answer:
                    st.session_state.gold_standard.append({
                        'image': st.session_state.current_image, 
                        'text': manual_answer.strip()
                    })
                    st.session_state.stats['total'] += 1
                    st.session_state.current_result = None
                    st.success("校正成功！下次辨識會參考此範例。")
                    st.rerun()

# 統計數據
st.divider()
total = st.session_state.stats['total']
acc = (st.session_state.stats['correct'] / total * 100) if total > 0 else 0
st.metric("當前準確率", f"{acc:.1f}%", delta=f"總測試數: {total}")
