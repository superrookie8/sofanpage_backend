from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from werkzeug.security import generate_password_hash, check_password_hash
from database import admins

admin_bp = Blueprint('admin_bp', __name__)

def admin_required(fn):
    @jwt_required()
    def wrapper(*args, **kwargs):
        identity = get_jwt_identity()
        if identity["role"] != "admin":
            return jsonify({"msg": "관리자 권한이 필요합니다"}), 403
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper

@admin_bp.route('/api/admin/login', methods=['POST'])
def admin_login():
    username = request.json.get('username', None)
    password = request.json.get('password', None)
    admin = admins.find_one({"username": username})
    
    if admin and check_password_hash(admin['password'], password):
        access_token = create_access_token(identity={"username": username, "role": "admin"})
        return jsonify(access_token=access_token), 200
    else:
        return jsonify({"msg": "관리자 계정이 아니거나 비밀번호가 맞지 않습니다"}), 401

@admin_bp.route('/api/admin/protected', methods=['GET'])
@admin_required
def admin_protected():
    return jsonify({"msg": "관리자 전용 데이터"}), 200

@admin_bp.route('/api/admin/refresh-token', methods=['POST'])
@jwt_required(refresh=True)
def refresh_token():
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return jsonify(access_token=access_token), 200
