from flask import Blueprint, request, jsonify
from database import schedules
from bson import ObjectId
from .admin_routes import admin_required

admin_schedule_bp = Blueprint('schedule_bp', __name__)

@admin_schedule_bp.route('/api/admin/get/seasons', methods=['GET'])
@admin_required
def get_seasons():
    try:
        seasons = schedules.distinct("season")
        return jsonify(seasons), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500    

@admin_schedule_bp.route('/api/admin/create_update/schedule', methods=['POST'])
@admin_required
def create_or_update_schedule():
    try:
        data = request.json
        schedule_id = data.get("_id")
        schedule_data = {
            "date": data.get("date", ""),
            "opponent": data.get("opponent", ""),
            "isHome": data.get("isHome", False),
            "time": data.get("time", ""),
            "season": data.get("season", "")
        }

        if data.get("extraHome"):
            schedule_data["extraHome"] = data["extraHome"]

        # spacialGame 필드 추가
        if data.get("spacialGame"):
            schedule_data["spacialGame"] = data["spacialGame"]

        if schedule_id:
            schedules.update_one({"_id": ObjectId(schedule_id)}, {"$set": schedule_data})
            message = "Schedule updated"
        else:
            schedule_data["_id"] = ObjectId()
            schedules.insert_one(schedule_data)
            message = "Schedule created"
        
        return jsonify({"status": message}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@admin_schedule_bp.route('/api/admin/get/schedule', methods=['GET'])
def get_schedules():
    try:
        season = request.args.get("season")
        schedule_list = list(schedules.find({"season": season}).sort("date", 1))
        for schedule in schedule_list:
            schedule["_id"] = str(schedule["_id"])
        return jsonify(schedule_list), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@admin_schedule_bp.route('/api/admin/delete/schedule', methods=['DELETE'])
@admin_required
def delete_schedule():
    try:
        data = request.json
        schedule_id = data.get("_id")
        schedules.delete_one({"_id": ObjectId(schedule_id)})
        return jsonify({"status": "Schedule deleted"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500
