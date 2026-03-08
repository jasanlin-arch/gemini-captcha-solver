import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageFilter, ImageEnhance
import os
import pandas as pd
import io
import base64
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from collections import Counter

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
    if not client:
        return None
    try:
        sheet = client.open(SHEET_NAME).sheet1
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
    except:
        return None

def save_to_sheet(image, text, model, status):
    sheet = init_sheet()
    if not sheet:
        return False
    try:
        img_b64 = image_to_base64(image)
        timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, model, text, img_b64, status])
        return True
    except Exception as e:
        st.error(f"寫入失敗: {e}")
        return False

# ✅ 改善：優先載入「人工修正」的高品質範本
def load_gold_standard(limit=5):
    sheet = init_sheet()
    if not sheet:
        return []
    try:
        all_values = sheet.get_all_records()
        df = pd.DataFrame(all_values)
        if df.empty:
            return []

        examples = []

        if 'status' in df.columns:
            # 優先取人工修正的高品質範本
            df_corrected = df[df['status'] == '人工修正'].tail(3)
            df_ai_correct = df[df['status'] == 'AI答對'].tail(limit - len(df_corrected))
            combined = pd.concat([df_corrected, df_ai_correct]).drop_duplicates()
        else:
            combined = df.tail(limit)

        for _, row in combined.iloc[::-1].iterrows():
            img = base64_to_image(row['image_base64'])
            if img:
                examples.append({'image': img, 'text': row['correct_text']})

        return examples
    except:
        return []

# --- ✅ 新增：圖片預處理函式 ---
def preprocess_captcha(image):
    """對驗證碼圖片進行預處理以提升辨識率"""
    # 轉灰階
    img = image.convert('L')
    # 提高對比度
    img = ImageEnhance.Contrast(img).enhance(2.0)
    # 提高銳利度
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    # 銳化濾鏡
    img = img.filter(ImageFilter.SHARPEN)
    # 放大 2 倍（幫助 AI 看清楚細節）
    w, h = img.size
    img = img.resize((w * 2, h * 2), Image.LANCZOS)
    return img.convert('RGB')

# --- ✅ 新增：單一模型辨識函式 ---
def predict_single(image, model_id, gold_standard):
    """使用單一模型進行辨識，回傳辨識結果字串"""
    # ✅ 改善：精簡且精準的 Prompt
    if "image" in model_id:
        prompt = """你是專業驗證碼 OCR 系統。
請對這張驗證碼執行像素級深度掃描：
1. 過濾背景雜訊（干擾線、網格）
2. 由左至右獨立識別每個字元
3. 嚴格區分大小寫與易混淆字元：l/1、O/0、S/5、B/8、Z/2、I/1、G/6
只輸出最終文字，無空格、無說明，例如：KGWH"""
    elif "pro" in model_id:
        prompt = """你是具備強大邏輯推理能力的驗證碼專家。
先推論干擾線走向，再根據剩餘筆畫特徵推斷最可能的英數組合。
嚴格區分易混淆字元：l/1、O/0、S/5、B/8、Z/2、I/1、G/6
只輸出最終文字，無空格、無說明，例如：KGWH"""
    else:
        prompt = """你是專業驗證碼 OCR 系統。規則：
1. 只輸出驗證碼文字，不加任何說明
2. 嚴格區分大小寫：l(小寫L) vs 1(數字一)、O(大寫O) vs 0(數字零)
3. 常見易混淆字元：S/5、B/8、Z/2、I/1、G/6
4. 忽略背景雜訊、干擾線，專注前景字元
直接輸出結果，例如：KGWH"""

    model = genai.GenerativeModel(model_id)
    content_payload = [prompt]

    for sample in gold_standard:
        content_payload.extend([sample['image'], f"結果：{sample['text']}"])

    content_payload.append(image)

    response = model.generate_content(content_payload)

    if response.candidates and response.candidates[0].content.parts:
        raw_text = response.text.strip()
        # 擷取 "結果：" 後面的文字
        if "結果：" in raw_text:
            return raw_text.split("結果：")[-1].strip()
        # 若無格式，直接取最後一個非空行（最可能是答案）
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        return lines[-1] if lines else raw_text
    else:
        return None

# --- ✅ 新增：多模型投票辨識函式 ---
def predict_ensemble(image, primary_model, gold_standard, use_ensemble):
    """
    use_ensemble=True  → 用 3 個模型投票
    use_ensemble=False → 只用 primary_model
    """
    preprocessed = preprocess_captcha(image)

    if not use_ensemble:
        result = predict_single(preprocessed, primary_model, gold_standard)
        return result or "⚠️ 無法辨識 (AI 交了白卷)", primary_model

    # 投票模型組合（排除額度已滿的模型）
    vote_models = [
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.5-flash",
    ]
    vote_models = [m for m in vote_models if m not in st.session_state.quota_exceeded_models]

    if not vote_models:
        return "⚠️ 所有模型額度已滿，請稍後再試", "none"

    results = []
    used_models = []
    for m in vote_models[:3]:
        try:
            r = predict_single(preprocessed, m, gold_standard)
            if r:
                results.append(r)
                used_models.append(m)
        except Exception as e:
            if "429" in str(e):
                st.session_state.quota_exceeded_models.add(m)

    if not results:
        return "⚠️ 無法辨識 (AI 交了白卷)", "none"

    # 多數決
    winner = Counter(results).most_common(1)[0][0]
    model_label = f"投票({', '.join(used_models)})"
    return winner, model_label

# --- 3. 初始化 Session State ---
if 'stats' not in st.session_state:
    st.session_state.stats = {'total': 0, 'correct': 0}
if 'current_image' not in st.session_state:
    st.session_state.current_image = None
if 'current_result' not in st.session_state:
    st.session_state.current_result = None
if 'current_model_used' not in st.session_state:
    st.session_state.current_model_used = None
if 'last_processed_file' not in st.session_state:
    st.session_state.last_processed_file = None
if 'quota_exceeded_models' not in st.session_state:
    st.session_state.quota_exceeded_models = set()

# --- 4. 側邊欄：雲端資料中心 ---
with st.sidebar:
    st.header("☁️ Google Sheets 資料中心")
    sheet = init_sheet()
    if sheet:
        try:
            all_records = sheet.get_all_records()
            df = pd.DataFrame(all_records)
            row_count = len(df)
            st.metric("雲端已標註樣本", row_count)

            if row_count > 0 and 'status' in df.columns:
                total_ai_correct = len(df[df['status'] == 'AI答對'])
                overall_acc = (total_ai_correct / row_count) * 100

                recent_10 = df.tail(10)
                recent_correct = len(recent_10[recent_10['status'] == 'AI答對'])
                recent_acc = (recent_correct / len(recent_10)) * 100 if len(recent_10) > 0 else 0

                st.divider()
                st.write("### 📈 AI 成長指標")
                c1, c2 = st.columns(2)
                c1.metric("歷史總準確率", f"{overall_acc:.1f}%")

                progress_diff = recent_acc - overall_acc
                c2.metric("近10筆準確率", f"{recent_acc:.1f}%",
                          f"{progress_diff:+.1f}%" if row_count >= 10 else None)

                # ✅ 新增：各模型準確率明細
                st.divider()
                st.write("### 🤖 各模型表現")
                model_stats = df.groupby('model_used').apply(
                    lambda x: pd.Series({
                        '總數': len(x),
                        'AI答對': len(x[x['status'] == 'AI答對']),
                        '準確率': f"{len(x[x['status'] == 'AI答對']) / len(x) * 100:.1f}%"
                    })
                ).reset_index()
                st.dataframe(model_stats[['model_used', '總數', '準確率']], use_container_width=True)

        except Exception as e:
            st.warning("目前尚無足夠資料計算準確率。")

        st.divider()
        st.caption(f"連結至試算表: `{SHEET_NAME}`")
        if st.button("🔄 清除當前對話工作階段數據"):
            st.session_state.stats = {'total': 0, 'correct': 0}
            st.rerun()
    else:
        st.error("無法連接雲端資料庫")

# --- 5. 主介面 ---
st.title("🚀 Gemini 驗證碼雲端訓練營")

# 模型選擇
raw_model_list = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.5-pro",
]

def format_model_name(model_id):
    labels = {
        "gemini-2.5-flash-lite": "✨ (預設/極速) ",
        "gemini-2.5-pro":        "🧠 (高難度用) ",
    }
    prefix = labels.get(model_id, "")
    if model_id in st.session_state.quota_exceeded_models:
        return f"🚫 (額度已滿) {model_id}"
    return f"{prefix}{model_id}"

col_model, col_ensemble = st.columns([3, 1])
with col_model:
    selected_model = st.selectbox("🤖 選擇主力模型", raw_model_list, format_func=format_model_name)
with col_ensemble:
    use_ensemble = st.toggle("🗳️ 多模型投票", value=False, help="開啟後使用 3 個模型投票，準確率更高但速度較慢")

# 統計指標
col1, col2, col3 = st.columns(3)
total = st.session_state.stats['total']
correct = st.session_state.stats['correct']
rate = (correct / total * 100) if total > 0 else 0.0
col1.metric("當前對話總測驗數", f"{total}")
col2.metric("當前對話正確數", f"{correct}")
col3.metric("當前對話準確率", f"{rate:.1f}%")

st.divider()

# --- 6. 載入 Few-shot 範本 ---
with st.spinner("正在從 Google Sheets 下載最新教材..."):
    gold_standard = load_gold_standard(limit=5)

st.progress(min(len(gold_standard) / 5, 1.0), text=f"已載入 {len(gold_standard)}/5 個雲端範本（優先採用人工修正樣本）")

# --- 7. 上傳與辨識 ---
uploaded_file = st.file_uploader("上傳驗證碼圖片", type=["png", "jpg", "jpeg"])

if uploaded_file:
    img = Image.open(uploaded_file)
    st.session_state.current_image = img

    col_orig, col_proc = st.columns(2)
    with col_orig:
        st.image(img, caption="原始圖片", width=200)
    with col_proc:
        st.image(preprocess_captcha(img), caption="預處理後（送給 AI 的版本）", width=200)

    if uploaded_file.name != st.session_state.last_processed_file:
        if selected_model in st.session_state.quota_exceeded_models and not use_ensemble:
            st.error(f"🛑 模型 {selected_model} 今日額度已滿，請切換其他模型或開啟投票模式！")
        else:
            mode_label = "多模型投票" if use_ensemble else selected_model
            with st.spinner(f"正在使用 {mode_label} 思考中..."):
                try:
                    result, model_used = predict_ensemble(
                        st.session_state.current_image,
                        selected_model,
                        gold_standard,
                        use_ensemble
                    )
                    st.session_state.current_result = result
                    st.session_state.current_model_used = model_used
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

# --- 8. 結果與回饋 ---
if st.session_state.current_result:
    if "⚠️" in st.session_state.current_result:
        st.warning(f"🤖 辨識結果：**{st.session_state.current_result}**")
    else:
        st.success(f"🤖 辨識結果：**{st.session_state.current_result}**")
        if st.session_state.current_model_used:
            st.caption(f"使用模型：{st.session_state.current_model_used}")

    c1, c2 = st.columns(2)

    if c1.button("✅ 正確 (上傳雲端)", use_container_width=True):
        with st.spinner("正在寫入 Google Sheets..."):
            model_to_save = st.session_state.current_model_used or selected_model
            if save_to_sheet(st.session_state.current_image, st.session_state.current_result, model_to_save, "AI答對"):
                st.session_state.stats['total'] += 1
                st.session_state.stats['correct'] += 1
                st.toast("✅ 已上傳至雲端資料庫！")
                st.session_state.current_result = None
                st.session_state.last_processed_file = None
                st.rerun()

    with c2:
        with st.popover("❌ 錯誤 (修正並上傳)", use_container_width=True):
            manual_ans = st.text_input("輸入正確答案：")
            if st.button("送出修正"):
                if manual_ans:
                    with st.spinner("正在寫入 Google Sheets..."):
                        model_to_save = st.session_state.current_model_used or selected_model
                        if save_to_sheet(st.session_state.current_image, manual_ans.strip(), model_to_save, "人工修正"):
                            st.session_state.stats['total'] += 1
                            st.toast("✏️ 修正並已上傳！")
                            st.session_state.current_result = None
                            st.session_state.last_processed_file = None
                            st.rerun()
