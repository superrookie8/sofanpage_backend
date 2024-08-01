from flask import Flask, Blueprint, jsonify, current_app
from datetime import datetime, timedelta

news_bp = Blueprint('news_bp' , __name__)

@news_bp.route('/api/latest')
def get_latest_articles():
    db = current_app.config['db']
    news_rookie = db['news_rookie']
    news_jumpball = db['news_jumpball']

    latest_rookie = news_rookie.find_one(
        {'image_url':{'$exists':True, '$ne':None}},
        sort=[('created_at', -1)]
    )

    latest_jumpball = news_jumpball.find_one(
        {'image_url':{'$exists':True, '$ne':None}},
        sort=[('created_at', -1)]
    )

    main_article = latest_rookie if latest_rookie['created_at'] > latest_jumpball['created_at'] else latest_jumpball

    rookie_articles = list(news_rookie.find().sort('created_at', -1))
    jumpball_articles = list(news_jumpball.find().sort('created_at', -1))

    data = {
        'main_article': {
            'title' : main_article['title'],
            'link' : main_article['link'],
            'summary' : main_article['summary'],
            'image_url' : main_article['image_url'],
            'created_at' : main_article['created_at']
        },
        'rookie_article': [
            {'title':article['title'], 'link':article['link'], 'summary':article['summary'], 'image_url':article.get('image_url')}
            for article in rookie_articles
        ],
        'jumpball_article' :[ 
           {'title':article['title'], 'link':article['link'], 'summary':article['summary'], 'image_url':article.get('image_url')}
            for article in jumpball_articles 
        ]
    }

    return jsonify(data)