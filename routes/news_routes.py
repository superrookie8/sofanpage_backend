from flask import Blueprint, jsonify, current_app
from datetime import datetime, timedelta

news_bp = Blueprint('news_bp', __name__)

@news_bp.route('/api/latest', methods=['GET'])
def get_latest_news():
    db = current_app.config['db']
    news_rookie = db['news_rookie']
    news_jumpball = db['news_jumpball']

    latest_rookie = news_rookie.find_one(
        {'image_url': {'$exists': True, '$ne': None}},
        sort=[('created_at', -1)]
    )

    latest_jumpball = news_jumpball.find_one(
        {'image_url': {'$exists': True, '$ne': None}},
        sort=[('created_at', -1)]
    )

    if latest_rookie and latest_jumpball:
        main_article = latest_rookie if latest_rookie['created_at'] > latest_jumpball['created_at'] else latest_jumpball
    elif latest_rookie:
        main_article = latest_rookie
    elif latest_jumpball:
        main_article = latest_jumpball
    else:
        return jsonify({'error': 'No articles found'}), 404

    data = {
        'main_article': {
            'title': main_article['title'],
            'link': main_article['link'],
            'summary': main_article['summary'],
            'image_url': main_article['image_url'],
            'created_at': main_article['created_at']
        }
    }

    return jsonify(data)
