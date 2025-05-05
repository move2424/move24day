# app.py (UI/자동로드 원복, GDrive 로드 오류 수정, 상태 업데이트 오류(StreamlitAPIException) 수정)

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
    import excel_summary_generator # 추가 (Tab 3 요약용)
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
    # "prev_final_selected_vehicle", # 콜백 방식으로 변경 시 필요 없을 수 있음 (상태 확인 필요)
    "dispatched_1t", "dispatched_2_5t", "dispatched_3_5t", "dispatched_5t"
]
# 동적으로 생성되는 품목 키는 초기화 시 STATE_KEYS_TO_SAVE에 추가됨
# =========================================================

# --- === 콜백 함수 정의 === ---
MOVE_TYPE_OPTIONS = list(data.item_definitions.keys()) if hasattr(data, 'item_definitions') else ["가정 이사 🏠", "사무실 이사 🏢"]

def sync_move_type(widget_key):
    """이사 유형 라디오 버튼 변경 시 호출되어 상태 동기화"""
    if widget_key in st.session_state:
        new_value = st.session_state[widget_key]
        if st.session_state.base_move_type != new_value:
            st.session_state.base_move_type = new_value
            # 다른 탭의 위젯 상태도 함께 업데이트
            other_widget_key = 'base_move_type_widget_tab3' if widget_key == 'base_move_type_widget_tab1' else 'base_move_type_widget_tab1'
            if other_widget_key in st.session_state:
                 if new_value in MOVE_TYPE_OPTIONS:
                     st.session_state[other_widget_key] = new_value
                 else: # 옵션에 없는 값이면 동기화하지 않음 (오류 방지)
                     st.session_state[other_widget_key] = st.session_state.base_move_type
            # 이사 유형 변경 시 관련 상태 초기화 또는 업데이트 로직 추가 가능 (예: 추천 차량 재계산 등)
            # st.rerun() # 필요 시 UI 즉시 업데이트

def update_vehicle_and_baskets():
    """차량 선택 위젯(라디오, 셀렉트박스) 변경 시 호출되는 콜백"""
    # 1. 현재 위젯 상태를 기반으로 최종 차량 결정
    vehicle_radio = st.session_state.get('vehicle_select_radio')
    manual_vehicle = st.session_state.get('manual_vehicle_select_value')
    recommended_vehicle = st.session_state.get('recommended_vehicle_auto')
    current_move_type = st.session_state.base_move_type
    vehicle_prices_options = data.vehicle_prices.get(current_move_type, {})
    available_trucks = sorted(vehicle_prices_options.keys(), key=lambda x: data.vehicle_specs.get(x, {}).get("capacity", 0))

    new_final_vehicle = None
    is_auto_valid = (recommended_vehicle and "초과" not in recommended_vehicle and recommended_vehicle in available_trucks)

    if vehicle_radio == "자동 추천 차량 사용":
        if is_auto_valid:
            new_final_vehicle = recommended_vehicle
    elif vehicle_radio == "수동으로 차량 선택":
        if manual_vehicle in available_trucks:
            new_final_vehicle = manual_vehicle
        # 수동 선택값이 유효하지 않으면 None 유지 (또는 기본값 설정 가능)

    # 2. 최종 선택된 차량 상태 업데이트
    if st.session_state.final_selected_vehicle != new_final_vehicle:
        st.session_state.final_selected_vehicle = new_final_vehicle

        # 3. 변경된 최종 차량에 맞춰 기본 바구니 수량 업데이트
        if new_final_vehicle and new_final_vehicle in data.default_basket_quantities:
            defaults = data.default_basket_quantities[new_final_vehicle]
            basket_section_name = "포장 자재 📦"
            current_move_type_auto = st.session_state.base_move_type
            for item, qty in defaults.items():
                key = f"qty_{current_move_type_auto}_{basket_section_name}_{item}"
                # 키 유효성 및 존재 여부 확인 후 안전하게 업데이트
                if isinstance(key, str) and key.strip() and key in st.session_state:
                    st.session_state[key] = qty
                # else:
                #    print(f"Debug: Basket key '{key}' not found or invalid during update callback.")
        # else: # 선택된 차량이 없거나 기본 바구니 정보가 없는 경우
             # 필요시 기존 바구니 값 초기화 로직 추가 가능
             # pass


# --- 세션 상태 초기화 ---
def initialize_session_state():
    """세션 상태 변수들 초기화"""
    global STATE_KEYS_TO_SAVE # 전역 변수 접근 선언

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
        "remove_base_housewife": False,
        # "prev_final_selected_vehicle": None, # 콜백 방식 사용 시 필요성 재검토
        "dispatched_1t": 0, "dispatched_2_5t": 0, "dispatched_3_5t": 0, "dispatched_5t": 0,
        "gdrive_search_term": "", "gdrive_search_results": [],
        "gdrive_file_options_map": {}, "gdrive_selected_filename": None,
        "gdrive_selected_file_id": None,
        "base_move_type_widget_tab1": MOVE_TYPE_OPTIONS[0],
        "base_move_type_widget_tab3": MOVE_TYPE_OPTIONS[0],
    }
    for key, value in defaults.items():
        if key not in st.session_state: st.session_state[key] = value

    # 위젯 상태 동기화
    if st.session_state.base_move_type_widget_tab1 != st.session_state.base_move_type:
        st.session_state.base_move_type_widget_tab1 = st.session_state.base_move_type
    if st.session_state.base_move_type_widget_tab3 != st.session_state.base_move_type:
        st.session_state.base_move_type_widget_tab3 = st.session_state.base_move_type

    # 숫자 타입 변환
    int_keys = ["storage_duration", "sky_hours_from", "sky_hours_final", "add_men", "add_women",
                "deposit_amount", "adjustment_amount", "regional_ladder_surcharge",
                "dispatched_1t", "dispatched_2_5t", "dispatched_3_5t", "dispatched_5t"]
    float_keys = ["waste_tons_input"]
    allow_negative_keys = ["adjustment_amount"]
    for k in int_keys + float_keys:
        try:
            val = st.session_state.get(k, defaults.get(k))
            target_type = int if k in int_keys else float
            if val is None or (isinstance(val, str) and val.strip() == ''):
                st.session_state[k] = defaults.get(k); continue
            converted_val = target_type(val)
            if k in int_keys:
                if k in allow_negative_keys: st.session_state[k] = converted_val
                else: st.session_state[k] = max(0, converted_val)
            else: st.session_state[k] = max(0.0, converted_val)
        except (ValueError, TypeError): st.session_state[k] = defaults.get(k)
        except KeyError: st.session_state[k] = 0 if k in int_keys else 0.0

    # 동적 품목 키 초기화 및 저장 목록 업데이트
    processed_init_keys = set()
    item_keys_to_save = []
    if hasattr(data, 'item_definitions'):
        for move_type, sections in data.item_definitions.items():
            if isinstance(sections, dict):
                for section, item_list in sections.items():
                    if section == "폐기 처리 품목 🗑️": continue
                    if isinstance(item_list, list):
                        for item in item_list:
                            if item in data.items:
                                key = f"qty_{move_type}_{section}_{item}"
                                item_keys_to_save.append(key)
                                if key not in st.session_state:
                                    st.session_state[key] = 0
                                processed_init_keys.add(key)
    else: print("Warning: data.item_definitions not found during state initialization.")

    dispatched_keys = ["dispatched_1t", "dispatched_2_5t", "dispatched_3_5t", "dispatched_5t"]
    STATE_KEYS_TO_SAVE = list(set(STATE_KEYS_TO_SAVE + item_keys_to_save + dispatched_keys))

    # if 'prev_final_selected_vehicle' not in st.session_state:
    #     st.session_state['prev_final_selected_vehicle'] = st.session_state.get('final_selected_vehicle')


# ========== 상태 저장/불러오기 도우미 함수 ==========
def prepare_state_for_save():
    """세션 상태에서 지정된 키들의 값을 추출하여 저장 가능한 형태로 반환"""
    state_to_save = {}
    widget_keys_to_exclude = {'base_move_type_widget_tab1', 'base_move_type_widget_tab3'}
    # prev_final_selected_vehicle 제외하고 저장할 키 목록 생성
    actual_keys_to_save = list(set(STATE_KEYS_TO_SAVE) - widget_keys_to_exclude)
    for key in actual_keys_to_save:
        if key in st.session_state:
            value = st.session_state[key]
            if isinstance(value, date): state_to_save[key] = value.isoformat()
            elif isinstance(value, (str, int, float, bool, list, dict)) or value is None: state_to_save[key] = value
            else:
                 try: state_to_save[key] = str(value)
                 except Exception as e: print(f"Warning: Skipping non-serializable key '{key}'. Error: {e}")
    return state_to_save

def load_state_from_data(loaded_data):
    """불러온 데이터(딕셔너리)로 세션 상태를 업데이트"""
    if not isinstance(loaded_data, dict):
        st.error("잘못된 형식의 파일입니다 (딕셔너리가 아님)."); return False

    defaults_for_recovery = {
        "base_move_type": MOVE_TYPE_OPTIONS[0], "is_storage_move": False, "storage_type": data.DEFAULT_STORAGE_TYPE,
        "apply_long_distance": False, "customer_name": "", "customer_phone": "", "from_location": "",
        "to_location": "", "moving_date": date.today(), "from_floor": "", "from_method": data.METHOD_OPTIONS[0],
        "to_floor": "", "to_method": data.METHOD_OPTIONS[0], "special_notes": "", "storage_duration": 1,
        "long_distance_selector": data.long_distance_options[0], "vehicle_select_radio": "자동 추천 차량 사용",
        "manual_vehicle_select_value": None, "final_selected_vehicle": None, # "prev_final_selected_vehicle": None,
        "sky_hours_from": 1, "sky_hours_final": 1, "add_men": 0, "add_women": 0, "has_waste_check": False, "waste_tons_input": 0.5,
        "date_opt_0_widget": False, "date_opt_1_widget": False, "date_opt_2_widget": False,
        "date_opt_3_widget": False, "date_opt_4_widget": False, "deposit_amount": 0, "adjustment_amount": 0,
        "regional_ladder_surcharge": 0, "remove_base_housewife": False,
        "dispatched_1t": 0, "dispatched_2_5t": 0, "dispatched_3_5t": 0, "dispatched_5t": 0,
    }
    dynamic_keys = [key for key in STATE_KEYS_TO_SAVE if key.startswith("qty_")]
    for key in dynamic_keys:
        if key not in defaults_for_recovery: defaults_for_recovery[key] = 0

    int_keys = ["storage_duration", "sky_hours_from", "sky_hours_final", "add_men", "add_women", "deposit_amount", "adjustment_amount", "regional_ladder_surcharge", "dispatched_1t", "dispatched_2_5t", "dispatched_3_5t", "dispatched_5t"]
    float_keys = ["waste_tons_input"]
    allow_negative_keys = ["adjustment_amount"]
    bool_keys = ["is_storage_move", "apply_long_distance", "has_waste_check", "remove_base_housewife", "date_opt_0_widget", "date_opt_1_widget", "date_opt_2_widget", "date_opt_3_widget", "date_opt_4_widget"]
    load_success_count = 0; load_error_count = 0
    all_expected_keys = list(set(STATE_KEYS_TO_SAVE)) # prev_final_selected_vehicle 제외

    for key in all_expected_keys:
        if key in loaded_data:
            value = loaded_data[key]; original_value = value
            try:
                target_value = None
                if key == 'moving_date':
                    if isinstance(value, str):
                        try: target_value = datetime.fromisoformat(value).date()
                        except ValueError: target_value = defaults_for_recovery[key]; print(f"Warn: Bad date '{value}'")
                    elif isinstance(value, date): target_value = value
                    else: raise ValueError("Invalid date format")
                elif key.startswith("qty_"): converted_val = int(value) if value is not None else 0; target_value = max(0, converted_val)
                elif key in int_keys:
                    converted_val = int(value) if value is not None else 0
                    target_value = converted_val if key in allow_negative_keys else max(0, converted_val)
                elif key in float_keys: converted_val = float(value) if value is not None else 0.0; target_value = max(0.0, converted_val)
                elif key in bool_keys: target_value = bool(value)
                else: target_value = value
                if key in st.session_state: st.session_state[key] = target_value; load_success_count += 1
            except (ValueError, TypeError, KeyError) as e:
                load_error_count += 1; default_val = defaults_for_recovery.get(key)
                if key in st.session_state: st.session_state[key] = default_val
                print(f"Error loading key '{key}': {e}. Reset to default.")
    if load_error_count > 0: st.warning(f"{load_error_count}개 항목 로딩 오류 발생.")

    # GDrive 상태 초기화
    st.session_state.gdrive_search_results = []
    st.session_state.gdrive_file_options_map = {}
    st.session_state.gdrive_selected_filename = None
    st.session_state.gdrive_selected_file_id = None

    # 위젯 상태 동기화
    if 'base_move_type' in st.session_state:
        loaded_move_type = st.session_state.base_move_type
        if 'base_move_type_widget_tab1' in st.session_state: st.session_state.base_move_type_widget_tab1 = loaded_move_type
        if 'base_move_type_widget_tab3' in st.session_state: st.session_state.base_move_type_widget_tab3 = loaded_move_type

    # 로드 후 차량/바구니 상태 업데이트 콜백 명시적 호출 (선택 사항)
    # update_vehicle_and_baskets() # 로드 직후 상태 기준으로 콜백 실행

    return True
# ================================================

# --- 메인 애플리케이션 로직 ---
initialize_session_state() # 세션 상태 초기화 먼저 수행

# --- 탭 생성 ---
tab1, tab2, tab3 = st.tabs(["👤 고객 정보", "📋 물품 선택", "💰 견적 및 비용"])

# --- 탭 1: 고객 정보 ---
with tab1:
    # === Google Drive 섹션 ===
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
                        if results: # 첫번째 결과로 초기 선택 상태 설정
                            st.session_state.gdrive_selected_file_id = results[0]['id']
                            st.session_state.gdrive_selected_filename = results[0]['name']
                        st.success(f"✅ {len(results)}개 파일 검색 완료.")
                    else: # 결과 없음
                        st.session_state.gdrive_search_results = []
                        st.session_state.gdrive_file_options_map = {}
                        st.session_state.gdrive_selected_filename = None
                        st.session_state.gdrive_selected_file_id = None
                        st.warning("⚠️ 검색 결과가 없습니다.")
                else: st.warning("⚠️ 검색어를 입력하세요.")

            if st.session_state.gdrive_search_results:
                file_options_display = list(st.session_state.gdrive_file_options_map.keys())
                try: # 현재 선택된 파일명 기준 인덱스 찾기
                    current_index = file_options_display.index(st.session_state.get("gdrive_selected_filename", "")) if st.session_state.get("gdrive_selected_filename") in file_options_display else 0
                except ValueError: current_index = 0

                # 파일 선택 selectbox
                selected_filename_widget = st.selectbox(
                    "불러올 파일 선택:", options=file_options_display,
                    key="gdrive_selectbox_widget", # 위젯 키 분리
                    index=current_index
                )
                # Selectbox 값 변경 시 session_state 업데이트 (콜백 대신 직접 처리)
                if selected_filename_widget != st.session_state.get("gdrive_selected_filename"):
                    st.session_state.gdrive_selected_filename = selected_filename_widget
                    st.session_state.gdrive_selected_file_id = st.session_state.gdrive_file_options_map.get(selected_filename_widget)
                    # 선택 변경 시 즉시 rerun하여 버튼 활성화 상태 등 반영
                    st.rerun()


            # 불러오기 버튼
            load_button_disabled = not bool(st.session_state.gdrive_selected_file_id)
            if st.button("📂 선택 견적 불러오기", disabled=load_button_disabled, key="load_gdrive_btn"):
                file_id = st.session_state.gdrive_selected_file_id
                if file_id:
                    with st.spinner(f"🔄 견적 파일 로딩 중..."):
                        # --- AttributeError 수정 적용 ---
                        loaded_data = gdrive_utils.load_file(file_id) # JSON 파싱된 dict 또는 None 반환
                        # -----------------------------
                    if loaded_data:
                        load_success = load_state_from_data(loaded_data)
                        if load_success:
                            st.success("✅ 견적 정보를 성공적으로 불러왔습니다.")
                            st.rerun() # 로드 후 UI 즉시 업데이트
                    # 오류 발생 시 load_file 또는 load_state_from_data 내부에서 메시지 표시

        with col_save: # 저장
            st.markdown("**현재 견적 저장**")
            try: kst_ex = pytz.timezone("Asia/Seoul"); now_ex_str = datetime.now(kst_ex).strftime('%y%m%d')
            except: now_ex_str = datetime.now().strftime('%y%m%d')
            phone_ex = utils.extract_phone_number_part(st.session_state.get('customer_phone', ''), length=4, default="XXXX")
            example_fname = f"{now_ex_str}-{phone_ex}.json"
            st.caption(f"파일명 형식: `{example_fname}`")

            if st.button("💾 Google Drive에 저장", key="save_gdrive_btn"):
                try: kst_save = pytz.timezone("Asia/Seoul"); now_save = datetime.now(kst_save)
                except: now_save = datetime.now()
                date_str = now_save.strftime('%y%m%d')
                phone_part = utils.extract_phone_number_part(st.session_state.get('customer_phone', ''), length=4)
                if phone_part == "번호없음" or len(phone_part) < 4 or not str(st.session_state.get('customer_phone', '')).strip():
                    st.error("⚠️ 저장 실패: 유효한 고객 전화번호(숫자 4자리 이상 포함)를 먼저 입력해주세요.")
                else:
                    save_filename = f"{date_str}-{phone_part}.json"
                    state_data_to_save = prepare_state_for_save()
                    json_string_to_save = json.dumps(state_data_to_save, ensure_ascii=False, indent=2) # JSON 변환
                    with st.spinner(f"🔄 '{save_filename}' 파일 저장 중..."):
                         save_result = gdrive_utils.upload_or_update_json_to_drive(save_filename, json_string_to_save)
                    if save_result and isinstance(save_result, dict) and save_result.get('id'):
                         status_msg = "업데이트" if save_result.get('status') == 'updated' else "저장"
                         st.success(f"✅ '{save_filename}' 파일 {status_msg} 완료.")
                    else: st.error(f"❌ '{save_filename}' 파일 저장 중 오류 발생.")
            st.caption("동일 파일명 존재 시 덮어씁니다(업데이트).")

    st.divider()

    # --- 고객 정보 입력 필드 ---
    st.header("📝 고객 기본 정보")
    try: current_index_tab1 = MOVE_TYPE_OPTIONS.index(st.session_state.base_move_type)
    except ValueError: current_index_tab1 = 0
    st.radio(
        "🏢 **기본 이사 유형**", options=MOVE_TYPE_OPTIONS, index=current_index_tab1, horizontal=True,
        key="base_move_type_widget_tab1", on_change=sync_move_type, args=("base_move_type_widget_tab1",)
    )
    col_opts1, col_opts2 = st.columns(2)
    with col_opts1: st.checkbox("📦 보관이사 여부", key="is_storage_move")
    with col_opts2: st.checkbox("🛣️ 장거리 이사 적용", key="apply_long_distance")
    st.write("")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("👤 고객명", key="customer_name")
        st.text_input("📍 출발지 주소", key="from_location")
        if st.session_state.get('apply_long_distance'):
            st.selectbox("🛣️ 장거리 구간 선택", data.long_distance_options, key="long_distance_selector")
        st.text_input("🔼 출발지 층수", key="from_floor", placeholder="예: 3, B1")
        st.selectbox("🛠️ 출발지 작업 방법", data.METHOD_OPTIONS, key="from_method", help="사다리차, 승강기, 계단, 스카이 중 선택")
    with col2:
        st.text_input("📞 전화번호", key="customer_phone", placeholder="01012345678")
        st.text_input("📍 도착지 주소", key="to_location", placeholder="이사 도착지 상세 주소")
        st.text_input("🔽 도착지 층수", key="to_floor", placeholder="예: 5, 10")
        st.selectbox("🛠️ 도착지 작업 방법", data.METHOD_OPTIONS, key="to_method", help="사다리차, 승강기, 계단, 스카이 중 선택")
        current_moving_date_val = st.session_state.get('moving_date')
        if not isinstance(current_moving_date_val, date):
             try: kst_def = pytz.timezone("Asia/Seoul"); default_date_def = datetime.now(kst_def).date()
             except Exception: default_date_def = datetime.now().date()
             st.session_state.moving_date = default_date_def
        st.date_input("🗓️ 이사 예정일 (출발일)", key="moving_date")
        st.caption(f"⏱️ 견적 생성일: {utils.get_current_kst_time_str()}")

    st.divider()
    if st.session_state.get('is_storage_move'):
        st.subheader("📦 보관이사 추가 정보")
        if hasattr(data, 'STORAGE_TYPE_OPTIONS'):
            st.radio("보관 유형 선택:", options=data.STORAGE_TYPE_OPTIONS, key="storage_type", horizontal=True)
        else: st.warning("data.py에 STORAGE_TYPE_OPTIONS가 정의되지 않음")
        st.number_input("보관 기간 (일)", min_value=1, step=1, key="storage_duration")
    st.divider()
    st.header("🗒️ 고객 요구사항")
    st.text_area("기타 특이사항이나 요청사항을 입력해주세요.", height=100, key="special_notes", placeholder="예: 에어컨 이전 설치 필요, 특정 가구 분해/조립 요청 등")


# --- 탭 2: 물품 선택 ---
with tab2:
    st.header("📋 이사 품목 선택 및 수량 입력")
    st.caption(f"현재 선택된 기본 이사 유형: **{st.session_state.base_move_type}**")
    # 총 부피/무게 및 추천 차량 계산 (결과는 session_state에 저장됨)
    state_dict_for_calc = {key: st.session_state[key] for key in st.session_state}
    try:
        st.session_state.total_volume, st.session_state.total_weight = calculations.calculate_total_volume_weight(state_dict_for_calc, st.session_state.base_move_type)
        st.session_state.recommended_vehicle_auto, remaining_space = calculations.recommend_vehicle(st.session_state.total_volume, st.session_state.total_weight)
    except Exception as calc_err:
        st.error(f"물량 계산 중 오류 발생: {calc_err}")
        st.session_state.total_volume, st.session_state.total_weight = 0.0, 0.0
        st.session_state.recommended_vehicle_auto, remaining_space = None, 0.0

    # 품목별 수량 입력
    with st.container(border=True):
        st.subheader("품목별 수량 입력")
        item_category_to_display = data.item_definitions.get(st.session_state.base_move_type, {})
        basket_section_name_check = "포장 자재 📦"
        for section, item_list in item_category_to_display.items():
            if section == "폐기 처리 품목 🗑️": continue
            valid_items_in_section = [item for item in item_list if item in data.items]
            if not valid_items_in_section: continue
            with st.expander(f"{section} 품목 선택", expanded=(section == basket_section_name_check)):
                if section == basket_section_name_check:
                    selected_truck_tab2 = st.session_state.get("final_selected_vehicle")
                    if selected_truck_tab2 and selected_truck_tab2 in data.default_basket_quantities:
                        defaults = data.default_basket_quantities[selected_truck_tab2]
                        basket_qty = defaults.get('바구니', 0); med_basket_qty = defaults.get('중자바구니', 0); med_box_qty = defaults.get('중박스', med_basket_qty); book_qty = defaults.get('책바구니', 0)
                        st.info(f"💡 **{selected_truck_tab2}** 추천: 바{basket_qty} 중{med_box_qty} 책{book_qty} (직접 수정 가능)")
                    else: st.info("💡 비용 탭 차량 선택 시 추천 기본값 표시")
                num_columns = 2; cols = st.columns(num_columns)
                items_per_col = math.ceil(len(valid_items_in_section) / num_columns) if valid_items_in_section else 1
                for idx, item in enumerate(valid_items_in_section):
                    col_index = idx // items_per_col if items_per_col > 0 else 0
                    if col_index < num_columns:
                        with cols[col_index]:
                            unit = "칸" if item == "장롱" else "개"
                            widget_key = f"qty_{st.session_state.base_move_type}_{section}_{item}"
                            try: st.number_input(label=f"{item}", min_value=0, step=1, key=widget_key, help=f"{item} 수량 ({unit})")
                            except Exception as e: st.error(f"표시 오류: {item} ({e})")

    # 선택 품목 및 예상 물량 요약
    st.write("---")
    with st.container(border=True):
        st.subheader("📊 현재 선택된 품목 및 예상 물량")
        move_selection_display = {}
        processed_items_summary_move = set()
        original_item_defs_move = data.item_definitions.get(st.session_state.base_move_type, {})
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
                            except: qty = 0
                            if qty > 0 and item_move in data.items:
                                unit_move = "칸" if item_move == "장롱" else "개"
                                move_selection_display[item_move] = (qty, unit_move)
                        processed_items_summary_move.add(item_move)
        if move_selection_display:
            st.markdown("**선택 품목 목록:**")
            cols_disp_m = st.columns(2)
            item_list_disp_m = list(move_selection_display.items())
            items_per_col_disp_m = math.ceil(len(item_list_disp_m)/len(cols_disp_m)) if len(item_list_disp_m)>0 and len(cols_disp_m)>0 else 1
            for i, (item_disp, (qty_disp, unit_disp)) in enumerate(item_list_disp_m):
                col_idx_disp = i // items_per_col_disp_m if items_per_col_disp_m > 0 else 0
                if col_idx_disp < len(cols_disp_m):
                    with cols_disp_m[col_idx_disp]: st.write(f"- {item_disp}: {qty_disp} {unit_disp}")
            st.write(""); st.markdown("**예상 물량 및 추천 차량:**")
            st.info(f"📊 **총 부피:** {st.session_state.total_volume:.2f} m³ | **총 무게:** {st.session_state.total_weight:.2f} kg")
            recommended_vehicle_display = st.session_state.get('recommended_vehicle_auto')
            final_vehicle_tab2_display = st.session_state.get('final_selected_vehicle')
            if recommended_vehicle_display and "초과" not in recommended_vehicle_display:
                rec_text = f"✅ 추천 차량: **{recommended_vehicle_display}** ({remaining_space:.1f}% 여유 예상)"; spec = data.vehicle_specs.get(recommended_vehicle_display);
                if spec: rec_text += f" (최대: {spec['capacity']}m³, {spec['weight_capacity']:,}kg)"; st.success(rec_text)
                if final_vehicle_tab2_display and final_vehicle_tab2_display != recommended_vehicle_display: st.warning(f"⚠️ 비용 탭에서 **{final_vehicle_tab2_display}** 수동 선택됨.")
                elif not final_vehicle_tab2_display: st.info("💡 비용 탭에서 차량 최종 선택 필요.")
            elif recommended_vehicle_display and "초과" in recommended_vehicle_display:
                st.error(f"❌ 추천 차량: **{recommended_vehicle_display}**. 물량 과다. 물량 조정 또는 수동 차량 선택 필요.")
                if final_vehicle_tab2_display: st.info(f"ℹ️ 비용 탭에서 **{final_vehicle_tab2_display}** 수동 선택됨.")
            else:
                if st.session_state.total_volume > 0 or st.session_state.total_weight > 0: st.warning("⚠️ 자동 추천 불가. 비용 탭에서 수동 선택 필요.")
                else: st.info("ℹ️ 이사 품목 없음. 품목 선택 필요.")
                if final_vehicle_tab2_display: st.info(f"ℹ️ 비용 탭에서 **{final_vehicle_tab2_display}** 수동 선택됨.")
        else: st.info("ℹ️ 선택된 이사 품목이 없습니다. 위에서 품목을 선택해주세요.")


# --- 탭 3: 견적 및 비용 ---
with tab3:
    st.header("💰 계산 및 옵션 ")
    # 이사 유형 확인/변경
    st.subheader("🏢 이사 유형 확인/변경")
    try: current_index_tab3 = MOVE_TYPE_OPTIONS.index(st.session_state.base_move_type)
    except ValueError: current_index_tab3 = 0
    st.radio(
        "기본 이사 유형:", options=MOVE_TYPE_OPTIONS, index=current_index_tab3, horizontal=True,
        key="base_move_type_widget_tab3", on_change=sync_move_type, args=("base_move_type_widget_tab3",)
    )
    st.divider()

    # 차량 선택
    with st.container(border=True):
        st.subheader("🚚 차량 선택")
        col_v1_widget, col_v2_widget = st.columns([1, 2])
        with col_v1_widget:
            # --- StreamlitAPIException 수정: on_change 콜백 연결 ---
            st.radio("차량 선택 방식:", ["자동 추천 차량 사용", "수동으로 차량 선택"],
                     key="vehicle_select_radio",
                     help="자동 추천 사용 또는 목록에서 직접 선택",
                     on_change=update_vehicle_and_baskets) # 콜백 연결
            # -----------------------------------------------------
        with col_v2_widget:
            final_vehicle_widget = st.session_state.get('final_selected_vehicle')
            use_auto_widget = st.session_state.get('vehicle_select_radio') == "자동 추천 차량 사용"
            recommended_vehicle_auto_widget = st.session_state.get('recommended_vehicle_auto')
            current_move_type_widget = st.session_state.base_move_type
            vehicle_prices_options_widget = data.vehicle_prices.get(current_move_type_widget, {})
            available_trucks_widget = sorted(vehicle_prices_options_widget.keys(), key=lambda x: data.vehicle_specs.get(x, {}).get("capacity", 0))
            valid_auto_widget = (recommended_vehicle_auto_widget and "초과" not in recommended_vehicle_auto_widget and recommended_vehicle_auto_widget in available_trucks_widget)

            if use_auto_widget:
                if valid_auto_widget and final_vehicle_widget:
                    st.success(f"✅ 자동 선택됨: **{final_vehicle_widget}**")
                    spec = data.vehicle_specs.get(final_vehicle_widget)
                    if spec: st.caption(f"용량: {spec['capacity']}m³, {spec['weight_capacity']:,}kg | 예상짐: {st.session_state.get('total_volume',0.0):.2f}m³, {st.session_state.get('total_weight',0.0):.2f}kg")
                else:
                    error_msg = "⚠️ 자동 추천 불가: ";
                    if recommended_vehicle_auto_widget and "초과" in recommended_vehicle_auto_widget: error_msg += f"물량 초과({recommended_vehicle_auto_widget}). 수동 선택 필요."
                    elif not recommended_vehicle_auto_widget and (st.session_state.get('total_volume', 0.0) > 0 or st.session_state.get('total_weight', 0.0) > 0): error_msg += "계산/정보 부족. 수동 선택 필요."
                    else: error_msg += "물품 미선택 또는 정보 부족. 수동 선택 필요."
                    st.error(error_msg)

            if not use_auto_widget or (use_auto_widget and not valid_auto_widget):
                if not available_trucks_widget: st.error("❌ 선택 가능 차량 정보 없음.")
                else:
                    default_manual = recommended_vehicle_auto_widget if valid_auto_widget else (available_trucks_widget[0] if available_trucks_widget else None)
                    current_manual = st.session_state.get("manual_vehicle_select_value")
                    try: idx = available_trucks_widget.index(current_manual) if current_manual in available_trucks_widget else (available_trucks_widget.index(default_manual) if default_manual in available_trucks_widget else 0)
                    except ValueError: idx = 0
                    # --- StreamlitAPIException 수정: on_change 콜백 연결 ---
                    st.selectbox("차량 직접 선택:", available_trucks_widget, index=idx,
                                 key="manual_vehicle_select_value",
                                 on_change=update_vehicle_and_baskets) # 콜백 연결
                    # -----------------------------------------------------
                    manual_selected = st.session_state.get('manual_vehicle_select_value')
                    if manual_selected:
                        st.info(f"ℹ️ 수동 선택됨: **{manual_selected}**")
                        spec = data.vehicle_specs.get(manual_selected)
                        if spec: st.caption(f"용량: {spec['capacity']}m³, {spec['weight_capacity']:,}kg | 예상짐: {st.session_state.get('total_volume',0.0):.2f}m³, {st.session_state.get('total_weight',0.0):.2f}kg")

    st.divider()
    # 작업 조건 및 추가 옵션
    with st.container(border=True):
        st.subheader("🛠️ 작업 조건 및 추가 옵션")
        sky_from = st.session_state.get('from_method')=="스카이 🏗️"; sky_to = st.session_state.get('to_method')=="스카이 🏗️"
        if sky_from or sky_to:
            st.warning("스카이 작업 선택됨 - 시간 입력 필요", icon="🏗️")
            cols_sky = st.columns(2)
            with cols_sky[0]:
                if sky_from: st.number_input("출발 스카이 시간(h)", min_value=1, step=1, key="sky_hours_from")
                else: st.empty()
            with cols_sky[1]:
                if sky_to: st.number_input("도착 스카이 시간(h)", min_value=1, step=1, key="sky_hours_final")
                else: st.empty()
            st.write("")
        col_add1, col_add2 = st.columns(2)
        with col_add1: st.number_input("추가 남성 인원 👨", min_value=0, step=1, key="add_men", help="기본 인원 외 추가 남성 작업자 수")
        with col_add2: st.number_input("추가 여성 인원 👩", min_value=0, step=1, key="add_women", help="기본 인원 외 추가 여성 작업자 수")
        st.write("")
        st.subheader("🚚 실제 투입 차량")
        dispatched_cols = st.columns(4)
        with dispatched_cols[0]: st.number_input("1톤", min_value=0, step=1, key="dispatched_1t")
        with dispatched_cols[1]: st.number_input("2.5톤", min_value=0, step=1, key="dispatched_2_5t")
        with dispatched_cols[2]: st.number_input("3.5톤", min_value=0, step=1, key="dispatched_3_5t")
        with dispatched_cols[3]: st.number_input("5톤", min_value=0, step=1, key="dispatched_5t")
        st.caption("견적 계산과 별개로, 실제 투입될 차량 대수 입력")
        st.write("")

        base_w=0; remove_opt=False; final_vehicle_for_options = st.session_state.get('final_selected_vehicle'); current_move_type_options = st.session_state.base_move_type
        vehicle_prices_options_display = data.vehicle_prices.get(current_move_type_options, {})
        if final_vehicle_for_options and final_vehicle_for_options in vehicle_prices_options_display:
             base_info = vehicle_prices_options_display.get(final_vehicle_for_options, {}); base_w = base_info.get('housewife', 0);
             if base_w > 0: remove_opt = True
        if remove_opt:
            cost_per_person = getattr(data, 'ADDITIONAL_PERSON_COST', 200000); discount_amount = cost_per_person * base_w
            st.checkbox(f"기본 여성({base_w}명) 제외 (할인: -{discount_amount:,}원)", key="remove_base_housewife")
        else:
            if 'remove_base_housewife' in st.session_state: st.session_state.remove_base_housewife = False
        col_waste1, col_waste2 = st.columns([1, 2])
        with col_waste1: st.checkbox("폐기물 처리 필요 🗑️", key="has_waste_check", help="톤 단위 입력 방식")
        with col_waste2:
            if st.session_state.get('has_waste_check'):
                st.number_input("폐기물 양 (톤)", min_value=0.5, max_value=10.0, step=0.5, key="waste_tons_input", format="%.1f")
                waste_cost_per_ton = getattr(data, 'WASTE_DISPOSAL_COST_PER_TON', 300000); st.caption(f"💡 1톤당 {waste_cost_per_ton:,}원 추가 비용")
            else: st.empty()
        st.write("📅 **날짜 유형 선택** (중복 가능, 해당 시 할증)")
        date_options = ["이사많은날 🏠", "손없는날 ✋", "월말 📅", "공휴일 🎉", "금요일 📅"]; date_keys = [f"date_opt_{i}_widget" for i in range(len(date_options))]
        cols_date = st.columns(len(date_options))
        for i, option in enumerate(date_options):
            with cols_date[i]: st.checkbox(option, key=date_keys[i])

    st.divider()
    # 비용 조정 및 계약금
    with st.container(border=True):
        st.subheader("💰 비용 조정 및 계약금")
        col_adj1, col_adj2, col_adj3 = st.columns(3)
        with col_adj1: st.number_input("📝 계약금", min_value=0, step=10000, key="deposit_amount", format="%d", help="받을 계약금 입력")
        with col_adj2: st.number_input("💰 추가 조정 (+/-)", step=10000, key="adjustment_amount", help="추가 할증(+) 또는 할인(-) 금액", format="%d")
        with col_adj3: st.number_input("🪜 사다리 추가요금", min_value=0, step=10000, key="regional_ladder_surcharge", format="%d", help="추가 사다리차 비용 (지방 등)")

    st.divider()
    st.header("💵 최종 견적 결과")

    # 최종 견적 결과 표시
    total_cost = 0; cost_items = []; personnel_info = {}
    final_selected_vehicle_calc = st.session_state.get('final_selected_vehicle')

    if final_selected_vehicle_calc:
        try:
            current_state_dict = {k: v for k, v in st.session_state.items()}
            total_cost, cost_items, personnel_info = calculations.calculate_total_moving_cost(current_state_dict)
            total_cost_num = total_cost if isinstance(total_cost, (int, float)) else 0
            try: deposit_amount_num = int(st.session_state.get('deposit_amount', 0))
            except (ValueError, TypeError): deposit_amount_num = 0
            remaining_balance_num = total_cost_num - deposit_amount_num

            st.subheader(f"💰 총 견적 비용: {total_cost_num:,.0f} 원")
            st.subheader(f"➖ 계약금: {deposit_amount_num:,.0f} 원")
            st.subheader(f"➡️ 잔금 (총 비용 - 계약금): {remaining_balance_num:,.0f} 원")
            st.write("")
            st.subheader("📊 비용 상세 내역")
            error_item = next((item for item in cost_items if isinstance(item, (list, tuple)) and len(item)>0 and str(item[0]) == "오류"), None)
            if error_item: st.error(f"비용 계산 오류: {error_item[2]}")
            elif cost_items:
                df_display = pd.DataFrame(cost_items, columns=["항목", "금액", "비고"])
                st.dataframe(df_display.style.format({"금액": "{:,.0f}"}).set_properties(**{'text-align':'right'}, subset=['금액']).set_properties(**{'text-align':'left'}, subset=['항목','비고']), use_container_width=True, hide_index=True)
            else: st.info("ℹ️ 계산된 비용 항목이 없습니다.")
            st.write("")
            special_notes_display = st.session_state.get('special_notes')
            if special_notes_display and special_notes_display.strip():
                 st.subheader("📝 고객요구사항"); st.info(special_notes_display)

            st.subheader("📋 이사 정보 요약")
            summary_generated = False
            try:
                waste_info = {'total_waste_tons': st.session_state.get('waste_tons_input', 0.0) if st.session_state.get('has_waste_check') else 0.0,'total_waste_cost': 0}
                if waste_info['total_waste_tons'] > 0: waste_cost_per_ton_summary = getattr(data, 'WASTE_DISPOSAL_COST_PER_TON', 300000); waste_info['total_waste_cost'] = waste_info['total_waste_tons'] * waste_cost_per_ton_summary
                vehicle_info_summary = {'recommended_vehicles': {final_selected_vehicle_calc: 1} if final_selected_vehicle_calc else {}}
                excel_data_summary = excel_summary_generator.generate_summary_excel(current_state_dict, cost_items, personnel_info, vehicle_info_summary, waste_info)
                if excel_data_summary:
                    excel_buffer = io.BytesIO(excel_data_summary); xls = pd.ExcelFile(excel_buffer)
                    df_info = xls.parse("견적 정보", header=None); df_cost = xls.parse("비용 내역 및 요약", header=None)
                    info_dict = {}
                    if not df_info.empty and len(df_info.columns) > 1: info_dict = dict(zip(df_info[0].astype(str), df_info[1].astype(str)))
                    def fmt_m(a): try: i = int(float(str(a).replace(",","").split()[0])); return f"{i//10000}만" if i>=10000 else (f"{i}원" if i!=0 else "0원") except: return "금액오류"
                    def fmt_a(a): return str(a).strip() if isinstance(a,str) and a.strip() and a.lower()!='nan' else ""
                    def get_cost(k,ab,df):
                         if df.empty or len(df.columns)<2: return f"{ab} 정보없음"
                         for i in range(len(df)):
                             c = df.iloc[i,0];
                             if pd.notna(c) and str(c).strip().startswith(k): return f"{ab} {fmt_m(df.iloc[i,1])}"
                         return f"{ab} 정보없음"
                    def fmt_w(m): m=str(m).strip(); return "사" if "사다리차" in m else ("승" if "승강기" in m else ("계" if "계단" in m else ("스카이" if "스카이" in m else "?")))
                    from_a = fmt_a(info_dict.get("출발지 주소", "")); to_a = fmt_a(info_dict.get("도착지 주소", "")); ph = info_dict.get("연락처", "")
                    w_from = fmt_a(info_dict.get("출발지 작업 방법", "")); w_to = fmt_a(info_dict.get("도착지 작업 방법", ""))
                    disp_v = [f"1t:{st.session_state['dispatched_1t']}" if int(st.session_state.get('dispatched_1t',0))>0 else None, f"2.5t:{st.session_state['dispatched_2_5t']}" if int(st.session_state.get('dispatched_2_5t',0))>0 else None, f"3.5t:{st.session_state['dispatched_3_5t']}" if int(st.session_state.get('dispatched_3_5t',0))>0 else None, f"5t:{st.session_state['dispatched_5t']}" if int(st.session_state.get('dispatched_5t',0))>0 else None]
                    v_type = "/".join(filter(None, disp_v)) or (final_selected_vehicle_calc or "정보없음")
                    note = fmt_a(current_state_dict.get('special_notes',''))
                    p_info = personnel_info; men = p_info.get('final_men',0); women = p_info.get('final_women',0); p_fmt = f"{men}+{women}" if women>0 else f"{men}"
                    bsk_sec = "포장 자재 📦"; mv_type = st.session_state.base_move_type
                    k_b = f"qty_{mv_type}_{bsk_sec}_바구니"; k_mbk = f"qty_{mv_type}_{bsk_sec}_중자바구니"; k_mbox = f"qty_{mv_type}_{bsk_sec}_중박스"; k_book = f"qty_{mv_type}_{bsk_sec}_책바구니"
                    try: q_b,q_mbk,q_mbox,q_book = int(st.session_state.get(k_b,0)),int(st.session_state.get(k_mbk,0)),int(st.session_state.get(k_mbox,0)),int(st.session_state.get(k_book,0))
                    except: q_b,q_mbk,q_mbox,q_book = 0,0,0,0
                    q_med = q_mbox if q_mbox>0 else q_mbk; bsk_fmt = f"바{q_b} 중{q_med} 책{q_book}" if q_b+q_med+q_book>0 else ""
                    c_fee = get_cost("계약금","계",df_cost); r_fee = get_cost("잔금","잔",df_cost)
                    w_fmt = f"출{fmt_w(w_from)}도{fmt_w(w_to)}"
                    st.text(f"{from_a} - {to_a}");
                    if ph and ph!='-': st.text(f"{ph}")
                    st.text(f"{v_type} | {p_fmt}");
                    if bsk_fmt: st.text(bsk_fmt)
                    st.text(w_fmt); st.text(f"{c_fee} / {r_fee}");
                    if note and note.strip() and note.lower()!='nan' and note!='-': st.text(f"요청: {note.strip()}")
                    summary_generated = True
                else: st.warning("⚠️ 요약 정보 생성 실패 (엑셀 데이터 생성 오류)")
            except Exception as e: st.error(f"❌ 요약 정보 생성 중 오류 발생: {e}"); traceback.print_exc()
            if not summary_generated and final_selected_vehicle_calc: st.info("ℹ️ 요약 정보 표시 불가.")

            st.divider()
            # 다운로드 섹션
            st.subheader("📄 견적서 파일 다운로드")
            can_gen_pdf = bool(final_selected_vehicle_calc) and not error_item
            cols_dl = st.columns(3)
            with cols_dl[0]: # Final 견적서 (Excel)
                 st.markdown("**① Final 견적서 (Excel)**")
                 if st.button("📄 생성: Final 견적서"):
                    filled_excel_data = excel_filler.fill_final_excel_template(current_state_dict, cost_items, total_cost, personnel_info)
                    if filled_excel_data: st.session_state['final_excel_data'] = filled_excel_data; st.success("✅ 생성 완료!")
                    else:
                        if 'final_excel_data' in st.session_state: del st.session_state['final_excel_data']; st.error("❌ 생성 실패.")
                 if st.session_state.get('final_excel_data'):
                     ph_part = utils.extract_phone_number_part(st.session_state.get('customer_phone',''), length=4, default="0000"); now_str = datetime.now(pytz.timezone("Asia/Seoul")).strftime('%y%m%d') if pytz else datetime.now().strftime('%y%m%d'); fname = f"{ph_part}_{now_str}_Final견적서.xlsx"
                     st.download_button(label="📥 다운로드 (Excel)", data=st.session_state['final_excel_data'], file_name=fname, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key='dl_final_excel')
                 else: st.caption("생성 버튼 클릭")
            with cols_dl[1]: # 고객용 견적서 (PDF)
                st.markdown("**② 고객용 견적서 (PDF)**")
                if can_gen_pdf:
                    if st.button("📄 생성: PDF 견적서"):
                        pdf_bytes = pdf_generator.generate_pdf(current_state_dict, cost_items, total_cost, personnel_info)
                        st.session_state['pdf_data_customer'] = pdf_bytes
                        if pdf_bytes: st.success("✅ 생성 완료!")
                        else: st.error("❌ 생성 실패.")
                    if st.session_state.get('pdf_data_customer'):
                        ph_part = utils.extract_phone_number_part(st.session_state.get('customer_phone',''), length=4, default="0000"); now_str = datetime.now(pytz.timezone("Asia/Seoul")).strftime('%y%m%d_%H%M') if pytz else datetime.now().strftime('%y%m%d_%H%M'); fname = f"{ph_part}_{now_str}_이삿날견적서.pdf"
                        st.download_button(label="📥 다운로드 (PDF)", data=st.session_state['pdf_data_customer'], file_name=fname, mime='application/pdf', key='dl_pdf')
                    elif not st.session_state.get('pdf_data_customer'): st.caption("생성 버튼 클릭")
                else: st.caption("PDF 생성 불가")
            with cols_dl[2]: st.empty()

        except Exception as e: st.error(f"견적 결과 표시 중 오류: {e}"); traceback.print_exc()

    else: # 차량 미선택 시
        st.warning("⚠️ **차량을 먼저 선택해주세요.** 비용 계산, 요약 정보 표시 및 다운로드는 차량 선택 후 가능합니다.")
