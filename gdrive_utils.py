from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from google.oauth2 import service_account
import io
import json
import zipfile
import mimetypes

# 환경 설정
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'your-service-account.json'  # 본인의 서비스 계정 키 파일명

FOLDER_ID = 'your-folder-id'  # 견적 파일이 저장된 Google Drive 폴더 ID

# 인증된 Google Drive 서비스 클라이언트 생성
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials)


def search_files(search_term):
    """Google Drive에서 파일 이름으로 검색"""
    query = f"'{FOLDER_ID}' in parents and name contains '{search_term}' and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id, name)", pageSize=100).execute()
    return results.get('files', [])


def load_estimate_and_images(file_id):
    """
    선택한 JSON 견적 파일과 관련 이미지(.png, .jpg 등)를 불러옵니다.
    JSON 파일에는 'uploaded_image_filenames' 필드가 포함되어 있어야 합니다.
    """
    # 1. JSON 파일 불러오기
    try:
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

        fh.seek(0)
        json_bytes = fh.read()
        json_data = json.loads(json_bytes.decode('utf-8'))

    except Exception as e:
        print(f"[오류] JSON 파일 다운로드 실패: {e}")
        return None, []

    # 2. 이미지 파일명 목록 확보
    image_filenames = json_data.get("uploaded_image_filenames", [])
    loaded_images = []

    # 3. 이미지 파일 개별 다운로드
    for image_filename in image_filenames:
        try:
            query = f"'{FOLDER_ID}' in parents and name = '{image_filename}' and trashed = false"
            results = drive_service.files().list(q=query, fields="files(id, name)").execute()
            files = results.get('files', [])
            if not files:
                print(f"[경고] 이미지 파일 '{image_filename}'을 찾을 수 없음")
                continue

            image_file_id = files[0]['id']
            img_request = drive_service.files().get_media(fileId=image_file_id)
            img_fh = io.BytesIO()
            img_downloader = MediaIoBaseDownload(img_fh, img_request)
            done = False
            while not done:
                status, done = img_downloader.next_chunk()
            img_fh.seek(0)
            loaded_images.append((image_filename, img_fh.read()))
        except Exception as e:
            print(f"[오류] 이미지 '{image_filename}' 다운로드 실패: {e}")
            continue

    return json_data, loaded_images


def save_estimate_with_images(file_base_name, json_data_dict, image_list):
    """
    JSON 데이터와 이미지들을 Google Drive에 저장합니다.
    같은 파일명이 있을 경우 덮어쓰기합니다.
    """
    try:
        # 기존 JSON 파일 존재 확인 및 삭제
        existing_files = search_files(file_base_name + ".json")
        for f in existing_files:
            drive_service.files().delete(fileId=f['id']).execute()

        # 1. JSON 파일 업로드
        json_bytes = json.dumps(json_data_dict, ensure_ascii=False, indent=2).encode("utf-8")
        media = MediaIoBaseUpload(io.BytesIO(json_bytes), mimetype='application/json')
        file_metadata = {
            'name': file_base_name + ".json",
            'parents': [FOLDER_ID]
        }
        drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        # 2. 이미지 파일 업로드 (동일 이름이 있다면 삭제 후 재업로드)
        for filename, img_bytes in image_list:
            existing_imgs = search_files(filename)
            for img in existing_imgs:
                drive_service.files().delete(fileId=img['id']).execute()
            mime_type = mimetypes.guess_type(filename)[0] or 'image/jpeg'
            img_media = MediaIoBaseUpload(io.BytesIO(img_bytes), mimetype=mime_type)
            img_metadata = {
                'name': filename,
                'parents': [FOLDER_ID]
            }
            drive_service.files().create(body=img_metadata, media_body=img_media, fields='id').execute()

        return True
    except Exception as e:
        print(f"[오류] 저장 실패: {e}")
        return False
