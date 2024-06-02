from flask import Flask, jsonify, request, send_from_directory
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from pymongo.mongo_client import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import timedelta
from bson import ObjectId

import datetime
import certifi
import re
import uuid

import os

load_dotenv()

ca = certifi.where()

app = Flask(__name__)
CORS(app)

#JWT 설정
app.config["JWT_SECRET_KEY"]= os.getenv("JWT_SECRET_KEY")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)  # 1시간 동안 유효
jwt = JWTManager(app)


client = MongoClient(os.getenv("MONGO_URI"),tlsCAFile=certifi.where() )
db = client.fanpage
collection = db['guestbooks_collections']
users = db['users']
admins = db['admin']
profiles = db['admin_profile']
admin_stats = db['admin_stats']
news = db['admin_news']
schedules = db['admin_schedules']



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



@app.route('/api/admin/create_or_update/stats', methods=['POST'])
@admin_required
def create_update_stats():
    try:
        data = request.json
        season = data.get("season")
        stats_data = {
            "season": season,
            "average": data.get("average", {}),
            "total": data.get("total", {})
        }
        # 시즌별로 데이터 업데이트 또는 생성
        db.admin_stats.update_one({"season": season}, {"$set": stats_data}, upsert=True)
        return jsonify({"status": "Stats created or updated"}), 200
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "Failed to create or update stats", "error": str(e)}), 500

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
        stats = list(db.admin_stats.find({}).sort("season", -1))
        # _id 필드를 문자열로 변환
        for stat in stats:
            stat['_id'] = str(stat['_id'])
        return jsonify(stats), 200
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "Failed to fetch stats", "error": str(e)}), 500



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

if __name__ == '__main__':
    app.run(debug=True)

