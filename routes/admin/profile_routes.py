from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from database import profiles
import datetime

profile_bp = Blueprint('profile_bp', __name__)

@profile_bp.route('/api/admin/create_or_update/profile', methods=['POST'])
@jwt_required()
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
        profiles.update_one({}, {"$set": profile_data}, upsert=True)
        return jsonify({"status": "Profile created or updated"}), 200
    except Exception as e:
        return jsonify({"status": "Failed to create or update profile", "error": str(e)}), 500

@profile_bp.route('/api/admin/get/profile', methods=['GET'])
def get_profile():
    try:
        profile = profiles.find_one({}, {"_id": 0})
        if not profile:
            return jsonify({"status": "Profile not found"}), 404
        return jsonify(profile), 200
    except Exception as e:
        return jsonify({"status": "Failed to get profile", "error": str(e)}), 500
