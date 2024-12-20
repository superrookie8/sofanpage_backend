from flask import Blueprint, request, jsonify, session, Flask, current_app
from database import fs_diary, diaries
from bson import ObjectId
from gridfs import GridFS, errors as gridfs_errors
from datetime import datetime
from flask_cors import CORS
import base64
from gridfs.errors import NoFile, GridFSError  # Add GridFSError import
from flask_jwt_extended import jwt_required, get_jwt_identity  # Add this import
import boto3

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
        section = request.form.get("section", "")
        row = request.form.get("row", "")
        number = request.form.get("number", "")
        message = request.form.get("message", "")

        # 사진 파일 받아오기
        ticket_photo = request.files.get('ticket_photo')
        view_photo = request.files.get('view_photo')
        additional_photo = request.files.get('additional_photo')

        # 필수 사진 확인
        if not ticket_photo or not view_photo:
            return jsonify({"error": "Ticket photo and view photo are required"}), 400

        # GridFS에 이미지 저장
        photo_ids = {}
        try:
            photo_ids['ticket_photo'] = fs_diary.put(ticket_photo, filename=f"{name}_ticket_{date}.jpg")
            photo_ids['view_photo'] = fs_diary.put(view_photo, filename=f"{name}_view_{date}.jpg")
            if additional_photo:
                photo_ids['additional_photo'] = fs_diary.put(additional_photo, filename=f"{name}_additional_{date}.jpg")
        except gridfs_errors.GridFSError as e:
            return jsonify({"error": "Failed to save photos"}), 500

        # location에 따른 홈경기 여부 자동 설정
        is_home_game = location in HOME_LOCATIONS

        # 현재 시간(데이터가 저장된 시간) 추가
        saved_at = datetime.now()

        # diaries 컬렉션에 저장할 데이터
        diary_entry = {
            "name": name,
            "date": datetime.strptime(date, '%Y-%m-%d'),
            "weather": weather,
            "location": location,
            "together": together,
            "win_status": win_status,
            "is_home_game": is_home_game,
            "diary_photos": photo_ids,
            "diary_message": message,
            "saved_at": saved_at,
            "seat_info": {
                "section": section,
                "row": row,
                "number": number
            }
        }

        # MongoDB에 다이어리 데이터 저장
        result = diaries.insert_one(diary_entry)
        return jsonify({"message": "Diary entry created successfully", "id": str(result.inserted_id)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@diary_bp.route('/api/get_diary_personal', methods=['GET'])
def get_diary_personal():
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        skip = (page - 1) * page_size
        user = request.args.get('user', None)

        if not user:
            return jsonify({"error": "User parameter is required"}), 400

        # saved_at 기준으로 정렬 변경 (-1은 내림차순, 즉 최신순)
        user_diaries = list(diaries.find({"name": user}).sort('saved_at', -1).skip(skip).limit(page_size))

        # ObjectId를 문자열로 변환 (JSON 직렬화 가능하게) 및 이미지 처리
        for diary in user_diaries:
            diary['_id'] = str(diary['_id'])

            # GridFS에서 이미지를 가져와서 Base64로 변환
            if diary.get('diary_photos'):
                for photo_type, photo_id in diary['diary_photos'].items():
                    try:
                        photo_file = fs_diary.get(ObjectId(photo_id))
                        diary['diary_photos'][photo_type] = base64.b64encode(photo_file.read()).decode('utf-8')
                    except (NoFile, GridFSError) as e:
                        print(f"Error retrieving {photo_type} {photo_id}: {str(e)}")
                        diary['diary_photos'][photo_type] = None

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

        # saved_at 기준으로 정렬 변경
        all_diaries = list(diaries.find().sort('saved_at', -1).skip(skip).limit(page_size))

        for diary in all_diaries:
            diary['_id'] = str(diary['_id'])

            # diary_photos가 존재할 때만 GridFS에서 이미지 가져오기
            if 'diary_photos' in diary:
                for photo_type, photo_id in diary['diary_photos'].items():
                    try:
                        file = fs_diary.get(ObjectId(photo_id))
                        base64_data = base64.b64encode(file.read()).decode('utf-8')
                        diary['diary_photos'][photo_type] = base64_data
                    except (NoFile, GridFSError) as e:
                        print(f"Error retrieving {photo_type} {photo_id}: {str(e)}")
                        diary['diary_photos'][photo_type] = None

            # datetime 객체를 문자열로 변환
            if 'date' in diary:
                diary['date'] = diary['date'].strftime('%Y-%m-%d')
            if 'saved_at' in diary:
                diary['saved_at'] = diary['saved_at'].isoformat()

        return jsonify(all_diaries), 200

    except Exception as e:
        print(f"Server Error: {str(e)}")
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


@diary_bp.route('/api/delete_diary', methods=['DELETE'])
@jwt_required()
def delete_diary():
    try:
        nickname = get_jwt_identity()
        entry_id = request.args.get('entry_id')

        if not entry_id:
            return jsonify({"error": "Entry ID is required"}), 400

        # Check if the diary entry exists and belongs to the user
        diary_entry = diaries.find_one({"_id": ObjectId(entry_id), "name": nickname})
        if not diary_entry:
            return jsonify({"error": "Diary entry not found or you do not have permission to delete it"}), 404

        # Delete the diary entry
        diaries.delete_one({"_id": ObjectId(entry_id)})

        # If the diary entry has a photo, delete it from GridFS
        if diary_entry.get('diary_photos'):
            for photo_type, photo_id in diary_entry['diary_photos'].items():
                try:
                    fs_diary.delete(ObjectId(photo_id))
                except gridfs_errors.NoFile:
                    pass  # If the file is not found, ignore the error

        return jsonify({"message": "Diary entry deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@diary_bp.route('/api/test_s3_connection', methods=['GET'])
def test_s3_connection():
    try:
        # S3 클라이언트 생성
        s3_client = boto3.client(
            's3',
            aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
            region_name=current_app.config['AWS_S3_REGION']
        )
        
        # 버킷 리스트 가져오기 시도
        response = s3_client.list_buckets()
        
        # 설정된 버킷이 존재하는지 확인
        buckets = [bucket['Name'] for bucket in response['Buckets']]
        target_bucket = current_app.config['AWS_S3_BUCKET']
        
        if target_bucket in buckets:
            return jsonify({
                "status": "success",
                "message": "Successfully connected to S3",
                "bucket_exists": True,
                "bucket_name": target_bucket,
                "all_buckets": buckets
            }), 200
        else:
            return jsonify({
                "status": "warning",
                "message": "Connected to S3, but target bucket not found",
                "bucket_exists": False,
                "bucket_name": target_bucket,
                "all_buckets": buckets
            }), 200
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to connect to S3: {str(e)}"
        }), 500