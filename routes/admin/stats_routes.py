from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from database import admin_stats
from .admin_routes import admin_required

admin_stats_bp = Blueprint('admin_stats_bp', __name__)

@admin_stats_bp.route('/api/admin/create_update_stats', methods=['POST'])
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
        admin_stats.update_one({"season": season}, {"$set": stats_data}, upsert=True)
        return jsonify({"status": "Stats created or updated"}), 200
    except Exception as e:
        return jsonify({"status": "Failed to create or update stats", "error": str(e)}), 500

@admin_stats_bp.route('/api/admin/get/stats', methods=['GET'])
def get_stats():
    try:
        stats = list(admin_stats.find({}).sort([("season", -1)]))
        for stat in stats:
            stat['_id'] = str(stat['_id'])
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"status": "Failed to fetch stats", "error": str(e)}), 500
