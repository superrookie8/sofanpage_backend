from flask import Flask, jsonify, request, send_from_directory
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from pymongo.mongo_client import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import timedelta, datetime as dt
from bson import ObjectId
import gridfs
from werkzeug.utils import secure_filename
import base64
import datetime
import certifi
import re
import uuid

import os

load_dotenv()

ca = certifi.where()


app = Flask(__name__)
CORS(app)

# 파일이 저장될 업로드 폴더 경로를 설정하고 생성합니다.
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


#JWT 설정
app.config["JWT_SECRET_KEY"]= os.getenv("JWT_SECRET_KEY")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)  # 1시간 동안 유효
jwt = JWTManager(app)


client = MongoClient(os.getenv("MONGO_URI"),tlsCAFile=certifi.where() )
db = client.fanpage
fs_admin = gridfs.GridFS(db, collection='admin_photo')
fs_user = gridfs.GridFS(db, collection='user_photo')
fs_event = gridfs.GridFS(db, collection="event_photo")
collection = db['guestbooks_collections']
users = db['users']
admins = db['admin']
profiles = db['admin_profile']
admin_stats = db['admin_stats']
news = db['admin_news']
schedules = db['admin_schedules']
events = db['admin_events']



@app.route ('/')
def home() : 
    return ('잘되고 있어!')


def validate_password(password):
    if len(password) < 8 or len(password) > 16:
        return False
    if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password) is None:
        return False 
    return True       


@app.route ('/api/sign_up', methods=['POST'])
def sign_up() :
    nickname = request.json.get('nickname', None)
    password = request.json.get('password', None)
    passwordConfirm = request.json.get('passwordConfirm', None)

    if not validate_password(password):
        return jsonify({"msg":"비밀번호는 특수문자를 포함한 8-16자 입니다"})

    if password != passwordConfirm:
        return jsonify({"msg": "비밀번호가 맞지 않습니다"}), 400

    if users.find_one({"nickname": nickname}):
        return jsonify({"msg":"이미 존재하는 닉네임입니다"}), 409

    hashed_password = generate_password_hash(password)
    users.insert_one({"nickname": nickname, "password" : hashed_password})        
    return jsonify({"msg" : "환영합니다!"}), 201

@app.route ('/api/login', methods = ['POST'])
def login() :
    nickname = request.json.get('nickname', None)
    password = request.json.get('password', None)
    user = users.find_one({"nickname": nickname})
    
    if user and check_password_hash(user['password'], password):
        access_token = create_access_token(identity=nickname)
        return jsonify(access_token=access_token), 200
    else:
        return jsonify({"msg":"닉네임이나 비밀번호가 맞지 않습니다"}), 401


@app.route('/api/nickname_check', methods=['POST'])
def nickname_check():
    data = request.get_json()
    nickname = data.get('nickname')
    if db.users.find_one({"nickname": nickname}):
        return jsonify({"msg": "이미 존재하는 닉네임입니다"}), 409
    else:
        return jsonify({"msg": "가능한 닉네임입니다"}), 200


@app.route('/api/create', methods=['POST'])
def insert_data():
    data = request.json
    post = {
        "nickname": data.get("nickname", "Anonymous"),  # 기본값으로 "Anonymous" 설정
        "text": data.get("text", ""),
        "date": datetime.datetime.utcnow()
    }
    collection.insert_one(post)
    return jsonify({"status": "Data inserted"}), 200

@app.route('/api/fetch')
def fetch_data():
    user_name = request.args.get('user', '하나')  # 쿼리 파라미터로 유저 이름 받기, 기본값 '하나'
    data = collection.find_one({"user": user_name})
    return jsonify(data), 200     

@app.route('/api/get/events', methods=['GET'])
def get_events():
    try:
        events = list(db.admin_events.find({}))
        for event in events:
            event["_id"] = str(event["_id"])  # ObjectId를 문자열로 변환
            if "check_1" in event or "check_2" in event or "check_3" in event:
                check_fields = {
                    "check_1": event.get("check_1", ""),
                    "check_2": event.get("check_2", ""),
                    "check_3": event.get("check_3", "")
                }
                event["checkFields"] = check_fields

            if "photos" in event:
                photo_ids = event["photos"]
                photos = []
                for photo_id in photo_ids:
                    try:
                        photo_file = fs_event.get(ObjectId(photo_id))
                        photo_data = base64.b64encode(photo_file.read()).decode('utf-8')
                        photos.append(f"data:{photo_file.content_type};base64,{photo_data}")
                    except gridfs.errors.NoFile:
                        continue
                event["photos"] = photos
            else:
                event["photos"] = []

        return jsonify({"events": events}), 200
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"message": str(e)}), 500    


@app.route('/api/get/photos', methods=['GET'])
def get_photos_public():
    try:
        # Fetch photos from admin collection
        admin_photos = fs_admin.find()
        admin_photo_list = []
        for photo in admin_photos:
            # Read image data and encode in base64
            image_data = fs_admin.get(photo._id).read()
            base64_img = base64.b64encode(image_data).decode('utf-8')
            data_url = f"data:image/jpeg;base64,{base64_img}"  # Assuming the image type is JPEG
            admin_photo_list.append({
                "_id": str(photo._id),
                "filename": photo.filename,
                "base64": data_url,
                "url": f"/api/photos/{photo._id}"
            })

        # Fetch photos from user collection
        user_photos = fs_user.find()
        user_photo_list = []
        for photo in user_photos:
            # Read image data and encode in base64
            image_data = fs_user.get(photo._id).read()
            base64_img = base64.b64encode(image_data).decode('utf-8')
            data_url = f"data:image/jpeg;base64,{base64_img}"  # Assuming the image type is JPEG
            user_photo_list.append({
                "_id": str(photo._id),
                "filename": photo.filename,
                "base64": data_url,
                "url": f"/api/photos/{photo._id}"
            })

        return jsonify({"admin_photos": admin_photo_list, "user_photos": user_photo_list}), 200

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "Failed", "message": str(e)}), 500

          

# 관리자 전용 엔드포인트
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    username = request.json.get('username', None)
    password = request.json.get('password', None)
    admin = admins.find_one({"username": username})  # 관리자 컬렉션에서 조회
    
    if admin and check_password_hash(admin['password'], password):
        access_token = create_access_token(identity={"username": username, "role": "admin"})
        return jsonify(access_token=access_token), 200
    else:
        return jsonify({"msg": "관리자 계정이 아니거나 비밀번호가 맞지 않습니다"}), 401

def admin_required(fn):
    @jwt_required()
    def wrapper(*args, **kwargs):
        identity = get_jwt_identity()
        if identity["role"] != "admin":
            return jsonify({"msg": "관리자 권한이 필요합니다"}), 403
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__  # 함수 이름을 동일하게 유지
    return wrapper

@app.route('/api/admin/protected', methods=['GET'])
@admin_required
def admin_protected():
    return jsonify({"msg": "관리자 전용 데이터"}), 200        

@app.route('/api/admin/refresh-token', methods=['POST'])
@jwt_required(refresh=True)
def refresh_token():
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return jsonify(access_token=access_token), 200


@app.route('/api/admin/create_or_update/profile', methods=['POST'])
@admin_required
def admin_create_or_update_profile():
    try:
        data = request.json
        profile_data = {
            "name": data.get("name", "Anonymous"),
            "team": data.get("team", ""),
            "position": data.get("position", ""),
            "number": data.get("number", ""),
            "height": data.get("height", ""),
            "nickname": data.get("nickname", ""),
            "features": data.get("features", ""),
            "date": datetime.datetime.utcnow()
        }
        profiles.update_one({}, {"$set": profile_data}, upsert=True)  # 프로필 데이터 업데이트, 없으면 새로 생성
        return jsonify({"status": "Profile created or updated"}), 200
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "Failed to create or update profile", "error": str(e)}), 500



@app.route('/api/admin/create_update_stats', methods=['POST'])
@admin_required
def create_update_stats():
    try:
        data = request.json
        season = data.get("season")
        stats_data = {
            "season": season,
            "average": {
                "G": data["average"]["G"],
                "MPG": data["average"]["MPG"],
                "2P%": data["average"]["2P%"],
                "3P%": data["average"]["3P%"],
                "FT": data["average"]["FT"],
                "OFF": data["average"]["OFF"],
                "DEF": data["average"]["DEF"],
                "TOT": data["average"]["TOT"],
                "APG": data["average"]["APG"],
                "SPG": data["average"]["SPG"],
                "BPG": data["average"]["BPG"],
                "TO": data["average"]["TO"],
                "PF": data["average"]["PF"],
                "PPG": data["average"]["PPG"]
            },
            "total": {
                "MIN": data["total"]["MIN"],
                "FGM-A": data["total"]["FGM-A"],
                "3PM-A": data["total"]["3PM-A"],
                "FTM-A": data["total"]["FTM-A"],
                "OFF": data["total"]["OFF"],
                "DEF": data["total"]["DEF"],
                "TOT": data["total"]["TOT"],
                "AST": data["total"]["AST"],
                "STL": data["total"]["STL"],
                "BLK": data["total"]["BLK"],
                "TO": data["total"]["TO"],
                "PF": data["total"]["PF"],
                "PTS": data["total"]["PTS"]
            }
        }
        db.admin_stats.update_one({"season": season}, {"$set": stats_data}, upsert=True)
        return jsonify({"status": "Stats created or updated"}), 200
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "Failed to create or update stats", "error": str(e)}), 500

@app.route('/api/admin/postphoto', methods=['POST'])
@jwt_required()
def post_photo():
    try:
        files = request.files.getlist("photos")
        for file in files:
            fs_admin.put(file, filename=file.filename, content_type=file.content_type)
        return jsonify({"message": "Photos uploaded successfully"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route('/api/admin/create/news', methods=['POST'])
@admin_required
def admin_create_news():
    data = request.json
    news_data = {
        "title": data.get("title", ""),
        "content": data.get("content", ""),
        "date": datetime.datetime.utcnow()
    }
    news.insert_one(news_data)
    return jsonify({"status": "News created"}), 200

@app.route('/api/admin/create/schedule', methods=['POST'])
@admin_required
def admin_create_schedule():
    data = request.json
    schedule = {
        "event": data.get("event", ""),
        "date": data.get("date", ""),
        "location": data.get("location", "")
    }
    schedules.insert_one(schedule)
    return jsonify({"status": "Schedule created"}), 200   


@app.route('/api/admin/postevents', methods=['POST'])
@jwt_required()
def post_events():
    try:
        # 이벤트 데이터 추출
        title = request.form.get('title', '')
        url = request.form.get('url', '')
        description = request.form.get('description', '')

        # 체크 필드들을 동적으로 처리
        check_fields = {}
        for key in request.form.keys():
            if key.startswith('check_'):
                check_fields[key] = request.form.get(key, '')

        event_data = {
            "title": title,
            "url": url,
            "description": description,
            "date": datetime.datetime.utcnow(),
            **check_fields  # 체크 필드 추가
        }

        event_id = db.admin_events.insert_one(event_data).inserted_id

        # 사진 파일 처리
        files = request.files.getlist("photos")
        photo_ids = []
        for file in files:
            file_id = fs_event.put(file, filename=file.filename, content_type=file.content_type)
            photo_ids.append(str(file_id))

        # 이벤트 문서에 사진 파일 ID 추가
        db.admin_events.update_one(
            {"_id": event_id},
            {"$set": {"photos": photo_ids}}
        )

        return jsonify({"message": "Event and photos uploaded successfully"}), 200
    except Exception as e:
        print(f"Error: {str(e)}")  # 에러 메시지 출력
        return jsonify({"message": str(e)}), 500








@app.route('/api/admin/get/profile', methods=['GET'])
def get_profile():
    try:
        profile = profiles.find_one({}, {"_id": 0})  # 첫 번째 프로필을 가져옴, _id는 제외
        if not profile:
            return jsonify({"status": "Profile not found"}), 404
        return jsonify(profile), 200
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "Failed to get profile", "error": str(e)}), 500


@app.route('/api/admin/get/stats', methods=['GET'])
def get_stats():
    try:
        stats = list(db.admin_stats.find({}).sort([("season", -1)]))
        # _id 필드를 문자열로 변환
        for stat in stats:
            stat['_id'] = str(stat['_id'])
        return jsonify(stats), 200
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "Failed to fetch stats", "error": str(e)}), 500


@app.route('/api/admin/get/photo/<photo_id>', methods=['GET'])
@jwt_required()
def get_photo(photo_id):
    try:
        # First, try to get the photo from the admin collection
        try:
            file = fs_admin.get(ObjectId(photo_id))
        except gridfs.errors.NoFile:
            # If not found in admin collection, try to get it from the user collection
            file = fs_user.get(ObjectId(photo_id))

        # Read the data from the file
        data = file.read()

        # Create a response with the image data
        response = make_response(data)
        response.headers.set('Content-Type', file.content_type)
        response.headers.set('Content-Disposition', 'inline', filename=file.filename)
        
        return response

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "Failed", "message": str(e)}), 500

@app.route('/api/admin/get/photos', methods=['GET'])
@jwt_required()  # Ensure only authorized users can access this endpoint
def get_photos():
    try:
        token = request.headers.get('Authorization').split()[1]
        # Fetch photos from admin collection
        admin_photos = fs_admin.find()
        admin_photo_list = []
        for photo in admin_photos:
            # Read image data and encode in base64
            image_data = fs_admin.get(photo._id).read()
            base64_img = base64.b64encode(image_data).decode('utf-8')
            data_url = f"data:image/jpeg;base64,{base64_img}"  # Assuming the image type is JPEG
            admin_photo_list.append({
                "_id": str(photo._id),
                "filename": photo.filename,
                "base64": data_url,
                "url": f"/api/admin/get/photo/{photo._id}?token={token}"
            })

        # Fetch photos from user collection
        user_photos = fs_user.find()
        user_photo_list = []
        for photo in user_photos:
            # Read image data and encode in base64
            image_data = fs_user.get(photo._id).read()
            base64_img = base64.b64encode(image_data).decode('utf-8')
            data_url = f"data:image/jpeg;base64,{base64_img}"  # Assuming the image type is JPEG
            user_photo_list.append({
                "_id": str(photo._id),
                "filename": photo.filename,
                "base64": data_url,
                "url": f"/api/admin/get/photo/{photo._id}?token={token}"
            })

        return jsonify({"admin_photos": admin_photo_list, "user_photos": user_photo_list}), 200

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "Failed", "message": str(e)}), 500

@app.route('/api/admin/deletephoto', methods=['DELETE'])
@jwt_required()
def delete_photos():
    try:
        data = request.get_json()
        photo_ids = data.get('photoIds', [])
        
        if not photo_ids:
            return jsonify({"message": "No photo IDs provided"}), 400

        for photo_id in photo_ids:
            if fs_admin.exists({"_id": ObjectId(photo_id)}):
                fs_admin.delete(ObjectId(photo_id))
            elif fs_user.exists({"_id": ObjectId(photo_id)}):
                fs_user.delete(ObjectId(photo_id))
            else:
                return jsonify({"message": f"Photo with ID {photo_id} does not exist"}), 404

        return jsonify({"message": "Photos deleted successfully"}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"message": "Failed to delete photos", "error": str(e)}), 500

@app.route('/api/get/photos/<photo_id>', methods=['GET'])
def get_photo_public(photo_id):
    try:
        # First, try to get the photo from the admin collection
        try:
            file = fs_admin.get(ObjectId(photo_id))
        except gridfs.errors.NoFile:
            # If not found in admin collection, try to get it from the user collection
            file = fs_user.get(ObjectId(photo_id))

        # Read the data from the file
        data = file.read()

        # Create a response with the image data
        response = make_response(data)
        response.headers.set('Content-Type', file.content_type)
        response.headers.set('Content-Disposition', 'inline', filename=file.filename)
        
        return response

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "Failed", "message": str(e)}), 500



@app.route('/api/admin/get/events', methods=['GET'])
@jwt_required()
def get_admin_events():
    try:
        events = list(db.admin_events.find({}))
        for event in events:
            event["_id"] = str(event["_id"])  # ObjectId를 문자열로 변환
            if "check_1" in event or "check_2" in event or "check_3" in event:
                check_fields = {
                    "check_1": event.get("check_1", ""),
                    "check_2":
                event.get("check_2", ""),
                    "check_3": event.get("check_3", "")
                }
                event["checkFields"] = check_fields

            if "photos" in event:
                photo_ids = event["photos"]
                photos = []
                for photo_id in photo_ids:
                    try:
                        photo_file = fs_event.get(ObjectId(photo_id))
                        photo_data = base64.b64encode(photo_file.read()).decode('utf-8')
                        photos.append(f"data:{photo_file.content_type};base64,{photo_data}")
                    except gridfs.errors.NoFile:
                        continue
                event["photos"] = photos
            else:
                event["photos"] = []

        return jsonify({"events": events}), 200
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"message": str(e)}), 500







@app.route('/api/admin/delete/eventphoto', methods=['DELETE'])
@jwt_required()
def delete_photo():
    try:
        data = request.get_json()
        event_id = data['eventId']
        photo_index = data['photoIndex']  # 수정된 부분

        # 이벤트를 찾습니다.
        event = db.admin_events.find_one({"_id": ObjectId(event_id)})
        if not event:
            return jsonify({"message": "Event not found"}), 404

        # 사진 ID를 얻습니다.
        photo_id = event['photos'][photo_index]

        # GridFS에서 사진을 삭제합니다.
        fs_event.delete(ObjectId(photo_id))

        # 이벤트에서 사진 ID를 제거합니다.
        db.admin_events.update_one(
            {"_id": ObjectId(event_id)},
            {"$pull": {"photos": photo_id}}
        )

        return jsonify({"message": "Photo deleted successfully"}), 200

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"message": str(e)}), 500




@app.route('/api/admin/delete/event', methods=['DELETE'])
@jwt_required()
def delete_event():
    try:
        data = request.get_json()
        event_id = data['eventId']

        # 이벤트를 찾습니다.
        event = db.admin_events.find_one({"_id": ObjectId(event_id)})
        if not event:
            return jsonify({"message": "Event not found"}), 404

        # 이벤트 내 모든 사진을 삭제합니다.
        if "photos" in event:
            for photo_id in event["photos"]:
                try:
                    fs_event.delete(ObjectId(photo_id))
                except gridfs.errors.NoFile:
                    continue

        # 이벤트를 삭제합니다.
        db.admin_events.delete_one({"_id": ObjectId(event_id)})

        return jsonify({"message": "Event and its photos deleted successfully"}), 200

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"message": str(e)}), 500




if __name__ == '__main__':
    app.run(debug=True)

