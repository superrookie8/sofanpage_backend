from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from database import users
import re

auth_bp = Blueprint('auth', __name__)

def validate_password(password):
    if len(password) < 8 or len(password) > 16:
        return False
    if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password) is None:
        return False 
    return True       

@auth_bp.route('/api/sign_up', methods=['POST'])
def sign_up():
    nickname = request.json.get('nickname', None)
    password = request.json.get('password', None)
    passwordConfirm = request.json.get('passwordConfirm', None)

    if not validate_password(password):
        return jsonify({"msg": "비밀번호는 특수문자를 포함한 8-16자 입니다"}), 400

    if password != passwordConfirm:
        return jsonify({"msg": "비밀번호가 맞지 않습니다"}), 400

    if users.find_one({"nickname": nickname}):
        return jsonify({"msg": "이미 존재하는 닉네임입니다"}), 409

    hashed_password = generate_password_hash(password)
    user_id = users.insert_one({
        "nickname": nickname,
        "password": hashed_password,
        "description": "",  # 초기 가입 시 description을 빈 문자열로 설정
        "photo": ""  # 초기 가입 시 photo를 빈 문자열로 설정
    }).inserted_id

    return jsonify({"msg": "환영합니다!"}), 201

@auth_bp.route('/api/login', methods=['POST'])
def login():
    nickname = request.json.get('nickname', None)
    password = request.json.get('password', None)
    user = users.find_one({"nickname": nickname})
    
    if user and check_password_hash(user['password'], password):
        access_token = create_access_token(identity=nickname)
        return jsonify(access_token=access_token), 200
    else:
        return jsonify({"msg":"닉네임이나 비밀번호가 맞지 않습니다"}), 401

@auth_bp.route('/api/nickname_check', methods=['POST'])
def nickname_check():
    data = request.get_json()
    nickname = data.get('nickname')
    if users.find_one({"nickname": nickname}):
        return jsonify({"msg": "이미 존재하는 닉네임입니다"}), 409
    else:
        return jsonify({"msg": "가능한 닉네임입니다"}), 200
