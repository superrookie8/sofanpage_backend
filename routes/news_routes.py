from flask import Blueprint, jsonify, current_app
from datetime import datetime, timedelta

news_bp = Blueprint('news_bp', __name__)

@news_bp.route('/api/latest', methods=['GET'])
def get_latest_news():
    db = current_app.config['db']
    news_rookie = db['news_rookie']
    news_jumpball = db['news_jumpball']

    # 'created_at' 필드가 크롤링한 기사 작성 시간을 저장하고 있다면 그대로 사용
    # 그렇지 않다면 기사 작성 시간을 저장하는 필드를 사용해야 함
    latest_rookie = news_rookie.find_one(
        {'image_url': {'$exists': True, '$ne': None}},
        sort=[('created_at', -1)]  # 'created_at' 필드가 기사 작성 시간을 의미해야 함
    )

    latest_jumpball = news_jumpball.find_one(
        {'image_url': {'$exists': True, '$ne': None}},
        sort=[('created_at', -1)]  # 동일하게 기사 작성 시간 기준으로 정렬
    )

    # 최신 기사를 기사 작성 시간을 기준으로 비교
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
            'created_at': main_article['created_at']  # 이 시간은 기사 작성 시간이어야 함
        }
    }

    return jsonify(data)

