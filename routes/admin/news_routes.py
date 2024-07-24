from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from database import news
import datetime

news_bp = Blueprint('news_bp', __name__)

@news_bp.route('/api/admin/create/news', methods=['POST'])
@jwt_required()
def admin_create_news():
    data = request.json
    news_data = {
        "title": data.get("title", ""),
        "content": data.get("content", ""),
        "date": datetime.datetime.utcnow()
    }
    news.insert_one(news_data)
    return jsonify({"status": "News created"}), 200
