# ui_tab3.py (Updated summary display logic)
import streamlit as st
import pandas as pd
import io
import pytz
from datetime import datetime
import traceback # Keep for error handling

# Import necessary custom modules
try:
    import data
    import utils
    import calculations
    import pdf_generator # Needed for generate_excel (used in summary) and generate_pdf
    import excel_filler # Needed for the final excel generation
    from state_manager import MOVE_TYPE_OPTIONS
    from callbacks import sync_move_type, update_basket_quantities
except ImportError as e:
    st.error(f"UI Tab 3: 필수 모듈 로딩 실패 - {e}")
    st.stop()


def render_tab3():
    """Renders the UI for Tab 3: Costs, Options, and Downloads."""

    st.header("💰 계산 및 옵션 ")

    # --- Move Type Selection (Tab 3) ---
    # (Remains the same)
    st.subheader("🏢 이사 유형 확인/변경")
    current_move_type = st.session_state.get('base_move_type')
    try:
        if not MOVE_TYPE_OPTIONS: raise ValueError("MOVE_TYPE_OPTIONS not defined")
        current_index_tab3 = MOVE_TYPE_OPTIONS.index(current_move_type)
    except (ValueError, AttributeError):
        current_index_tab3 = 0
        if current_move_type is not None: st.session_state.base_move_type = MOVE_TYPE_OPTIONS[0]; print("Warning: Resetting base_move_type in Tab 3 due to invalid state.")
    st.radio( "기본 이사 유형:", options=MOVE_TYPE_OPTIONS, index=current_index_tab3, horizontal=True, key="base_move_type_widget_tab3", on_change=sync_move_type, args=("base_move_type_widget_tab3",) )
    st.divider()

    # --- Vehicle Selection ---
    # (Remains the same)
    with st.container(border=True):
        st.subheader("🚚 차량 선택")
        col_v1_widget, col_v2_widget = st.columns([1, 2])
        with col_v1_widget: st.radio( "차량 선택 방식:", ["자동 추천 차량 사용", "수동으로 차량 선택"], key="vehicle_select_radio", help="자동 추천을 사용하거나, 목록에서 직접 차량을 선택합니다.", on_change=update_basket_quantities )
        with col_v2_widget:
            current_move_type_widget = st.session_state.base_move_type; vehicle_prices_options_widget = data.vehicle_prices.get(current_move_type_widget, {})
            available_trucks_widget = sorted(vehicle_prices_options_widget.keys(), key=lambda x: data.vehicle_specs.get(x, {}).get("capacity", 0))
            use_auto_widget = st.session_state.get('vehicle_select_radio') == "자동 추천 차량 사용"; recommended_vehicle_auto_widget = st.session_state.get('recommended_vehicle_auto')
            final_vehicle_widget = st.session_state.get('final_selected_vehicle'); valid_auto_widget = (recommended_vehicle_auto_widget and "초과" not in recommended_vehicle_auto_widget and recommended_vehicle_auto_widget in available_trucks_widget)
            if use_auto_widget:
                if valid_auto_widget:
                    st.success(f"✅ 자동 선택됨: **{final_vehicle_widget}**"); spec = data.vehicle_specs.get(final_vehicle_widget)
                    if spec: st.caption(f"선택차량 최대 용량: {spec.get('capacity', 'N/A')}m³, {spec.get('weight_capacity', 'N/A'):,}kg"); st.caption(f"현재 이사짐 예상: {st.session_state.get('total_volume',0.0):.2f}m³, {st.session_state.get('total_weight',0.0):.2f}kg")
                else:
                    error_msg = "⚠️ 자동 추천 불가: "
                    if recommended_vehicle_auto_widget and "초과" in recommended_vehicle_auto_widget: error_msg += f"물량 초과({recommended_vehicle_auto_widget}). 수동 선택 필요."
                    elif not recommended_vehicle_auto_widget and (st.session_state.get('total_volume', 0.0) > 0 or st.session_state.get('total_weight', 0.0) > 0): error_msg += "계산/정보 부족. 수동 선택 필요."
                    else: error_msg += "물품 미선택 또는 정보 부족. 수동 선택 필요."; st.error(error_msg)
                    if not available_trucks_widget: st.error("❌ 현재 이사 유형에 선택 가능한 차량 정보가 없습니다.")
                    else:
                         current_manual_selection_widget = st.session_state.get("manual_vehicle_select_value")
                         try: current_index_widget = available_trucks_widget.index(current_manual_selection_widget) if current_manual_selection_widget in available_trucks_widget else 0
                         except ValueError: current_index_widget = 0
                         if current_manual_selection_widget not in available_trucks_widget: st.session_state.manual_vehicle_select_value = available_trucks_widget[0]
                         st.selectbox( "수동으로 차량 선택:", available_trucks_widget, index=current_index_widget, key="manual_vehicle_select_value", on_change=update_basket_quantities )
                         manual_selected_display = st.session_state.get('manual_vehicle_select_value')
                         if manual_selected_display:
                            st.info(f"ℹ️ 수동 선택됨: **{manual_selected_display}**"); spec_manual = data.vehicle_specs.get(manual_selected_display)
                            if spec_manual: st.caption(f"선택차량 최대 용량: {spec_manual.get('capacity', 'N/A')}m³, {spec_manual.get('weight_capacity', 'N/A'):,}kg"); st.caption(f"현재 이사짐 예상: {st.session_state.get('total_volume',0.0):.2f}m³, {st.session_state.get('total_weight',0.0):.2f}kg")
            else: # Manual mode
                if not available_trucks_widget: st.error("❌ 현재 이사 유형에 선택 가능한 차량 정보가 없습니다.")
                else:
                    current_manual_selection_widget = st.session_state.get("manual_vehicle_select_value");
                    try: current_index_widget = available_trucks_widget.index(current_manual_selection_widget) if current_manual_selection_widget in available_trucks_widget else 0
                    except ValueError: current_index_widget = 0
                    if current_manual_selection_widget not in available_trucks_widget: st.session_state.manual_vehicle_select_value = available_trucks_widget[0]
                    st.selectbox( "차량 직접 선택:", available_trucks_widget, index=current_index_widget, key="manual_vehicle_select_value", on_change=update_basket_quantities )
                    manual_selected_display = st.session_state.get('manual_vehicle_select_value')
                    if manual_selected_display:
                       st.info(f"ℹ️ 수동 선택됨: **{manual_selected_display}**"); spec_manual = data.vehicle_specs.get(manual_selected_display)
                       if spec_manual: st.caption(f"선택차량 최대 용량: {spec_manual.get('capacity', 'N/A')}m³, {spec_manual.get('weight_capacity', 'N/A'):,}kg"); st.caption(f"현재 이사짐 예상: {st.session_state.get('total_volume',0.0):.2f}m³, {st.session_state.get('total_weight',0.0):.2f}kg")
    st.divider()

    # --- Work Conditions & Options ---
    # (Remains the same)
    with st.container(border=True):
        st.subheader("🛠️ 작업 조건 및 추가 옵션")
        sky_from = st.session_state.get('from_method') == "스카이 🏗️"; sky_to = st.session_state.get('to_method') == "스카이 🏗️"
        if sky_from or sky_to:
            st.warning("스카이 작업 선택됨 - 시간 입력 필요", icon="🏗️"); cols_sky = st.columns(2)
            with cols_sky[0]:
                if sky_from: st.number_input("출발 스카이 시간(h)", min_value=1, step=1, key="sky_hours_from")
            with cols_sky[1]:
                if sky_to: st.number_input("도착 스카이 시간(h)", min_value=1, step=1, key="sky_hours_final")
            st.write("")
        col_add1, col_add2 = st.columns(2)
        with col_add1: st.number_input("추가 남성 인원 👨", min_value=0, step=1, key="add_men", help="기본 인원 외 추가로 필요한 남성 작업자 수")
        with col_add2: st.number_input("추가 여성 인원 👩", min_value=0, step=1, key="add_women", help="기본 인원 외 추가로 필요한 여성 작업자 수")
        st.write("")
        st.subheader("🚚 실제 투입 차량")
        dispatched_cols = st.columns(4); with dispatched_cols[0]: st.number_input("1톤", min_value=0, step=1, key="dispatched_1t"); with dispatched_cols[1]: st.number_input("2.5톤", min_value=0, step=1, key="dispatched_2_5t"); with dispatched_cols[2]: st.number_input("3.5톤", min_value=0, step=1, key="dispatched_3_5t"); with dispatched_cols[3]: st.number_input("5톤", min_value=0, step=1, key="dispatched_5t")
        st.caption("견적 계산과 별개로, 실제 현장에 투입될 차량 대수를 입력합니다."); st.write("")
        base_w = 0; remove_opt = False; final_vehicle_for_options = st.session_state.get('final_selected_vehicle'); current_move_type_options = st.session_state.base_move_type; vehicle_prices_options_display = data.vehicle_prices.get(current_move_type_options, {})
        if final_vehicle_for_options and final_vehicle_for_options in vehicle_prices_options_display: base_info = vehicle_prices_options_display.get(final_vehicle_for_options, {}); base_w = base_info.get('housewife', 0);
        if base_w > 0: remove_opt = True
        if remove_opt: discount_amount = data.ADDITIONAL_PERSON_COST * base_w; st.checkbox(f"기본 여성({base_w}명) 제외 (비용 할인: -{discount_amount:,}원)", key="remove_base_housewife")
        else:
             if 'remove_base_housewife' in st.session_state: st.session_state.remove_base_housewife = False
        col_waste1, col_waste2 = st.columns([1, 2])
        with col_waste1: st.checkbox("폐기물 처리 필요 🗑️", key="has_waste_check", help="톤 단위 직접 입력 방식입니다.")
        with col_waste2:
            if st.session_state.get('has_waste_check'): st.number_input("폐기물 양 (톤)", min_value=0.5, max_value=10.0, step=0.5, key="waste_tons_input", format="%.1f"); st.caption(f"💡 1톤당 {data.WASTE_DISPOSAL_COST_PER_TON:,}원 추가 비용 발생")
        st.write("📅 **날짜 유형 선택** (중복 가능, 해당 시 할증)")
        date_options = ["이사많은날 🏠", "손없는날 ✋", "월말 📅", "공휴일 🎉", "금요일 📅"]; date_keys = [f"date_opt_{i}_widget" for i in range(len(date_options))]; cols_date = st.columns(len(date_options))
        for i, option in enumerate(date_options): with cols_date[i]: st.checkbox(option, key=date_keys[i])
    st.divider()

    # --- Cost Adjustment & Deposit ---
    # (Remains the same)
    with st.container(border=True):
        st.subheader("💰 비용 조정 및 계약금")
        col_adj1, col_adj2, col_adj3 = st.columns(3)
        with col_adj1: st.number_input("📝 계약금", min_value=0, step=10000, key="deposit_amount", format="%d", help="고객에게 받을 계약금 입력")
        with col_adj2: st.number_input("💰 추가 조정 (+/-)", step=10000, key="adjustment_amount", help="견적 금액 외 추가 할증(+) 또는 할인(-) 금액 입력", format="%d")
        with col_adj3: st.number_input("🪜 사다리 추가요금", min_value=0, step=10000, key="regional_ladder_surcharge", format="%d", help="추가되는 사다리차 비용")
    st.divider()

    # --- Final Quote Results ---
    st.header("💵 최종 견적 결과")

    final_selected_vehicle_calc = st.session_state.get('final_selected_vehicle')

    if final_selected_vehicle_calc:
        # Calculate costs
        current_state_dict = st.session_state.to_dict()
        total_cost, cost_items, personnel_info = calculations.calculate_total_moving_cost(current_state_dict)
        total_cost_num = total_cost if isinstance(total_cost, (int, float)) else 0
        try: deposit_amount_num = int(st.session_state.get('deposit_amount', 0))
        except (ValueError, TypeError): deposit_amount_num = 0
        remaining_balance_num = total_cost_num - deposit_amount_num

        # Display Cost Summary
        # (Remains the same)
        st.subheader(f"💰 총 견적 비용: {total_cost_num:,.0f} 원")
        st.subheader(f"➖ 계약금: {deposit_amount_num:,.0f} 원")
        st.subheader(f"➡️ 잔금 (총 비용 - 계약금): {remaining_balance_num:,.0f} 원")
        st.write("")

        # Display Detailed Costs
        # (Remains the same)
        st.subheader("📊 비용 상세 내역")
        error_item = next((item for item in cost_items if isinstance(item, (list, tuple)) and len(item)>0 and str(item[0]) == "오류"), None)
        if error_item: st.error(f"비용 계산 오류: {error_item[2]}")
        elif cost_items:
            df_display = pd.DataFrame(cost_items, columns=["항목", "금액", "비고"])
            st.dataframe( df_display.style.format({"금액": "{:,.0f}"}).set_properties(**{'text-align': 'right'}, subset=['금액']).set_properties(**{'text-align': 'left'}, subset=['항목', '비고']), use_container_width=True, hide_index=True )
        else: st.info("ℹ️ 계산된 비용 항목이 없습니다.")
        st.write("")

        # Display Special Notes if they exist
        # (Remains the same)
        special_notes_display = st.session_state.get('special_notes')
        if special_notes_display and special_notes_display.strip(): st.subheader("📝 고객요구사항"); st.info(special_notes_display)

        # --- Move Info Summary (UPDATED) ---
        st.subheader("📋 이사 정보 요약")
        summary_generated = False
        try:
            # Generate excel data in memory to easily extract formatted values
            excel_data_summary = pdf_generator.generate_excel(current_state_dict, cost_items, total_cost, personnel_info)
            if excel_data_summary:
                excel_buffer = io.BytesIO(excel_data_summary)
                xls = pd.ExcelFile(excel_buffer)
                if "견적 정보" in xls.sheet_names and "비용 내역 및 요약" in xls.sheet_names:
                    df_info = xls.parse("견적 정보", header=None)
                    df_cost = xls.parse("비용 내역 및 요약", header=None)
                    info_dict = dict(zip(df_info[0].astype(str), df_info[1].astype(str))) if not df_info.empty and len(df_info.columns) > 1 else {}

                    # --- Helper functions (Keep as before) ---
                    def format_money_kor(amount):
                        try: amount_str = str(amount).replace(",", "").split()[0]; amount_float = float(amount_str); amount_int = int(amount_float)
                        except: return "금액오류"
                        if amount_int >= 10000: return f"{amount_int // 10000}만원"
                        elif amount_int != 0: return f"{amount_int}원"
                        else: return "0원"
                    def format_address(addr): return str(addr).strip() if isinstance(addr, str) and addr.strip() and addr.lower() != 'nan' else ""
                    def get_cost_abbr(kw, abbr, df):
                        if df.empty or len(df.columns) < 2: return f"{abbr} 정보 없음"
                        for i in range(len(df)):
                            if pd.notna(df.iloc[i, 0]) and str(df.iloc[i, 0]).strip().startswith(kw): return f"{abbr} {format_money_kor(df.iloc[i, 1])}"
                        return f"{abbr} 정보 없음"
                    def format_method(m):
                        m = str(m).strip(); return "사" if "사다리차" in m else "승" if "승강기" in m else "계" if "계단" in m else "스카이" if "스카이" in m else "?"
                    # --- End Helper functions ---

                    # --- Extract data for summary ---
                    from_addr = format_address(info_dict.get("출발지", st.session_state.get('from_location','')))
                    to_addr = format_address(info_dict.get("도착지", st.session_state.get('to_location','')))
                    phone = info_dict.get("고객 연락처", st.session_state.get('customer_phone',''))
                    vehicle_type = final_selected_vehicle_calc # Use the final selected vehicle
                    note = format_address(info_dict.get("고객요구사항", st.session_state.get('special_notes',''))) # Use "note" for special notes
                    p_info = personnel_info if isinstance(personnel_info, dict) else {}
                    men = p_info.get('final_men', 0); women = p_info.get('final_women', 0); ppl = f"{men}+{women}" if women > 0 else f"{men}"
                    b_name = "포장 자재 📦"; move_t = st.session_state.base_move_type
                    q_b = int(st.session_state.get(f"qty_{move_t}_{b_name}_바구니", 0)); q_m = int(st.session_state.get(f"qty_{move_t}_{b_name}_중박스", 0)); q_c = int(st.session_state.get(f"qty_{move_t}_{b_name}_옷바구니", 0)); q_k = int(st.session_state.get(f"qty_{move_t}_{b_name}_책바구니", 0)) # Get clothes basket too
                    # Format basket string including new items
                    bask_parts = []
                    if q_b > 0: bask_parts.append(f"바{q_b}")
                    if q_m > 0: bask_parts.append(f"중{q_m}")
                    if q_c > 0: bask_parts.append(f"옷{q_c}") # Add clothes basket
                    if q_k > 0: bask_parts.append(f"책{q_k}")
                    bask = " ".join(bask_parts)

                    cont_fee = get_cost_abbr("계약금 (-)", "계", df_cost); rem_fee = get_cost_abbr("잔금 (VAT 별도)", "잔", df_cost)
                    w_from = format_method(info_dict.get("출발 작업", st.session_state.get('from_method',''))); w_to = format_method(info_dict.get("도착 작업", st.session_state.get('to_method',''))); work = f"출{w_from}도{w_to}"
                    # --- End Extract data ---

                    # --- Construct and display summary ---
                    st.text(f"{vehicle_type}") # Line 1: Vehicle only
                    st.text("")

                    if phone and phone != '-': # Line 2: Phone
                        st.text(phone)
                        st.text("")

                    if from_addr: # Line 3: Full From Address
                        st.text(from_addr)
                    if to_addr: # Line 4: Full To Address
                        st.text(to_addr)
                    if from_addr or to_addr: # Add blank line if addresses were printed
                        st.text("")

                    # Line 5: Personnel (already includes vehicle type) - Let's just show personnel count
                    st.text(f"{ppl}") # Just show personnel count e.g., "4+2"
                    st.text("")

                    if bask: # Line 6: Baskets
                        st.text(bask)
                        st.text("")

                    # Line 7: Work method
                    st.text(work)
                    st.text("")

                    # Line 8: Costs
                    st.text(f"{cont_fee} / {rem_fee}")
                    st.text("")

                    # Line 9 onwards: Special Notes (split by '.')
                    if note: # Check if note is not empty or just whitespace
                        notes_list = [n.strip() for n in note.split('.') if n.strip()] # Split by '.', remove empty strings
                        for note_line in notes_list:
                            st.text(note_line) # Print each part on a new line
                    # --- End construct and display ---

                    summary_generated = True
                else: st.warning("⚠️ 요약 정보 생성 실패 (필수 Excel 시트 누락)")
            else: st.warning("⚠️ 요약 정보 생성 실패 (Excel 데이터 생성 오류)")
        except Exception as e: st.error(f"❌ 요약 정보 생성 중 오류 발생: {e}"); traceback.print_exc()
        if not summary_generated: st.info("ℹ️ 요약 정보를 표시할 수 없습니다.")
        # --- End Move Info Summary ---

        st.divider()

        # --- Download Section ---
        # (Remains the same)
        st.subheader("📄 견적서 파일 다운로드")
        has_cost_error = any(isinstance(item, (list, tuple)) and len(item)>0 and str(item[0]) == "오류" for item in cost_items) if cost_items else False
        can_gen_pdf = bool(final_selected_vehicle_calc) and not has_cost_error; can_gen_final_excel = bool(final_selected_vehicle_calc)
        cols_dl = st.columns(3)
        with cols_dl[0]:
            st.markdown("**① Final 견적서 (Excel)**")
            if can_gen_final_excel:
                if st.button("📄 생성: Final 견적서"):
                    latest_total_cost_fe, latest_cost_items_fe, latest_personnel_info_fe = calculations.calculate_total_moving_cost(st.session_state.to_dict())
                    filled_excel_data = excel_filler.fill_final_excel_template(st.session_state.to_dict(), latest_cost_items_fe, latest_total_cost_fe, latest_personnel_info_fe)
                    if filled_excel_data: st.session_state['final_excel_data'] = filled_excel_data; st.success("✅ 생성 완료!")
                    else:
                        if 'final_excel_data' in st.session_state: del st.session_state['final_excel_data']
                        st.error("❌ 생성 실패.")
                if st.session_state.get('final_excel_data'):
                    ph_part = utils.extract_phone_number_part(st.session_state.get('customer_phone', ''), 4, "0000"); now_str = datetime.now(pytz.timezone("Asia/Seoul")).strftime('%y%m%d') if pytz else datetime.now().strftime('%y%m%d')
                    fname = f"{ph_part}_{now_str}_Final견적서.xlsx"
                    st.download_button("📥 다운로드 (Excel)", st.session_state['final_excel_data'], fname, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key='dl_final_excel')
                elif not st.session_state.get('final_excel_data'): st.caption("생성 버튼 클릭")
            else: st.caption("Excel 생성 불가 (차량 미선택)")
        with cols_dl[1]:
            st.markdown("**② 고객용 견적서 (PDF)**")
            if can_gen_pdf:
                if st.button("📄 생성: PDF 견적서"):
                    latest_total_cost_pdf, latest_cost_items_pdf, latest_personnel_info_pdf = calculations.calculate_total_moving_cost(st.session_state.to_dict())
                    pdf_bytes = pdf_generator.generate_pdf(st.session_state.to_dict(), latest_cost_items_pdf, latest_total_cost_pdf, latest_personnel_info_pdf)
                    st.session_state['pdf_data_customer'] = pdf_bytes
                    if pdf_bytes: st.success("✅ 생성 완료!")
                    else: st.error("❌ 생성 실패.")
                if st.session_state.get('pdf_data_customer'):
                    ph_part = utils.extract_phone_number_part(st.session_state.get('customer_phone', ''), 4, "0000"); now_str = datetime.now(pytz.timezone("Asia/Seoul")).strftime('%y%m%d_%H%M') if pytz else datetime.now().strftime('%y%m%d_%H%M')
                    fname = f"{ph_part}_{now_str}_이삿날견적서.pdf"
                    st.download_button("📥 다운로드 (PDF)", st.session_state['pdf_data_customer'], fname, 'application/pdf', key='dl_pdf')
                elif not st.session_state.get('pdf_data_customer'): st.caption("생성 버튼 클릭")
            else: st.caption("PDF 생성 불가 (차량 미선택/비용 오류)")
        with cols_dl[2]: st.empty()

    else: # Vehicle not selected
        st.warning("⚠️ **차량을 먼저 선택해주세요.** 비용 계산, 요약 정보 표시 및 다운로드는 차량 선택 후 가능합니다.")

# --- End of render_tab3 function ---
