from flask import Blueprint, jsonify
from database import schedules

schedule_bp = Blueprint('schedule', __name__)

@schedule_bp.route('/api/get_schedules', methods=['GET'])
def get_user_schedules():
    try:
        schedule_list = []
        for schedule in schedules.find():
            schedule['_id'] = str(schedule['_id'])
            schedule_list.append(schedule)
        return jsonify(schedule_list), 200
    except Exception as e:
        print(f"Error: {str(e)}")  # 디버깅용 로그
        return jsonify({"message": str(e)}), 500
