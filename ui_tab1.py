import streamlit as st
import os
import json
import gdrive_utils
import google_drive_helper
from PIL import Image
from io import BytesIO

def render_tab1():
    st.subheader("1단계: 고객 정보 및 견적 파일 관리")

    # --- 기본 정보 입력 ---
    with st.form("customer_info_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            customer_name = st.text_input("고객 성함", key="customer_name")
        with col2:
            customer_phone = st.text_input("연락처 (- 포함)", key="customer_phone")
        with col3:
            moving_date = st.date_input("이사 예정일", key="moving_date")

        submitted_customer = st.form_submit_button("기본 정보 저장")
        if submitted_customer:
            st.success("✅ 고객 정보가 저장되었습니다. 아래에서 파일을 불러오거나 새로 저장할 수 있습니다.")

    st.markdown("---")

    # --- 파일 불러오기 ---
    st.markdown("### 🔍 Google Drive에서 기존 견적 불러오기")
    search_key = st.text_input("검색 키워드 (예: 0425-1234)", key="search_key")
    if st.button("검색"):
        if search_key:
            files = gdrive_utils.search_files(search_key)
            if files:
                selected_file = st.selectbox("파일을 선택하세요", files)
                if selected_file:
                    json_data, loaded_images = gdrive_utils.load_estimate_and_images(selected_file['id'])
                    if json_data:
                        st.session_state.update(json_data)
                        st.session_state['loaded_images'] = loaded_images
                        st.success("✅ 파일이 성공적으로 불러와졌습니다.")
                    else:
                        st.warning("⚠️ 파일 로딩에 실패했습니다.")
            else:
                st.warning("검색된 파일이 없습니다.")
        else:
            st.warning("검색 키워드를 입력해주세요.")

    st.markdown("---")

    # --- 이미지 업로드 ---
    st.markdown("### 📷 이사 사진 업로드 (최대 5장)")
    uploaded_image_files = st.file_uploader(
        "사진 첨부 (최대 5장):",
        accept_multiple_files=True,
        type=['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp']
    )

    if uploaded_image_files:
        st.image(uploaded_image_files, width=150)

    st.markdown("---")

    # --- 저장하기 ---
    st.markdown("### 💾 Google Drive에 견적 저장하기")
    save_filename = st.text_input("저장할 파일명 (예: 0425-1234)", key="save_filename")
    if st.button("Google Drive에 저장"):
        if save_filename:
            # JSON 저장
            state_data_to_save = st.session_state.to_dict()
            save_success = gdrive_utils.save_file(save_filename, state_data_to_save)
            
            # 이미지 저장
            if uploaded_image_files:
                for idx, image_file in enumerate(uploaded_image_files):
                    if idx >= 5:
                        st.warning("5장까지만 저장됩니다.")
                        break
                    image_bytes = image_file.read()
                    google_drive_helper.upload_image_to_drive(f"{save_filename}_사진{idx+1}.png", image_bytes)

            if save_success:
                st.success("✅ 견적이 Google Drive에 저장되었습니다.")
            else:
                st.error("❌ 저장에 실패했습니다.")
        else:
            st.warning("파일명을 입력해주세요.")
