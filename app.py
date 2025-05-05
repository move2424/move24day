# app.py (UI/자동로드 원복, 이사 유형 선택만 동기화 적용, GDrive 로드 AttributeError 수정)

# 1. streamlit 라이브러리를 가장 먼저 임포트합니다.
import streamlit as st

# 2. 다른 st 명령어보다 반드시 먼저 set_page_config를 호출합니다.
st.set_page_config(page_title="이삿날 포장이사 견적서", layout="wide", page_icon="🚚") # 아이콘 유지

# 3. 그 다음에 다른 라이브러리들을 임포트합니다.
import pandas as pd
from datetime import datetime, date
import pytz
import base64
import math
import re
import traceback # 오류 추적용
import os
import json # JSON 처리를 위해 추가
import io # 엑셀 데이터 메모리 처리용
import excel_filler  # 새로 만든 모듈

# 4. 직접 만든 모듈들을 임포트합니다.
try:
    import data # data.py 필요
    import utils # utils.py 필요
    import pdf_generator # pdf_generator.py 필요
    import calculations # calculations.py 필요
    import gdrive_utils # gdrive_utils.py 필요
except ImportError as ie:
    st.error(f"필수 모듈 로딩 실패: {ie}. (app.py와 같은 폴더에 모든 .py 파일이 있는지 확인하세요)")
    st.stop()
except Exception as e:
    st.error(f"모듈 로딩 중 오류 발생: {e}")
    st.stop()


# --- 타이틀 ---
st.markdown("<h1 style='text-align: center; color: #1E90FF;'>🚚 이삿날 스마트 견적 시스템 🚚</h1>", unsafe_allow_html=True) # UI 개선 유지
st.write("")

# ========== 상태 저장/불러오기를 위한 키 목록 정의 ==========
# (이전과 동일)
STATE_KEYS_TO_SAVE = [
    "base_move_type", "is_storage_move", "storage_type", "apply_long_distance",
    "customer_name", "customer_phone", "from_location", "to_location", "moving_date",
    "from_floor", "from_method", "to_floor", "to_method", "special_notes",
    "storage_duration", "long_distance_selector", "vehicle_select_radio",
    "manual_vehicle_select_value", "final_selected_vehicle", "sky_hours_from",
    "sky_hours_final", "add_men", "add_women", "has_waste_check", "waste_tons_input",
    "date_opt_0_widget", "date_opt_1_widget", "date_opt_2_widget",
    "date_opt_3_widget", "date_opt_4_widget",
    "deposit_amount", "adjustment_amount", "regional_ladder_surcharge",
    "remove_base_housewife",
    "prev_final_selected_vehicle",
    "dispatched_1t", "dispatched_2_5t", "dispatched_3_5t", "dispatched_5t"
]
# =========================================================

# --- === 이사 유형 동기화 콜백 함수 정의 === ---
MOVE_TYPE_OPTIONS = list(data.item_definitions.keys()) if hasattr(data, 'item_definitions') else ["가정 이사 🏠", "사무실 이사 🏢"]

def sync_move_type(widget_key):
    """이사 유형 라디오 버튼 변경 시 호출되어 상태 동기화"""
    if widget_key in st.session_state:
        new_value = st.session_state[widget_key]
        if st.session_state.base_move_type != new_value:
            st.session_state.base_move_type = new_value
            # 위젯 상태도 함께 업데이트하여 즉시 반영되도록 함
            other_widget_key = 'base_move_type_widget_tab3' if widget_key == 'base_move_type_widget_tab1' else 'base_move_type_widget_tab1'
            if other_widget_key in st.session_state:
                 st.session_state[other_widget_key] = new_value
            # 필요 시 rerun()을 호출하여 다른 UI 요소 업데이트
            # st.rerun()
# --- ==================================== ---

# --- 세션 상태 초기화 ---
def initialize_session_state():
    """세션 상태 변수들 초기화"""
    try: kst = pytz.timezone("Asia/Seoul"); default_date = datetime.now(kst).date()
    except Exception: default_date = datetime.now().date()
    defaults = {
        "base_move_type": MOVE_TYPE_OPTIONS[0],
        "is_storage_move": False, "storage_type": data.DEFAULT_STORAGE_TYPE,
        "apply_long_distance": False, "customer_name": "", "customer_phone": "",
        "from_location": "", "to_location": "", "moving_date": default_date,
        "from_floor": "", "from_method": data.METHOD_OPTIONS[0],
        "to_floor": "", "to_method": data.METHOD_OPTIONS[0],
        "special_notes": "", "storage_duration": 1,
        "long_distance_selector": data.long_distance_options[0],
        "vehicle_select_radio": "자동 추천 차량 사용", "manual_vehicle_select_value": None,
        "final_selected_vehicle": None, "sky_hours_from": 1, "sky_hours_final": 1,
        "add_men": 0, "add_women": 0, "has_waste_check": False, "waste_tons_input": 0.5,
        "date_opt_0_widget": False, "date_opt_1_widget": False, "date_opt_2_widget": False,
        "date_opt_3_widget": False, "date_opt_4_widget": False, "total_volume": 0.0,
        "total_weight": 0.0, "recommended_vehicle_auto": None, 'pdf_data_customer': None,
        "deposit_amount": 0, "adjustment_amount": 0, "regional_ladder_surcharge": 0,
        "remove_base_housewife": False, "prev_final_selected_vehicle": None,
        "dispatched_1t": 0, "dispatched_2_5t": 0, "dispatched_3_5t": 0, "dispatched_5t": 0,
        "gdrive_search_term": "", "gdrive_search_results": [],
        "gdrive_file_options_map": {}, "gdrive_selected_filename": None, # 불러오기 버튼용 상태 유지
        "gdrive_selected_file_id": None, # 불러오기 버튼용 상태 유지
        "base_move_type_widget_tab1": MOVE_TYPE_OPTIONS[0], # 위젯 상태 추가/유지
        "base_move_type_widget_tab3": MOVE_TYPE_OPTIONS[0], # 위젯 상태 추가/유지
    }
    for key, value in defaults.items():
        if key not in st.session_state: st.session_state[key] = value

    # 위젯 상태 동기화
    if st.session_state.base_move_type_widget_tab1 != st.session_state.base_move_type:
        st.session_state.base_move_type_widget_tab1 = st.session_state.base_move_type
    if st.session_state.base_move_type_widget_tab3 != st.session_state.base_move_type:
        st.session_state.base_move_type_widget_tab3 = st.session_state.base_move_type

    # (숫자 타입 변환 로직 등은 이전과 동일)
    int_keys = ["storage_duration", "sky_hours_from", "sky_hours_final", "add_men", "add_women",
                "deposit_amount", "adjustment_amount", "regional_ladder_surcharge",
                "dispatched_1t", "dispatched_2_5t", "dispatched_3_5t", "dispatched_5t"]
    float_keys = ["waste_tons_input"]
    allow_negative_keys = ["adjustment_amount"]
    for k in int_keys + float_keys:
        try:
            val = st.session_state.get(k, defaults.get(k))
            target_type = int if k in int_keys else float
            if val is None or (isinstance(val, str) and val.strip() == ''): st.session_state[k] = defaults.get(k); continue
            converted_val = target_type(val)
            if k in int_keys:
                if k in allow_negative_keys: st.session_state[k] = converted_val
                else: st.session_state[k] = max(0, converted_val)
            else: st.session_state[k] = max(0.0, converted_val)
        except (ValueError, TypeError): st.session_state[k] = defaults.get(k)
        except KeyError: st.session_state[k] = 0 if k in int_keys else 0.0

    # (동적 품목 키 초기화 로직 등은 이전과 동일)
    processed_init_keys = set(); item_keys_to_save = []
    if hasattr(data, 'item_definitions'):
        for move_type, sections in data.item_definitions.items():
            if isinstance(sections, dict):
                for section, item_list in sections.items():
                    if section == "폐기 처리 품목 🗑️": continue # 폐기 품목 초기화 제외
                    if isinstance(item_list, list):
                        for item in item_list:
                            if item in data.items: # data.items 에 정의된 품목만 초기화
                                key = f"qty_{move_type}_{section}_{item}"
                                item_keys_to_save.append(key) # 저장할 키 목록에도 추가
                                # 초기화: session_state에 없으면 0으로 설정
                                if key not in st.session_state:
                                    st.session_state[key] = 0
                                processed_init_keys.add(key) # 중복 초기화 방지
    else: print("Warning: data.item_definitions not found during initialization.")

    global STATE_KEYS_TO_SAVE
    # 실제 투입 차량 키도 저장 목록에 포함
    dispatched_keys = ["dispatched_1t", "dispatched_2_5t", "dispatched_3_5t", "dispatched_5t"]
    # item_keys_to_save와 dispatched_keys를 STATE_KEYS_TO_SAVE에 병합 (중복 제거)
    STATE_KEYS_TO_SAVE = list(set(STATE_KEYS_TO_SAVE + item_keys_to_save + dispatched_keys))

    # 이전 차량 상태 초기화
    if 'prev_final_selected_vehicle' not in st.session_state:
        st.session_state['prev_final_selected_vehicle'] = st.session_state.get('final_selected_vehicle')

# ========== 상태 저장/불러오기 도우미 함수 ==========
# (prepare_state_for_save 내용은 이전과 동일, 위젯키 제외 확인)
def prepare_state_for_save(keys_to_save):
    """세션 상태에서 지정된 키들의 값을 추출하여 저장 가능한 형태로 반환"""
    state_to_save = {}
    # 위젯 상태 키는 저장 대상에서 제외
    actual_keys_to_save = list(set(keys_to_save + ['prev_final_selected_vehicle']) - set(['base_move_type_widget_tab1', 'base_move_type_widget_tab3']))
    for key in actual_keys_to_save:
        if key in st.session_state:
            value = st.session_state[key]
            # 날짜 객체는 ISO 형식 문자열로 변환
            if isinstance(value, date):
                state_to_save[key] = value.isoformat()
            # 기본 자료형 (str, int, float, bool, list, dict, None)은 그대로 저장
            elif isinstance(value, (str, int, float, bool, list, dict)) or value is None:
                state_to_save[key] = value
            # 그 외 타입은 문자열로 변환 시도 (오류 발생 시 경고 출력)
            else:
                 try:
                     state_to_save[key] = str(value)
                 except:
                     print(f"Warning: Skipping non-serializable key '{key}' of type {type(value)} during save.")
    return state_to_save

# (load_state_from_data 수정: GDrive 상태 초기화 방식 변경)
def load_state_from_data(loaded_data):
    """불러온 데이터(딕셔너리)로 세션 상태를 업데이트"""
    if not isinstance(loaded_data, dict):
        st.error("잘못된 형식의 파일입니다 (딕셔너리가 아님).")
        return False

    # 로드 실패 시 복구를 위한 기본값 정의
    defaults_for_recovery = {
        "base_move_type": MOVE_TYPE_OPTIONS[0], "is_storage_move": False, "storage_type": data.DEFAULT_STORAGE_TYPE,
        "apply_long_distance": False, "customer_name": "", "customer_phone": "", "from_location": "",
        "to_location": "", "moving_date": date.today(), "from_floor": "", "from_method": data.METHOD_OPTIONS[0],
        "to_floor": "", "to_method": data.METHOD_OPTIONS[0], "special_notes": "", "storage_duration": 1,
        "long_distance_selector": data.long_distance_options[0], "vehicle_select_radio": "자동 추천 차량 사용",
        "manual_vehicle_select_value": None, "final_selected_vehicle": None, "prev_final_selected_vehicle": None,
        "sky_hours_from": 1, "sky_hours_final": 1, "add_men": 0, "add_women": 0, "has_waste_check": False, "waste_tons_input": 0.5,
        "date_opt_0_widget": False, "date_opt_1_widget": False, "date_opt_2_widget": False,
        "date_opt_3_widget": False, "date_opt_4_widget": False, "deposit_amount": 0, "adjustment_amount": 0,
        "regional_ladder_surcharge": 0, "remove_base_housewife": False,
        "dispatched_1t": 0, "dispatched_2_5t": 0, "dispatched_3_5t": 0, "dispatched_5t": 0,
    }
    # 동적으로 생성되는 품목 수량 키('qty_...')의 기본값도 0으로 설정
    dynamic_keys = [key for key in STATE_KEYS_TO_SAVE if key.startswith("qty_")]
    for key in dynamic_keys:
        if key not in defaults_for_recovery:
            defaults_for_recovery[key] = 0

    # 타입별 키 목록 정의 (타입 변환 로직용)
    int_keys = ["storage_duration", "sky_hours_from", "sky_hours_final", "add_men", "add_women", "deposit_amount", "adjustment_amount", "regional_ladder_surcharge", "dispatched_1t", "dispatched_2_5t", "dispatched_3_5t", "dispatched_5t"]
    float_keys = ["waste_tons_input"]
    allow_negative_keys = ["adjustment_amount"] # 음수 허용 키
    bool_keys = ["is_storage_move", "apply_long_distance", "has_waste_check", "remove_base_housewife", "date_opt_0_widget", "date_opt_1_widget", "date_opt_2_widget", "date_opt_3_widget", "date_opt_4_widget"]

    load_success_count = 0
    load_error_count = 0
    all_expected_keys = list(set(STATE_KEYS_TO_SAVE)) # 저장될 것으로 예상되는 모든 키 목록

    # 불러온 데이터(loaded_data)를 순회하며 세션 상태 업데이트
    for key in all_expected_keys:
        if key in loaded_data:
            value = loaded_data[key]
            original_value = value # 디버깅용 원본 값 저장
            try:
                target_value = None # 최종적으로 세션 상태에 저장될 값
                # 타입별 변환 로직
                if key == 'moving_date':
                    if isinstance(value, str): target_value = datetime.fromisoformat(value).date()
                    elif isinstance(value, date): target_value = value # 이미 date 객체면 그대로 사용
                    else: raise ValueError("Invalid date format")
                elif key.startswith("qty_"): # 품목 수량 키
                    converted_val = int(value) if value is not None else 0
                    target_value = max(0, converted_val) # 0 이상 보장
                elif key in int_keys:
                    converted_val = int(value) if value is not None else 0
                    if key in allow_negative_keys: target_value = converted_val # 음수 허용
                    else: target_value = max(0, converted_val) # 0 이상 보장
                elif key in float_keys:
                    converted_val = float(value) if value is not None else 0.0
                    target_value = max(0.0, converted_val) # 0.0 이상 보장
                elif key in bool_keys:
                    target_value = bool(value) # 불리언 변환
                else:
                    target_value = value # 그 외 타입은 그대로 사용

                # 변환된 값을 세션 상태에 업데이트
                if key in st.session_state:
                    st.session_state[key] = target_value
                    load_success_count += 1
            except (ValueError, TypeError, KeyError) as e:
                # 타입 변환 실패 또는 기타 오류 발생 시
                load_error_count += 1
                default_val = defaults_for_recovery.get(key) # 기본값 가져오기
                if key in st.session_state:
                    st.session_state[key] = default_val # 세션 상태를 기본값으로 설정
                # print(f"Error loading key '{key}': {e}. Value '{original_value}' reset to default '{default_val}'.")

    if load_error_count > 0:
        st.warning(f"일부 항목({load_error_count}개) 로딩 중 오류가 발생하여 기본값으로 설정되었거나 무시되었습니다.")

    # === 로드 후 GDrive 관련 상태 초기화 (selectbox 연결 상태 직접 수정 방지) ===
    st.session_state.gdrive_search_results = []
    st.session_state.gdrive_file_options_map = {}
    # st.session_state.gdrive_selected_filename = None # 선택된 파일 이름 상태는 유지하지 않음
    st.session_state.gdrive_selected_file_id = None

    # 위젯 상태 동기화 로직은 유지 (탭 간 이동 시 일관성 유지)
    if 'base_move_type' in st.session_state:
        loaded_move_type = st.session_state.base_move_type
        st.session_state.base_move_type_widget_tab1 = loaded_move_type
        st.session_state.base_move_type_widget_tab3 = loaded_move_type

    return True
# ================================================

# --- 메인 애플리케이션 로직 ---
initialize_session_state()

# --- 탭 생성 ---
tab1, tab2, tab3 = st.tabs(["👤 고객 정보", "📋 물품 선택", "💰 견적 및 비용"])

# --- 탭 1: 고객 정보 (레이아웃 원복, 불러오기 버튼 복구) ---
with tab1:
    # === Google Drive 섹션 (버튼 복구) ===
    with st.container(border=True):
        st.subheader("☁️ Google Drive 연동")
        st.caption("Google Drive의 지정된 폴더에 견적을 저장하고 불러옵니다.")
        col_load, col_save = st.columns(2)

        with col_load: # 불러오기
            st.markdown("**견적 불러오기**")
            search_term = st.text_input("검색어 (날짜 YYMMDD 또는 번호 XXXX)", key="gdrive_search_term", help="파일 이름 일부 입력 후 검색")
            if st.button("🔍 견적 검색"):
                search_term_strip = search_term.strip()
                if search_term_strip:
                    with st.spinner("🔄 Google Drive에서 검색 중..."):
                         results = gdrive_utils.search_files(search_term_strip)
                    if results:
                        st.session_state.gdrive_search_results = results
                        st.session_state.gdrive_file_options_map = {res['name']: res['id'] for res in results}
                        # 검색 결과 중 첫 번째 파일의 ID를 기본 선택 ID로 설정
                        if results: # 결과가 있을 때만 ID 설정
                            st.session_state.gdrive_selected_file_id = results[0]['id']
                        st.success(f"✅ {len(results)}개 파일 검색 완료.")
                    else:
                        st.session_state.gdrive_search_results = []
                        st.session_state.gdrive_file_options_map = {}
                        st.session_state.gdrive_selected_file_id = None
                        st.warning("⚠️ 검색 결과가 없습니다.")
                else:
                     st.warning("⚠️ 검색어를 입력하세요.")

            # 검색 결과가 있을 때만 파일 선택 드롭다운 표시
            if st.session_state.gdrive_search_results:
                file_options_display = list(st.session_state.gdrive_file_options_map.keys())
                # 현재 선택된 ID에 해당하는 파일 이름을 기본값으로 설정 시도
                current_selected_name = next((name for name, fid in st.session_state.gdrive_file_options_map.items() if fid == st.session_state.gdrive_selected_file_id), None)
                # 기본값이 옵션 목록에 없으면 첫 번째 옵션 사용
                try:
                    default_index = file_options_display.index(current_selected_name) if current_selected_name in file_options_display else 0
                except ValueError:
                    default_index = 0

                selected_filename = st.selectbox(
                    "불러올 파일 선택:",
                    options=file_options_display,
                    key="gdrive_selected_filename", # 키는 유지하되, 값은 아래 로직으로 업데이트
                    index=default_index
                )
                # Selectbox에서 선택된 이름으로 ID 업데이트
                if selected_filename:
                    st.session_state.gdrive_selected_file_id = st.session_state.gdrive_file_options_map.get(selected_filename)

            # --- 불러오기 버튼 ---
            # 선택된 파일 ID가 있을 때만 버튼 활성화
            load_button_disabled = not bool(st.session_state.gdrive_selected_file_id)
            if st.button("📂 선택 견적 불러오기", disabled=load_button_disabled, key="load_gdrive_btn"):
                file_id = st.session_state.gdrive_selected_file_id
                if file_id:
                    with st.spinner(f"🔄 견적 파일 로딩 중..."):
                        # ----------------- 수정 시작 (AttributeError Fix) -----------------
                        # gdrive_utils.load_file 함수는 JSON을 파싱하여 dict 형태로 반환
                        loaded_data = gdrive_utils.load_file(file_id)
                        loaded_images = [] # 현재 이미지 미지원 상태
                        # ----------------- 수정 끝 ---------------------------------

                    # loaded_data 변수는 이후 로직에서 사용됨 (파일 로드 성공 시 dict, 실패 시 None)
                    if loaded_data:
                        load_success = load_state_from_data(loaded_data) # 세션 상태 업데이트 시도
                        if load_success:
                            st.success("✅ 견적 정보를 성공적으로 불러왔습니다.")
                            st.rerun() # UI 업데이트를 위해 스크립트 재실행
                        # load_state_from_data 내부에서 오류 발생 시 경고 표시됨
                    # gdrive_utils.load_file 내부에서 다운로드/파싱 오류 발생 시 에러 표시됨

        with col_save: # 저장
            st.markdown("**현재 견적 저장**")
            try: kst_ex = pytz.timezone("Asia/Seoul"); now_ex_str = datetime.now(kst_ex).strftime('%y%m%d')
            except: now_ex_str = datetime.now().strftime('%y%m%d')
            phone_ex = utils.extract_phone_number_part(st.session_state.customer_phone, length=4, default="XXXX")
            example_fname = f"{now_ex_str}-{phone_ex}.json"
            st.caption(f"파일명 형식: `{example_fname}`")
            if st.button("💾 Google Drive에 저장", key="save_gdrive_btn"):
                try: kst_save = pytz.timezone("Asia/Seoul"); now_save = datetime.now(kst_save)
                except: now_save = datetime.now()
                date_str = now_save.strftime('%y%m%d')
                phone_part = utils.extract_phone_number_part(st.session_state.customer_phone, length=4)
                # 전화번호 유효성 검사 강화
                if phone_part == "번호없음" or len(phone_part) < 4 or not st.session_state.customer_phone.strip():
                    st.error("⚠️ 저장 실패: 유효한 고객 전화번호(숫자 4자리 이상 포함)를 먼저 입력해주세요.")
                else:
                    save_filename = f"{date_str}-{phone_part}.json"
                    state_data_to_save = prepare_state_for_save(STATE_KEYS_TO_SAVE)
                    with st.spinner(f"🔄 '{save_filename}' 파일 저장 중..."):
                         save_result = gdrive_utils.save_file(save_filename, state_data_to_save) # upload_or_update_json_to_drive 호출
                    if save_result and isinstance(save_result, dict) and save_result.get('id'):
                         status_msg = "업데이트" if save_result.get('status') == 'updated' else "저장"
                         st.success(f"✅ '{save_filename}' 파일 {status_msg} 완료.")
                    else:
                         st.error(f"❌ '{save_filename}' 파일 저장 중 오류 발생.")
            st.caption("동일 파일명 존재 시 덮어씁니다(업데이트).")

    st.divider() # 구분선 원복

    # --- 고객 정보 입력 필드 (레이아웃 원복) ---
    st.header("📝 고객 기본 정보") # 헤더 원복

    # 이사 유형 선택 (탭 1)
    try: current_index_tab1 = MOVE_TYPE_OPTIONS.index(st.session_state.base_move_type)
    except ValueError: current_index_tab1 = 0
    st.radio( # 라벨 원복
        "🏢 **기본 이사 유형**",
        options=MOVE_TYPE_OPTIONS, index=current_index_tab1, horizontal=True,
        key="base_move_type_widget_tab1", on_change=sync_move_type, args=("base_move_type_widget_tab1",)
    )
    # 체크박스 위치 원복
    col_opts1, col_opts2 = st.columns(2)
    with col_opts1: st.checkbox("📦 보관이사 여부", key="is_storage_move") # 라벨 원복
    with col_opts2: st.checkbox("🛣️ 장거리 이사 적용", key="apply_long_distance") # 라벨 원복
    st.write("") # 공백 제거 또는 유지 (선택사항)

    col1, col2 = st.columns(2) # 컬럼 레이아웃 원복
    with col1: # 왼쪽 컬럼 내용 원복
        st.text_input("👤 고객명", key="customer_name")
        st.text_input("📍 출발지 주소", key="from_location") # 라벨 원복
        if st.session_state.get('apply_long_distance'):
            st.selectbox("🛣️ 장거리 구간 선택", data.long_distance_options, key="long_distance_selector")
        st.text_input("🔼 출발지 층수", key="from_floor", placeholder="예: 3, B1") # 지하층 입력 예시 추가
        st.selectbox("🛠️ 출발지 작업 방법", data.METHOD_OPTIONS, key="from_method", help="사다리차, 승강기, 계단, 스카이 중 선택") # 라벨/help 원복

    with col2: # 오른쪽 컬럼 내용 원복
        st.text_input("📞 전화번호", key="customer_phone", placeholder="01012345678") # placeholder 원복
        st.text_input("📍 도착지 주소", key="to_location", placeholder="이사 도착지 상세 주소") # placeholder 원복
        st.text_input("🔽 도착지 층수", key="to_floor", placeholder="예: 5, 10") # 입력 예시 변경
        st.selectbox("🛠️ 도착지 작업 방법", data.METHOD_OPTIONS, key="to_method", help="사다리차, 승강기, 계단, 스카이 중 선택") # help 원복
        current_moving_date_val = st.session_state.get('moving_date')
        # 날짜 타입 검증 및 기본값 설정 강화
        if not isinstance(current_moving_date_val, date):
             try:
                 # ISO 형식 문자열 등 다른 타입 변환 시도 (필요 시 추가)
                 # current_moving_date_val = datetime.fromisoformat(str(current_moving_date_val)).date()
                 if not isinstance(current_moving_date_val, date): raise ValueError
             except (ValueError, TypeError):
                 try: kst_def = pytz.timezone("Asia/Seoul"); default_date_def = datetime.now(kst_def).date()
                 except Exception: default_date_def = datetime.now().date()
                 st.session_state.moving_date = default_date_def # 잘못된 타입이면 기본값으로 설정
        st.date_input("🗓️ 이사 예정일 (출발일)", key="moving_date") # 라벨 원복
        st.caption(f"⏱️ 견적 생성일: {utils.get_current_kst_time_str()}") # 라벨 원복

    st.divider() # 구분선 원복

    # 보관 이사 정보 위치 원복
    if st.session_state.get('is_storage_move'):
        st.subheader("📦 보관이사 추가 정보") # subheader 원복
        # 보관 유형 선택 라디오 버튼 추가 (data.py에 STORAGE_TYPE_OPTIONS 필요)
        if hasattr(data, 'STORAGE_TYPE_OPTIONS'):
            st.radio("보관 유형 선택:", options=data.STORAGE_TYPE_OPTIONS, key="storage_type", horizontal=True)
        else:
             st.warning("data.py에 STORAGE_TYPE_OPTIONS가 정의되지 않아 보관 유형 선택 불가")
        st.number_input("보관 기간 (일)", min_value=1, step=1, key="storage_duration") # 라벨 원복

    st.divider() # 구분선 원복

    # 고객 요구사항 위치/헤더 원복
    st.header("🗒️ 고객 요구사항") # 헤더 원복
    st.text_area("기타 특이사항이나 요청사항을 입력해주세요.", height=100, key="special_notes", placeholder="예: 에어컨 이전 설치 필요, 특정 가구 분해/조립 요청 등")


# =============================================================================
# === Vehicle Selection and Auto-Basket Logic (Original - No StreamlitAPIException Fix Here) ===
# =============================================================================
# 차량 선택 관련 상태 가져오기
prev_vehicle = st.session_state.get('final_selected_vehicle')
prev_prev_vehicle_state = st.session_state.get('prev_final_selected_vehicle') # 이전 스크립트 실행 시의 차량 상태
vehicle_radio_choice = st.session_state.get('vehicle_select_radio', "자동 추천 차량 사용")
manual_vehicle_choice = st.session_state.get('manual_vehicle_select_value')
recommended_vehicle_auto = st.session_state.get('recommended_vehicle_auto') # Tab 2에서 계산된 추천 차량
current_move_type_logic = st.session_state.base_move_type # 현재 이사 유형

# 선택 가능한 차량 목록 가져오기
vehicle_prices_options_logic = data.vehicle_prices.get(current_move_type_logic, {})
available_trucks_logic = sorted(vehicle_prices_options_logic.keys(), key=lambda x: data.vehicle_specs.get(x, {}).get("capacity", 0))

# 최종 선택될 차량 결정 로직
selected_vehicle_logic = None
valid_auto_logic = (recommended_vehicle_auto and "초과" not in recommended_vehicle_auto and recommended_vehicle_auto in available_trucks_logic)

if vehicle_radio_choice == "자동 추천 차량 사용":
    if valid_auto_logic: selected_vehicle_logic = recommended_vehicle_auto
elif vehicle_radio_choice == "수동으로 차량 선택":
    if manual_vehicle_choice in available_trucks_logic: selected_vehicle_logic = manual_vehicle_choice

# 차량 변경 감지 플래그
vehicle_changed_flag = False
# 현재 로직상 선택된 차량(selected_vehicle_logic)과 이전 실행 시 선택된 차량(prev_vehicle) 비교
if selected_vehicle_logic != prev_vehicle:
    # prev_vehicle이 prev_prev_vehicle_state와 같은 경우 = 순수한 차량 변경 (이중 변경 방지)
    if prev_vehicle == prev_prev_vehicle_state:
        st.session_state.final_selected_vehicle = selected_vehicle_logic
        st.session_state.prev_final_selected_vehicle = selected_vehicle_logic # 다음 실행을 위해 상태 업데이트
        vehicle_changed_flag = True # 차량 변경됨 플래그 설정

        # 차량 변경 시 기본 바구니 수량 자동 업데이트 (원본 로직 유지)
        if selected_vehicle_logic in data.default_basket_quantities:
            defaults = data.default_basket_quantities[selected_vehicle_logic]
            basket_section_name = "포장 자재 📦"
            current_move_type_auto = st.session_state.base_move_type
            for item, qty in defaults.items():
                # 바구니 수량 업데이트를 위한 session_state 키 생성
                key = f"qty_{current_move_type_auto}_{basket_section_name}_{item}"
                # 키 존재 여부만 확인하고 할당 (원본)
                if key in st.session_state:
                    st.session_state[key] = qty

    else: # 이중 변경 상황 - 현재 상태는 유지하고 prev_prev만 업데이트
        st.session_state.final_selected_vehicle = selected_vehicle_logic
        st.session_state.prev_final_selected_vehicle = selected_vehicle_logic
else: # 차량 변경 없음
    st.session_state.final_selected_vehicle = selected_vehicle_logic
    # 이전 상태 추적을 위해 prev_prev 업데이트는 계속 필요
    if prev_vehicle != prev_prev_vehicle_state:
        st.session_state.prev_final_selected_vehicle = prev_vehicle
# =============================================================================


# --- 탭 2: 물품 선택 (UI 원복 없음 - 개선된 상태 유지) ---
# (이전 UI 개선 버전의 Tab 2 코드 유지)
with tab2:
    st.header("📋 이사 품목 선택 및 수량 입력")
    st.caption(f"현재 선택된 기본 이사 유형: **{st.session_state.base_move_type}**")
    # 총 부피/무게 및 추천 차량 계산 (계산 모듈 호출)
    st.session_state.total_volume, st.session_state.total_weight = calculations.calculate_total_volume_weight(st.session_state.to_dict(), st.session_state.base_move_type)
    st.session_state.recommended_vehicle_auto, remaining_space = calculations.recommend_vehicle(st.session_state.total_volume, st.session_state.total_weight)

    with st.container(border=True):
        st.subheader("품목별 수량 입력")
        # 현재 이사 유형에 맞는 품목 정의 가져오기
        item_category_to_display = data.item_definitions.get(st.session_state.base_move_type, {})
        basket_section_name_check = "포장 자재 📦" # 바구니 섹션 이름

        # 품목 섹션별로 expander 생성
        for section, item_list in item_category_to_display.items():
            if section == "폐기 처리 품목 🗑️": continue # 폐기 품목 섹션은 건너뜀
            # 유효한(data.items에 정의된) 품목만 필터링
            valid_items_in_section = [item for item in item_list if item in data.items]
            if not valid_items_in_section: continue # 유효 품목 없으면 섹션 건너뜀

            expander_label = f"{section} 품목 선택"
            expanded_default = (section == basket_section_name_check) # 바구니 섹션은 기본 펼침
            with st.expander(expander_label, expanded=expanded_default):
                # 바구니 섹션일 경우, 선택된 차량 기준 기본값 안내 표시
                if section == basket_section_name_check:
                    selected_truck_tab2 = st.session_state.get("final_selected_vehicle")
                    if selected_truck_tab2 and selected_truck_tab2 in data.default_basket_quantities:
                        defaults = data.default_basket_quantities[selected_truck_tab2]
                        basket_qty = defaults.get('바구니', 0); med_basket_qty = defaults.get('중자바구니', 0); book_qty = defaults.get('책바구니', 0)
                        # 중박스가 별도로 있으면 중박스 우선, 없으면 중자바구니 사용 (data.py 정의 따라감)
                        med_box_qty = defaults.get('중박스', med_basket_qty)
                        st.info(f"💡 **{selected_truck_tab2}** 추천 기본값: 바구니 {basket_qty}개, 중박스 {med_box_qty}개, 책 {book_qty}개 (현재 값이며, 직접 수정 가능합니다)")
                    else:
                        st.info("💡 비용 탭에서 차량 선택 시 추천 기본 바구니 개수가 여기에 표시됩니다.")

                # 품목 입력 UI (2열 레이아웃)
                num_columns = 2; cols = st.columns(num_columns)
                num_items = len(valid_items_in_section)
                items_per_col = math.ceil(num_items / len(cols)) if num_items > 0 and len(cols) > 0 else 1
                for idx, item in enumerate(valid_items_in_section):
                    col_index = idx // items_per_col if items_per_col > 0 else 0
                    if col_index < len(cols):
                        with cols[col_index]:
                            unit = "칸" if item == "장롱" else "개"
                            key_prefix = "qty"
                            # session_state 키 생성 (이사유형_섹션_품목명)
                            widget_key = f"{key_prefix}_{st.session_state.base_move_type}_{section}_{item}"
                            # 키가 없으면 0으로 초기화 (initialize_session_state에서 이미 처리되었어야 함)
                            if widget_key not in st.session_state: st.session_state[widget_key] = 0
                            # 숫자 입력 위젯 생성
                            try:
                                st.number_input(label=f"{item}", min_value=0, step=1, key=widget_key, help=f"{item}의 수량 ({unit})")
                            except Exception as e: # 위젯 생성 오류 시 처리
                                st.error(f"표시 오류: {item}. 상태 초기화.")
                                st.session_state[widget_key] = 0 # 오류 시 0으로 리셋
                                # 리셋 후 다시 위젯 생성 시도
                                st.number_input(label=f"{item}", min_value=0, step=1, key=widget_key, help=f"{item}의 수량 ({unit})")

    st.write("---")
    # 선택된 품목 및 예상 물량 요약 표시
    with st.container(border=True):
        st.subheader("📊 현재 선택된 품목 및 예상 물량")
        move_selection_display = {} # 표시할 품목 (수량 > 0)
        processed_items_summary_move = set()
        original_item_defs_move = data.item_definitions.get(st.session_state.base_move_type, {})

        # session_state에서 수량이 0보다 큰 품목 찾기
        if isinstance(original_item_defs_move, dict):
            for section_move, item_list_move in original_item_defs_move.items():
                if section_move == "폐기 처리 품목 🗑️": continue
                if isinstance(item_list_move, list):
                    for item_move in item_list_move:
                        if item_move in processed_items_summary_move: continue
                        widget_key_move = f"qty_{st.session_state.base_move_type}_{section_move}_{item_move}"
                        if widget_key_move in st.session_state:
                            qty = 0; raw_qty_m = st.session_state.get(widget_key_move)
                            try: qty = int(raw_qty_m) if raw_qty_m is not None else 0
                            except Exception: qty = 0
                            if qty > 0 and item_move in data.items: # 수량 > 0 이고 유효한 품목일 때만
                                unit_move = "칸" if item_move == "장롱" else "개"
                                move_selection_display[item_move] = (qty, unit_move)
                        processed_items_summary_move.add(item_move)

        # 선택된 품목 목록 및 예상 물량/추천 차량 표시
        if move_selection_display:
            st.markdown("**선택 품목 목록:**")
            cols_disp_m = st.columns(2)
            item_list_disp_m = list(move_selection_display.items())
            items_per_col_disp_m = math.ceil(len(item_list_disp_m)/len(cols_disp_m)) if len(item_list_disp_m)>0 and len(cols_disp_m)>0 else 1
            for i, (item_disp, (qty_disp, unit_disp)) in enumerate(item_list_disp_m):
                col_idx_disp = i // items_per_col_disp_m if items_per_col_disp_m > 0 else 0
                if col_idx_disp < len(cols_disp_m):
                    with cols_disp_m[col_idx_disp]:
                         st.write(f"- {item_disp}: {qty_disp} {unit_disp}")

            st.write("")
            st.markdown("**예상 물량 및 추천 차량:**")
            st.info(f"📊 **총 부피:** {st.session_state.total_volume:.2f} m³ | **총 무게:** {st.session_state.total_weight:.2f} kg")

            recommended_vehicle_display = st.session_state.get('recommended_vehicle_auto')
            final_vehicle_tab2_display = st.session_state.get('final_selected_vehicle') # Tab 3에서 최종 선택된 차량

            # 추천 차량 표시 로직
            if recommended_vehicle_display and "초과" not in recommended_vehicle_display:
                rec_text = f"✅ 추천 차량: **{recommended_vehicle_display}** ({remaining_space:.1f}% 여유 공간 예상)"
                spec = data.vehicle_specs.get(recommended_vehicle_display)
                if spec: rec_text += f" (최대: {spec['capacity']}m³, {spec['weight_capacity']:,}kg)"
                st.success(rec_text)
                # 추천 차량과 실제 선택 차량이 다를 경우 경고
                if final_vehicle_tab2_display and final_vehicle_tab2_display != recommended_vehicle_display:
                     st.warning(f"⚠️ 현재 비용계산 탭에서 **{final_vehicle_tab2_display}** 차량이 수동 선택되어 있습니다.")
                elif not final_vehicle_tab2_display: # 아직 차량 선택 전
                     st.info("💡 비용계산 탭에서 차량을 최종 선택해주세요.")
            elif recommended_vehicle_display and "초과" in recommended_vehicle_display: # 물량 초과
                st.error(f"❌ 추천 차량: **{recommended_vehicle_display}**. 선택된 물량이 너무 많습니다. 물량을 줄이거나 더 큰 차량을 수동 선택해야 합니다.")
                if final_vehicle_tab2_display: st.info(f"ℹ️ 현재 비용계산 탭에서 **{final_vehicle_tab2_display}** 차량이 수동 선택되어 있습니다.")
            else: # 자동 추천 불가
                if st.session_state.total_volume > 0 or st.session_state.total_weight > 0:
                     st.warning("⚠️ 추천 차량: 자동 추천 불가. 비용계산 탭에서 차량을 수동 선택해주세요.")
                else: # 물품 미선택
                     st.info("ℹ️ 이사할 품목이 없습니다. 품목을 선택해주세요.")
                if final_vehicle_tab2_display: st.info(f"ℹ️ 현재 비용계산 탭에서 **{final_vehicle_tab2_display}** 차량이 수동 선택되어 있습니다.")
        else: # 선택된 품목 없음
             st.info("ℹ️ 선택된 이사 품목이 없습니다. 위에서 품목을 선택해주세요.")


# --- 탭 3: 견적 및 비용 (UI 원복 없음, 이사 유형 선택만 추가) ---
with tab3:
    st.header("💰 계산 및 옵션 ") # 헤더 원복

    # --- === 이사 유형 선택 위젯 (탭 3) === ---
    st.subheader("🏢 이사 유형 확인/변경")
    try: current_index_tab3 = MOVE_TYPE_OPTIONS.index(st.session_state.base_move_type)
    except ValueError: current_index_tab3 = 0
    st.radio( # 라벨 원복
        "기본 이사 유형:",
        options=MOVE_TYPE_OPTIONS, index=current_index_tab3, horizontal=True,
        key="base_move_type_widget_tab3", on_change=sync_move_type, args=("base_move_type_widget_tab3",)
    )
    st.divider() # 구분선 원복
    # --- ============================== ---

    with st.container(border=True): # 차량 선택 컨테이너 유지
        st.subheader("🚚 차량 선택")
        col_v1_widget, col_v2_widget = st.columns([1, 2]) # 레이아웃 비율 유지
        with col_v1_widget:
            st.radio("차량 선택 방식:", ["자동 추천 차량 사용", "수동으로 차량 선택"], key="vehicle_select_radio", help="자동 추천을 사용하거나, 목록에서 직접 차량을 선택합니다.")
        with col_v2_widget:
            # 필요한 상태 변수 가져오기
            final_vehicle_widget = st.session_state.get('final_selected_vehicle') # 현재 최종 선택된 차량
            use_auto_widget = st.session_state.get('vehicle_select_radio') == "자동 추천 차량 사용"
            recommended_vehicle_auto_widget = st.session_state.get('recommended_vehicle_auto') # 자동 추천된 차량
            current_move_type_widget = st.session_state.base_move_type
            vehicle_prices_options_widget = data.vehicle_prices.get(current_move_type_widget, {})
            available_trucks_widget = sorted(vehicle_prices_options_widget.keys(), key=lambda x: data.vehicle_specs.get(x, {}).get("capacity", 0))
            valid_auto_widget = (recommended_vehicle_auto_widget and "초과" not in recommended_vehicle_auto_widget and recommended_vehicle_auto_widget in available_trucks_widget)

            # 자동 추천 사용 시 UI
            if use_auto_widget:
                if valid_auto_widget and final_vehicle_widget: # 자동 추천 가능하고 최종 차량이 선택되었으면
                    st.success(f"✅ 자동 선택됨: **{final_vehicle_widget}**")
                    spec = data.vehicle_specs.get(final_vehicle_widget)
                    if spec:
                         st.caption(f"선택차량 최대 용량: {spec['capacity']}m³, {spec['weight_capacity']:,}kg")
                         st.caption(f"현재 이사짐 예상: {st.session_state.get('total_volume',0.0):.2f}m³, {st.session_state.get('total_weight',0.0):.2f}kg")
                else: # 자동 추천 불가 시
                    error_msg = "⚠️ 자동 추천 불가: "
                    if recommended_vehicle_auto_widget and "초과" in recommended_vehicle_auto_widget:
                        error_msg += f"물량 초과({recommended_vehicle_auto_widget}). 수동 선택 필요."
                    elif not recommended_vehicle_auto_widget and (st.session_state.get('total_volume', 0.0) > 0 or st.session_state.get('total_weight', 0.0) > 0):
                        error_msg += "계산/정보 부족. 수동 선택 필요."
                    else:
                        error_msg += "물품 미선택 또는 정보 부족. 수동 선택 필요."
                    st.error(error_msg)
                    # 자동 추천 불가 시에도 수동 선택 드롭다운 표시 (아래 로직에서 처리)

            # 수동 선택 사용 시 또는 자동 추천 불가 시 드롭다운 표시
            if not use_auto_widget or (use_auto_widget and not valid_auto_widget):
                if not available_trucks_widget:
                    st.error("❌ 선택 가능한 차량 정보가 없습니다.")
                else:
                    # 수동 선택 드롭다운 기본값 설정
                    default_manual_vehicle_widget = None
                    if valid_auto_widget: # 자동 추천이 유효하면 그걸 기본값으로
                        default_manual_vehicle_widget = recommended_vehicle_auto_widget
                    elif available_trucks_widget: # 아니면 목록 첫번째 차량
                        default_manual_vehicle_widget = available_trucks_widget[0]

                    # 현재 수동 선택 값 가져오기
                    current_manual_selection_widget = st.session_state.get("manual_vehicle_select_value")

                    # Selectbox 인덱스 계산
                    current_index_widget = 0
                    try:
                        if current_manual_selection_widget in available_trucks_widget:
                            current_index_widget = available_trucks_widget.index(current_manual_selection_widget)
                        elif default_manual_vehicle_widget in available_trucks_widget:
                             current_index_widget = available_trucks_widget.index(default_manual_vehicle_widget)
                             # 기본값으로 session_state 업데이트 (선택 전 상태 반영)
                             st.session_state.manual_vehicle_select_value = default_manual_vehicle_widget
                        elif available_trucks_widget: # 둘 다 없으면 0번 인덱스
                             current_index_widget = 0
                             st.session_state.manual_vehicle_select_value = available_trucks_widget[0]
                    except ValueError: # 인덱스 찾기 실패 시 0번
                        current_index_widget = 0
                        if available_trucks_widget:
                            st.session_state.manual_vehicle_select_value = available_trucks_widget[0]

                    # Selectbox 위젯 생성
                    st.selectbox("차량 직접 선택:", available_trucks_widget, index=current_index_widget, key="manual_vehicle_select_value")

                    # 수동 선택된 차량 정보 표시
                    manual_selected_display = st.session_state.get('manual_vehicle_select_value')
                    if manual_selected_display:
                        st.info(f"ℹ️ 수동 선택됨: **{manual_selected_display}**")
                        spec = data.vehicle_specs.get(manual_selected_display)
                        if spec:
                            st.caption(f"선택차량 최대 용량: {spec['capacity']}m³, {spec['weight_capacity']:,}kg")
                            st.caption(f"현재 이사짐 예상: {st.session_state.get('total_volume',0.0):.2f}m³, {st.session_state.get('total_weight',0.0):.2f}kg")

    st.divider() # 구분선 원복
    with st.container(border=True): # 작업 옵션 컨테이너 유지
        st.subheader("🛠️ 작업 조건 및 추가 옵션") # 서브헤더 원복
        # 스카이 작업 시간 입력 UI
        sky_from = st.session_state.get('from_method')=="스카이 🏗️"
        sky_to = st.session_state.get('to_method')=="스카이 🏗️"
        if sky_from or sky_to:
            st.warning("스카이 작업 선택됨 - 시간 입력 필요", icon="🏗️")
            cols_sky = st.columns(2)
            with cols_sky[0]:
                if sky_from: st.number_input("출발 스카이 시간(h)", min_value=1, step=1, key="sky_hours_from")
                else: st.empty() # 출발지 스카이 아니면 공간 비움
            with cols_sky[1]:
                if sky_to: st.number_input("도착 스카이 시간(h)", min_value=1, step=1, key="sky_hours_final")
                else: st.empty() # 도착지 스카이 아니면 공간 비움
            st.write("") # 스카이 옵션 후 공백

        # 추가 인원 입력 UI
        col_add1, col_add2 = st.columns(2)
        with col_add1: st.number_input("추가 남성 인원 👨", min_value=0, step=1, key="add_men", help="기본 인원 외 추가로 필요한 남성 작업자 수")
        with col_add2: st.number_input("추가 여성 인원 👩", min_value=0, step=1, key="add_women", help="기본 인원 외 추가로 필요한 여성 작업자 수")
        st.write("") # 추가 인원 후 공백

        # 실제 투입 차량 입력 UI
        st.subheader("🚚 실제 투입 차량") # subheader 원복
        dispatched_cols = st.columns(4)
        with dispatched_cols[0]: st.number_input("1톤", min_value=0, step=1, key="dispatched_1t")
        with dispatched_cols[1]: st.number_input("2.5톤", min_value=0, step=1, key="dispatched_2_5t")
        with dispatched_cols[2]: st.number_input("3.5톤", min_value=0, step=1, key="dispatched_3_5t")
        with dispatched_cols[3]: st.number_input("5톤", min_value=0, step=1, key="dispatched_5t")
        st.caption("견적 계산과 별개로, 실제 현장에 투입될 차량 대수를 입력합니다.") # 캡션 원복
        st.write("") # 실제 투입 차량 후 공백

        # 기본 여성 인원 제외 옵션 UI
        base_w=0; remove_opt=False; final_vehicle_for_options = st.session_state.get('final_selected_vehicle'); current_move_type_options = st.session_state.base_move_type
        vehicle_prices_options_display = data.vehicle_prices.get(current_move_type_options, {})
        # 선택된 차량 정보가 있고, 해당 차량 가격 정보가 있을 때만 기본 여성 인원 확인
        if final_vehicle_for_options and final_vehicle_for_options in vehicle_prices_options_display:
             base_info = vehicle_prices_options_display.get(final_vehicle_for_options, {})
             base_w = base_info.get('housewife', 0) # 기본 여성 인원 수 가져오기
             if base_w > 0: remove_opt = True # 기본 여성 인원이 있으면 제외 옵션 표시

        if remove_opt:
            cost_per_person = getattr(data, 'ADDITIONAL_PERSON_COST', 200000) # data 모듈에서 인건비 가져오기
            discount_amount = cost_per_person * base_w
            st.checkbox(f"기본 여성({base_w}명) 제외 (비용 할인: -{discount_amount:,}원)", key="remove_base_housewife")
        else: # 제외 옵션 표시 조건 아닐 때
            # 상태 강제 초기화 (옵션이 사라졌을 때 이전 상태가 남는 것 방지)
            if 'remove_base_housewife' in st.session_state:
                 st.session_state.remove_base_housewife = False

        # 폐기물 처리 옵션 UI
        col_waste1, col_waste2 = st.columns([1, 2]) # 컬럼 비율 유지
        with col_waste1:
            st.checkbox("폐기물 처리 필요 🗑️", key="has_waste_check", help="톤 단위 직접 입력 방식입니다.") # 라벨/help 원복
        with col_waste2:
            if st.session_state.get('has_waste_check'): # 폐기물 처리 선택 시
                st.number_input("폐기물 양 (톤)", min_value=0.5, max_value=10.0, step=0.5, key="waste_tons_input", format="%.1f")
                waste_cost_per_ton = getattr(data, 'WASTE_DISPOSAL_COST_PER_TON', 300000) # 톤당 비용 가져오기
                st.caption(f"💡 1톤당 {waste_cost_per_ton:,}원 추가 비용 발생") # 아이콘 추가 또는 제거
            else: # 미선택 시 공간 비움
                st.empty()

        # 날짜 할증 옵션 UI
        st.write("📅 **날짜 유형 선택** (중복 가능, 해당 시 할증)") # 라벨 원복
        date_options = ["이사많은날 🏠", "손없는날 ✋", "월말 📅", "공휴일 🎉", "금요일 📅"]
        date_keys = [f"date_opt_{i}_widget" for i in range(len(date_options))]
        cols_date = st.columns(len(date_options)) # 옵션 개수만큼 컬럼 생성
        for i, option in enumerate(date_options):
            with cols_date[i]:
                st.checkbox(option, key=date_keys[i])

    st.divider() # 구분선 원복
    with st.container(border=True): # 비용 조정 컨테이너 유지
        st.subheader("💰 비용 조정 및 계약금") # 서브헤더 원복
        col_adj1, col_adj2, col_adj3 = st.columns(3)
        with col_adj1:
            st.number_input("📝 계약금", min_value=0, step=10000, key="deposit_amount", format="%d", help="고객에게 받을 계약금 입력") # 라벨 원복
        with col_adj2:
            st.number_input("💰 추가 조정 (+/-)", step=10000, key="adjustment_amount", help="견적 금액 외 추가 할증(+) 또는 할인(-) 금액 입력", format="%d") # 라벨 원복
        with col_adj3:
            st.number_input("🪜 사다리 추가요금", min_value=0, step=10000, key="regional_ladder_surcharge", format="%d", help="추가되는 사다리차 비용 (지방 등)") # 도움말 수정

    # 차량 변경 시 자동 바구니 업데이트 후 rerun (UI 즉시 반영 위함)
    if vehicle_changed_flag:
        st.rerun()

    st.divider() # 구분선 원복
    st.header("💵 최종 견적 결과") # 헤더 원복

    # 비용 계산 및 결과 표시
    total_cost = 0; cost_items = []; personnel_info = {}; excel_data = None
    final_selected_vehicle_calc = st.session_state.get('final_selected_vehicle')

    # 최종 차량이 선택되었을 때만 계산 및 결과 표시
    if final_selected_vehicle_calc:
        # 비용 계산 함수 호출
        total_cost, cost_items, personnel_info = calculations.calculate_total_moving_cost(st.session_state.to_dict())

        # 숫자 타입 변환 및 오류 처리
        total_cost_num = total_cost if isinstance(total_cost, (int, float)) else 0
        try: deposit_amount_num = int(st.session_state.get('deposit_amount', 0))
        except (ValueError, TypeError): deposit_amount_num = 0
        remaining_balance_num = total_cost_num - deposit_amount_num

        # --- 비용 요약 (st.metric -> st.subheader 원복) ---
        st.subheader(f"💰 총 견적 비용: {total_cost_num:,.0f} 원")
        st.subheader(f"➖ 계약금: {deposit_amount_num:,.0f} 원")
        st.subheader(f"➡️ 잔금 (총 비용 - 계약금): {remaining_balance_num:,.0f} 원")
        # ---------------------------------------------
        st.write("") # 공백 제거 또는 유지

        # 비용 상세 내역 (expander 제거, UI 원복)
        st.subheader("📊 비용 상세 내역") # 서브헤더 원복
        # 계산 오류 항목 확인
        error_item = next((item for item in cost_items if isinstance(item, (list, tuple)) and len(item)>0 and str(item[0]) == "오류"), None)
        if error_item:
            st.error(f"비용 계산 오류: {error_item[2]}") # 오류 메시지 표시
        elif cost_items: # 정상 계산 시 데이터프레임 표시
            df_display = pd.DataFrame(cost_items, columns=["항목", "금액", "비고"])
            # 데이터프레임 스타일링 (금액 오른쪽 정렬, 천단위 쉼표)
            st.dataframe(
                df_display.style.format({"금액": "{:,.0f}"})
                            .set_properties(**{'text-align':'right'}, subset=['금액'])
                            .set_properties(**{'text-align':'left'}, subset=['항목','비고']),
                use_container_width=True,
                hide_index=True
            )
        else: # 계산 결과 없으면
            st.info("ℹ️ 계산된 비용 항목이 없습니다.")

        st.write("") # 공백 제거 또는 유지

        # 고객 요구사항 표시 (내용 있을 때만)
        special_notes_display = st.session_state.get('special_notes')
        if special_notes_display and special_notes_display.strip(): # 고객 요구사항 위치/스타일 원복
             st.subheader("📝 고객요구사항")
             st.info(special_notes_display) # info 박스로 표시

        # 이사 정보 요약 (st.text() 사용 유지)
        st.subheader("📋 이사 정보 요약")
        summary_generated = False # 요약 생성 성공 플래그
        try:
            # 요약 엑셀 데이터 생성 시도 (메모리에서)
            # generate_excel 함수는 pdf_generator 또는 excel_summary_generator 모듈에 있어야 함
            # 여기서는 excel_summary_generator 모듈 사용 가정
            import excel_summary_generator # 모듈 임포트 확인
            # waste_info 계산 추가
            waste_info = {
                'total_waste_tons': st.session_state.get('waste_tons_input', 0.0) if st.session_state.get('has_waste_check') else 0.0,
                'total_waste_cost': 0
            }
            if waste_info['total_waste_tons'] > 0:
                 waste_cost_per_ton_summary = getattr(data, 'WASTE_DISPOSAL_COST_PER_TON', 300000)
                 waste_info['total_waste_cost'] = waste_info['total_waste_tons'] * waste_cost_per_ton_summary

            # vehicle_info 계산 추가
            vehicle_info_summary = {
                'recommended_vehicles': {final_selected_vehicle_calc: 1} if final_selected_vehicle_calc else {} # 단순화된 형태
            }

            excel_data_summary = excel_summary_generator.generate_summary_excel(
                st.session_state.to_dict(),
                cost_items,
                personnel_info,
                vehicle_info_summary, # 추가
                waste_info          # 추가
            )

            if excel_data_summary:
                excel_buffer = io.BytesIO(excel_data_summary)
                xls = pd.ExcelFile(excel_buffer)
                # '견적 정보' 시트 파싱 (헤더 없이)
                df_info = xls.parse("견적 정보", header=None)
                # '비용 내역 및 요약' 시트 파싱 (헤더 없이)
                df_cost = xls.parse("비용 내역 및 요약", header=None)

                info_dict = {} # 견적 정보 시트 내용을 딕셔너리로 변환
                if not df_info.empty and len(df_info.columns) > 1:
                     info_dict = dict(zip(df_info[0].astype(str), df_info[1].astype(str)))

                # --- 요약 정보 포매팅 함수 ---
                def format_money_kor(amount):
                    """금액을 'X만원' 또는 'X원' 형태로 변환"""
                    try:
                         # 문자열에서 숫자만 추출 (쉼표, ' 원' 등 제거)
                         amount_str = str(amount).replace(",", "").split()[0]
                         amount_float = float(amount_str)
                         amount_int = int(amount_float)
                    except: return "금액오류"
                    if amount_int == 0: return "0원"
                    elif amount_int >= 10000: return f"{amount_int // 10000}만원"
                    else: return f"{amount_int}원"

                def format_address(address_string):
                    """주소 문자열 정리 (공백 제거, nan 처리)"""
                    if not isinstance(address_string, str) or not address_string.strip() or address_string.lower() == 'nan':
                         return "" # 유효하지 않으면 빈 문자열 반환
                    return address_string.strip()

                def get_cost_value_abbr(keyword, abbr, cost_df):
                    """비용 데이터프레임에서 특정 키워드로 시작하는 항목의 금액을 축약형으로 반환"""
                    if cost_df.empty or len(cost_df.columns) < 2: return f"{abbr} 정보 없음"
                    for i in range(len(cost_df)):
                        cell_value = cost_df.iloc[i, 0] # 항목 셀 값
                        if pd.notna(cell_value) and str(cell_value).strip().startswith(keyword):
                             formatted_amount = format_money_kor(cost_df.iloc[i, 1]) # 금액 포매팅
                             return f"{abbr} {formatted_amount}" # 축약 문자 + 포매팅된 금액
                    return f"{abbr} 정보 없음" # 해당 항목 못 찾음

                def format_work_method(method_str):
                    """작업 방법을 한 글자 축약형으로 변환"""
                    method_str = str(method_str).strip()
                    if "사다리차" in method_str: return "사"
                    elif "승강기" in method_str: return "승"
                    elif "계단" in method_str: return "계"
                    elif "스카이" in method_str: return "스카이"
                    else: return "?" # 알 수 없음

                # --- 요약 정보 추출 및 포매팅 ---
                from_address_full = format_address(info_dict.get("출발지 주소", "")) # '출발지' -> '출발지 주소'
                to_address_full = format_address(info_dict.get("도착지 주소", ""))   # '도착지' -> '도착지 주소'
                phone = info_dict.get("연락처", "") # '고객 연락처' -> '연락처'
                work_from_raw = info_dict.get("출발지 작업 방법", "") # '출발 작업' -> '출발지 작업 방법'
                work_to_raw = info_dict.get("도착지 작업 방법", "")   # '도착 작업' -> '도착지 작업 방법'

                # 실제 투입 차량 정보 반영
                dispatched_vehicles_summary = []
                if int(st.session_state.get('dispatched_1t', 0)) > 0: dispatched_vehicles_summary.append(f"1t:{st.session_state['dispatched_1t']}")
                if int(st.session_state.get('dispatched_2_5t', 0)) > 0: dispatched_vehicles_summary.append(f"2.5t:{st.session_state['dispatched_2_5t']}")
                if int(st.session_state.get('dispatched_3_5t', 0)) > 0: dispatched_vehicles_summary.append(f"3.5t:{st.session_state['dispatched_3_5t']}")
                if int(st.session_state.get('dispatched_5t', 0)) > 0: dispatched_vehicles_summary.append(f"5t:{st.session_state['dispatched_5t']}")
                vehicle_type = "/".join(dispatched_vehicles_summary) if dispatched_vehicles_summary else (final_selected_vehicle_calc if final_selected_vehicle_calc else "차량정보없음")

                special_note = format_address(state_data.get('special_notes', '')) # 고객 요구사항은 state_data에서 직접 가져오기

                # 인원 정보 (계산된 결과 사용)
                p_info_calc = personnel_info
                final_men_calc = p_info_calc.get('final_men', 0)
                final_women_calc = p_info_calc.get('final_women', 0)
                personnel_formatted = f"{final_men_calc}+{final_women_calc}" if final_women_calc > 0 else f"{final_men_calc}"

                # 바구니 정보 (session_state에서 직접 가져오기)
                basket_section_name = "포장 자재 📦"
                current_move_type_summary = st.session_state.base_move_type
                key_basket = f"qty_{current_move_type_summary}_{basket_section_name}_바구니"
                key_med_basket = f"qty_{current_move_type_summary}_{basket_section_name}_중자바구니" # 중자바구니 키
                key_med_box = f"qty_{current_move_type_summary}_{basket_section_name}_중박스" # 중박스 키
                key_book_basket = f"qty_{current_move_type_summary}_{basket_section_name}_책바구니"

                try: qty_basket = int(st.session_state.get(key_basket, 0))
                except: qty_basket = 0
                try: qty_medium_basket = int(st.session_state.get(key_med_basket, 0)) # 중자바구니 수량
                except: qty_medium_basket = 0
                try: qty_medium_box = int(st.session_state.get(key_med_box, 0)) # 중박스 수량
                except: qty_medium_box = 0
                try: qty_book_basket = int(st.session_state.get(key_book_basket, 0))
                except: qty_book_basket = 0

                # 중박스, 중자바구니 중 수량이 있는 것을 '중'으로 표시
                qty_medium_display = qty_medium_box if qty_medium_box > 0 else qty_medium_basket

                basket_formatted = f"바{qty_basket} 중{qty_medium_display} 책{qty_book_basket}" if (qty_basket + qty_medium_display + qty_book_basket > 0) else ""

                # 계약금/잔금 정보 (비용 DF에서 추출)
                contract_fee_str = get_cost_value_abbr("계약금 (-)", "계", df_cost)
                remaining_fee_str = get_cost_value_abbr("잔금 (VAT 별도)", "잔", df_cost)

                # 작업 방식 축약
                work_from_abbr = format_work_method(work_from_raw)
                work_to_abbr = format_work_method(work_to_raw)
                work_method_formatted = f"출{work_from_abbr}도{work_to_abbr}"

                # --- 최종 요약 정보 출력 (st.text 사용) ---
                st.text(f"{from_address_full} - {to_address_full}")
                if phone and phone != '-': st.text(f"{phone}")
                st.text(f"{vehicle_type} | {personnel_formatted}")
                if basket_formatted: st.text(basket_formatted)
                st.text(work_method_formatted)
                st.text(f"{contract_fee_str} / {remaining_fee_str}")
                if special_note and special_note.strip() and special_note.strip().lower() != 'nan' and special_note != '-':
                    st.text(f"요청: {special_note.strip()}") # 고객요구사항 앞에 '요청:' 추가

                summary_generated = True # 요약 생성 성공
            else:
                st.warning("⚠️ 요약 정보 생성 실패 (엑셀 데이터 생성 오류)")
        except Exception as e:
            st.error(f"❌ 요약 정보 생성 중 오류 발생: {e}")
            traceback.print_exc()

        if not summary_generated and final_selected_vehicle_calc:
             st.info("ℹ️ 요약 정보를 표시할 수 없습니다.") # 요약 생성 실패 시 메시지

        st.divider() # 구분선 원복

        # 다운로드 섹션 UI 원복 (버튼 3개 버전, 마지막 버튼은 숨김 처리됨)
        st.subheader("📄 견적서 파일 다운로드")
        # 비용 계산 오류 여부 확인
        has_cost_error = any(isinstance(item, (list, tuple)) and len(item)>0 and str(item[0]) == "오류" for item in cost_items) if cost_items else False
        # 최종 차량 선택 및 비용 오류 없을 때만 PDF 생성 가능
        can_gen_pdf = bool(final_selected_vehicle_calc) and not has_cost_error
        cols_dl = st.columns(3) # 3열 레이아웃 유지

        with cols_dl[0]: # Final 견적서 (Excel)
             st.markdown("**① Final 견적서 (Excel)**")
             # Final 견적서 생성 버튼
             if st.button("📄 생성: Final 견적서"):
                # excel_filler 모듈 호출하여 템플릿 채우기
                filled_excel_data = excel_filler.fill_final_excel_template(
                    st.session_state.to_dict(), cost_items, total_cost, personnel_info
                )
                if filled_excel_data:
                    st.session_state['final_excel_data'] = filled_excel_data # 생성된 데이터 세션에 저장
                    st.success("✅ 생성 완료!")
                else: # 생성 실패 시
                    if 'final_excel_data' in st.session_state: del st.session_state['final_excel_data'] # 기존 데이터 삭제
                    st.error("❌ 생성 실패.")

             # 생성된 데이터가 있으면 다운로드 버튼 표시
             if st.session_state.get('final_excel_data'):
                 ph_part_final = utils.extract_phone_number_part(st.session_state.customer_phone, length=4, default="0000")
                 now_final_str = datetime.now(pytz.timezone("Asia/Seoul")).strftime('%y%m%d') if pytz else datetime.now().strftime('%y%m%d')
                 final_excel_fname = f"{ph_part_final}_{now_final_str}_Final견적서.xlsx"
                 st.download_button(
                     label="📥 다운로드 (Excel)",
                     data=st.session_state['final_excel_data'],
                     file_name=final_excel_fname,
                     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     key='final_excel_download_button'
                 )
             else: # 생성 전 안내
                 st.caption("생성 버튼을 눌러주세요.")

        with cols_dl[1]: # 고객용 견적서 (PDF)
            st.markdown("**② 고객용 견적서 (PDF)**")
            if can_gen_pdf: # PDF 생성 가능 조건 충족 시
                # PDF 생성 버튼
                if st.button("📄 생성: PDF 견적서"):
                    # 최신 상태로 비용 재계산 (혹시 모를 변경사항 반영)
                    latest_total_cost_pdf, latest_cost_items_pdf, latest_personnel_info_pdf = calculations.calculate_total_moving_cost(st.session_state.to_dict())
                    # PDF 생성 함수 호출
                    pdf_data_bytes = pdf_generator.generate_pdf(
                        st.session_state.to_dict(), latest_cost_items_pdf, latest_total_cost_pdf, latest_personnel_info_pdf
                    )
                    st.session_state['pdf_data_customer'] = pdf_data_bytes # 생성된 PDF 데이터 세션에 저장
                    if pdf_data_bytes: st.success("✅ 생성 완료!")
                    else: st.error("❌ 생성 실패.")

                # 생성된 PDF 데이터가 있으면 다운로드 버튼 표시
                if st.session_state.get('pdf_data_customer'):
                    ph_part_pdf = utils.extract_phone_number_part(st.session_state.customer_phone, length=4, default="0000")
                    now_pdf_str = datetime.now(pytz.timezone("Asia/Seoul")).strftime('%y%m%d_%H%M') if pytz else datetime.now().strftime('%y%m%d_%H%M')
                    fname_pdf = f"{ph_part_pdf}_{now_pdf_str}_이삿날견적서.pdf"
                    st.download_button(
                        label="📥 다운로드 (PDF)",
                        data=st.session_state['pdf_data_customer'],
                        file_name=fname_pdf,
                        mime='application/pdf',
                        key='pdf_download_button'
                    )
                elif not st.session_state.get('pdf_data_customer'): # 생성 전 안내
                    st.caption("생성 버튼을 눌러주세요.")
            else: # PDF 생성 불가 시 안내
                st.caption("PDF 생성 불가 (차량 미선택 또는 비용 오류)")

        with cols_dl[2]: # 종합 견적서 버튼 숨김 유지 (필요 시 여기에 UI 추가)
            st.empty() # 공간 비움

    else: # 차량 미선택 시 안내 원복
        st.warning("⚠️ **차량을 먼저 선택해주세요.** 비용 계산, 요약 정보 표시 및 다운로드는 차량 선택 후 가능합니다.")
