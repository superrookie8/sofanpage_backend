from flask import Blueprint, request, jsonify, current_app
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

newsrookie_bp = Blueprint('newsrookie_bp', __name__)

def parse_date(date_string):
    try:
        return datetime.strptime(date_string, "입력 %Y.%m.%d %H:%M")
    except ValueError:
        return None

def crawl_data(query):
    base_url = 'https://www.rookie.co.kr/news/articleList.html'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    total_pages = 47  # 크롤링할 총 페이지 수
    articles = []

    db = current_app.config['db']
    news_rookie = db['news_rookie']
    existing_links = set(article['link'] for article in news_rookie.find({}, {'link': 1}))

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
            summary_tag = item.select_one('.lead a')
            if title_tag:
                title = title_tag.text.strip()
                summary = summary_tag.text.strip() if summary_tag else ""
                if query in title or query in summary:
                    link = 'https://www.rookie.co.kr' + title_tag['href']
                    
                    # 중복 확인: 이미 있는 링크인지 확인
                    if link in existing_links:
                        print(f"Duplicate article found, skipping: {link}")
                        continue
                    
                    print(f"Found title: {title}")

                    # 기사 페이지에서 작성 시간 파싱
                    article_response = requests.get(link, headers=headers)
                    article_soup = BeautifulSoup(article_response.content, 'html.parser')
                    date_tag = article_soup.select_one('.infomation li:nth-child(2)')
                    date_text = date_tag.text.strip() if date_tag else ""
                    created_at = parse_date(date_text)

                    image_tag = item.select_one('.thumb img')
                    image_url = image_tag['src'] if image_tag else None
                    
                    article = {
                        'title': title, 
                        'link': link,
                        'summary': summary,
                        'image_url': image_url,
                        'created_at': created_at
                    }
                    
                    articles.append(article)
                    existing_links.add(link)  # Set에 새로운 링크 추가
                    page_articles += 1
        print(f"Articles found on page {page} from Rookie: {page_articles}")

    if articles:
        news_rookie.insert_many(articles)
    
    return articles  # 반드시 리스트를 반환

@newsrookie_bp.route('/api/rookie/search/' , strict_slashes=False)
def search_rookie():
    query = request.args.get('q')
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400

    db = current_app.config['db']
    news_rookie = db['news_rookie']
    two_months_ago = datetime.utcnow() - timedelta(days=60)
    articles = list(news_rookie.find({
        '$or': [
            {'title': {'$regex': query, '$options': 'i'}}, 
            # {'summary': {'$regex': query, '$options': 'i'}}
        ]
    }).sort('created_at', -1))

    # 중복 제거 로직 추가: link를 기준으로 중복 제거
    seen_links = set()
    unique_articles = []
    for article in articles:
        if article['link'] not in seen_links:
            seen_links.add(article['link'])
            unique_articles.append(article)
    
    data = [{'_id': str(article['_id']), 'title': article['title'], 'link': article['link'], 'summary': article['summary'], 'image_url': article.get('image_url'), 'created_at': article['created_at']} for article in unique_articles]

    last_crawl = news_rookie.find_one(sort=[("created_at", -1)])
    if not last_crawl or last_crawl['created_at'] < two_months_ago:
        # 기존 데이터 삭제
        news_rookie.delete_many({})
        
        # 새로운 데이터 크롤링 및 삽입
        new_data = crawl_data(query)
        if new_data:
            # 새로운 데이터 리스트 작성
            new_data = [{'_id': str(article['_id']), 'title': article['title'], 'link': article['link'], 'summary': article['summary'], 'image_url': article.get('image_url'), 'created_at': article['created_at']} for article in new_data]
            # 기존 데이터 위에 새로운 데이터를 추가
            data = new_data + data

    return jsonify(data)


