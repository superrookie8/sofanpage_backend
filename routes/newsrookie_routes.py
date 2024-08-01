from flask import Blueprint, request, jsonify, current_app
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

newsrookie_bp = Blueprint('newsrookie_bp', __name__)

def crawl_data(query):
    base_url = 'https://www.rookie.co.kr/news/articleList.html'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    total_pages = 47  # 크롤링할 총 페이지 수
    articles = []

    for page in range(1, total_pages + 1):
        params = {
            'sc_word': query,
            'view_type': 'sm',
            'page': page
        }
        print(f"Crawling page {page}")
        response = requests.get(base_url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Failed to retrieve data for page {page}: {response.status_code}")
            continue
        
        soup = BeautifulSoup(response.content, 'html.parser')
        page_articles = 0
        for item in soup.select('#section-list > ul > li'):
            title_tag = item.select_one('.titles a')
            summary_tag = item.select_one ('.lead a')
            if title_tag:
                title = title_tag.text.strip()
                summary = summary_tag.text.strip()
                if query in title or query in summary:
                    print(f"Found title: {title}")
                    link = 'https://www.rookie.co.kr' + title_tag['href']

                    image_tag = item.select_one('.thumb img')
                    image_url = image_tag['src'] if image_tag else None
                    
                    article = {
                        'title' : title, 
                        'link' : link,
                        'summary' : summary,
                        'image_url' :image_url,
                        'created_at' : datetime.utcnow()
                    }
                    
                    articles.append(article)
                    page_articles += 1
        print(f"Articles found on page {page} from Rookie: {page_articles}")

    if articles:
        db = current_app.config['db']
        news_rookie = db['news_rookie']
        news_rookie.insert_many(articles)

    return articles    

@newsrookie_bp.route('/api/rookie/search/')
def search_rookie():
    query = request.args.get('q')
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400

    db = current_app.config['db']
    news_rookie = db['news_rookie']
    two_months_ago = datetime.utcnow() - timedelta(days=60)
    articles = news_rookie.find({
        '$or': [
            {'title':{'$regex':query, '$options':'i'}}, {'summary':{'$regex':query, '$options':'i'}}
        ]
    }).sort('created_at', -1)
    data = [{'title':article['title'], 'link':article['link'], 'summary':article['summary'], 'image_url':article.get('image_url')} for article in articles]

    last_crawl = news_rookie.find_one(sort =[("created_at", -1)])
    if not last_crawl or last_crawl['created_at'] < two_months_ago:
        new_data = crawl_data(query)
        if new_data : 
            new_data = [{'title' : article['title'], 'link':article['link'], 'summary':article['summary'], 'image_url':article.get('image_url')} for article in new_data]
            data = new_data + data

    return jsonify(data)
