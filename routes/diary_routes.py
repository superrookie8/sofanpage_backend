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


@diary_bp.route('/api/user_stats', methods=['GET'])
def get_user_stats():
    try:
        # 사용자 닉네임을 파라미터로 받아옴
        nickname = request.args.get('nickname')

        # 현재 날짜
        today = datetime.now()

        # 현재 시즌의 시작일과 끝일 계산 (5월 1일 ~ 다음 해 4월 30일)
        if today.month >= 5:
            season_start = datetime(today.year, 5, 1)
            season_end = datetime(today.year + 1, 4, 30)
        else:
            season_start = datetime(today.year - 1, 5, 1)
            season_end = datetime(today.year, 4, 30)

        # 해당 시즌의 다이어리 항목들 가져오기 (5월 1일부터 다음 해 4월 30일까지)
        user_diaries = list(diaries.find({
            "name": nickname,
            "date": {"$gte": season_start, "$lte": season_end}
        }))

        total_games_watched = len(user_diaries)  # 사용자가 직관한 총 경기 수
        if total_games_watched == 0:
            return jsonify({"message": "No games found for the user."}), 404

        # 총 경기 수 (1년 160경기 기준)
        total_season_games = 160

        # 홈 경기 장소 목록
        HOME_LOCATIONS = ["busan", "second", "third"]

        # 승리한 경기 수, 홈 경기 수, 홈 승리 수 등 계산
        win_count = 0
        home_games = 0
        home_wins = 0

        # 맑은 날씨 경기에 대한 카운트
        sunny_count = 0

        for diary in user_diaries:
            location = diary['location']
            win_status = diary['win_status']
            weather = diary['weather']

            # 홈 경기 여부 판단
            is_home_game = location in HOME_LOCATIONS

            if win_status == "win":  # 승리한 경기
                win_count += 1
                if is_home_game:
                    home_wins += 1

            if is_home_game:
                home_games += 1

            # 맑은 날씨 경기를 카운트
            if weather == 'sunny':
                sunny_count += 1

        # 원정 경기 관련 데이터
        away_games = total_games_watched - home_games
        away_wins = win_count - home_wins

        # 맑은 날씨 퍼센트 계산
        sunny_percentage = round((sunny_count / total_games_watched) * 100, 1) if total_games_watched > 0 else 0

        # 승률, 홈 경기 승률, 원정 경기 승률 계산 (직관한 경기만 기준으로 계산)
        win_percentage = round((win_count / total_games_watched) * 100, 1) if total_games_watched > 0 else 0
        home_win_percentage = round((home_wins / home_games) * 100, 1) if home_games > 0 else 0
        away_win_percentage = round((away_wins / away_games) * 100, 1) if away_games > 0 else 0

        # 총경기수 대비 직관 경기 비율 계산
        attendance_percentage = round((total_games_watched / total_season_games) * 100, 1)

        # 결과 데이터 반환
        data = {
            "nickname": nickname,
            "total_games_watched": total_games_watched,
            "win_percentage": win_percentage,
            "home_win_percentage": home_win_percentage,
            "away_win_percentage": away_win_percentage,
            "sunny_percentage": sunny_percentage,  # 맑은 날씨 비율
            "attendance_percentage": attendance_percentage,  # 총경기 대비 직관 횟수 비율
            "season": f"{season_start.year}-{season_end.year}"  # 시즌 정보 추가
        }

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


