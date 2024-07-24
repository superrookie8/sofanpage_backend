from flask import Blueprint, request, jsonify
from database import admin_stats

stats_bp = Blueprint('stats_bp', __name__)

@stats_bp.route('/api/admin/get/stats', methods=['GET'])
def get_stats():
    try:
        stats = list(admin_stats.find({}).sort([("season", -1)]))
        for stat in stats:
            stat['_id'] = str(stat['_id'])
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"status": "Failed to fetch stats", "error": str(e)}), 500
