from flask import Blueprint, request, jsonify, session, Flask
from database import fs_diary, diaries
from bson import ObjectId
from gridfs.errors import NoFile, GridFSError  # 중복 제거
from datetime import datetime
from flask_cors import CORS
import base64

# Blueprint 설정
diary_bp = Blueprint('diary_bp', __name__)

app = Flask(__name__)
CORS(app)  # 모든 도메인에서의 요청을 허용

# 홈 경기 장소 리스트
HOME_LOCATIONS = ["busan", "second", "third"]

@diary_bp.route('/api/post_diary', methods=['POST'])
def post_diary():
    try:
        # 입력 데이터 받아오기
        name = request.form.get('name', "")
        date = request.form.get("date", "")
        weather = request.form.get("weather", "")
        location = request.form.get("location", "")
        together = request.form.get("together", "")
        win_status = request.form.get("win_status", "")
        section = request.form.get("section", "")  # 좌석 구역
        row = request.form.get("row", "")  # 좌석 열
        number = request.form.get("number", "")  # 좌석 번호
        diary_photo = request.files.get('diary_photo')  # 이미지 파일
        message = request.form.get("message", "")

        # GridFS에 이미지 저장
        photo_id = None
        if diary_photo:
            try:
                # 파일을 GridFS에 저장하고 ID를 photo_id로 저장
                photo_id = fs_diary.put(diary_photo, filename=diary_photo.filename)
            except gridfs.errors.GridFSError as e:
                return jsonify({"error": "Failed to save photo"}), 500

        # location에 따른 홈경기 여부 자동 설정
        is_home_game = location in HOME_LOCATIONS

        # 현재 시간(데이터가 저장된 시간) 추가
        saved_at = datetime.now()

        # diaries 컬렉션에 저장할 데이터
        diary_entry = {
            "name": name,
            "date": datetime.strptime(date, '%Y-%m-%d'),  # 날짜 파싱
            "weather": weather,
            "location": location,
            "together": together,
            "win_status": win_status,
            "is_home_game": is_home_game,
            "diary_photo": photo_id,  # 이미지 ID
            "diary_message": message,  # 메시지 필드
            "saved_at": saved_at,  # 데이터 저장 시간 추가
            "seat_info": {
                "section": section,
                "row": row,
                "number": number
            }  # 좌석 정보 추가
        }

        # MongoDB에 다이어리 데이터 저장
        result = diaries.insert_one(diary_entry)
        return jsonify({"message": "Diary entry created successfully", "id": str(result.inserted_id)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@diary_bp.route('/api/get_diary_personal', methods=['GET'])
def get_diary_personal():
    try:
        # 쿼리 매개변수로부터 사용자 이름, 페이지, 페이지 크기 가져오기
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        skip = (page - 1) * page_size
        user = request.args.get('user', None)

        if not user:
            return jsonify({"error": "User parameter is required"}), 400

        # MongoDB에서 해당 사용자의 일지들만 가져오기 (페이지네이션)
        user_diaries = list(diaries.find({"name": user}).sort('date', -1).skip(skip).limit(page_size))

        # ObjectId를 문자열로 변환 (JSON 직렬화 가능하게) 및 이미지 처리
        for diary in user_diaries:
            diary['_id'] = str(diary['_id'])

            # GridFS에서 이미지를 가져와서 Base64로 변환
            if diary.get('diary_photo'):
                try:
                    photo_id = diary['diary_photo']
                    if ObjectId.is_valid(photo_id):
                        print(f"Trying to fetch photo with id: {photo_id}")
                        # GridFS에서 파일을 찾기
                        file = fs_diary.get(ObjectId(photo_id))  # fs_diary를 사용
                        print(f"Photo {photo_id} found in GridFS.")
                        # 파일 데이터를 Base64로 인코딩
                        base64_data = base64.b64encode(file.read()).decode('utf-8')
                        # Base64 데이터를 diary_photo 필드에 저장
                        diary['diary_photo'] = base64_data
                    else:
                        print(f"Invalid ObjectId for photo: {photo_id}")
                        diary['diary_photo'] = None  # 잘못된 ObjectId 처리
                except NoFile:
                    print(f"Error retrieving photo {photo_id}: File not found")
                    diary['diary_photo'] = None  # 이미지가 없는 경우 처리
                except GridFSError as e:
                    print(f"GridFS Error retrieving photo {photo_id}: {str(e)}")
                    diary['diary_photo'] = None  # GridFS 관련 에러 처리
                except Exception as e:
                    print(f"Error retrieving photo {photo_id}: {str(e)}")
                    diary['diary_photo'] = None  # 기타 에러 발생 시 None으로 설정

        return jsonify(user_diaries), 200

    except Exception as e:
        print(f"Server Error: {str(e)}")  # 에러 메시지 출력
        return jsonify({"error": str(e)}), 500


@diary_bp.route('/api/get_diary_entries', methods=['GET'])
def get_diary_entries():
    try:
        # 페이지네이션 쿼리 매개변수 받기
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        skip = (page - 1) * page_size

        # MongoDB에서 모든 일지 가져오기 (페이지네이션)
        all_diaries = list(diaries.find().skip(skip).sort('date', -1).limit(page_size))

        # ObjectId를 문자열로 변환하고, 사진 처리
        for diary in all_diaries:
            diary['_id'] = str(diary['_id'])
            
            # diary_photo가 존재할 때만 GridFS에서 이미지 가져오기
            if diary.get('diary_photo'):
                try:
                    photo_file = fs_diary.get(ObjectId(diary['diary_photo']))
                    diary['diary_photo'] = base64.b64encode(photo_file.read()).decode('utf-8')
                except gridfs.errors.NoFile:
                    diary['diary_photo'] = None  # 파일이 없는 경우

        return jsonify(all_diaries), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

