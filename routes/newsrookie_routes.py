from flask import Blueprint, request, jsonify, current_app
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

newsrookie_bp = Blueprint('newsrookie_bp', __name__)

def parse_date(date_string):
    try:
        pattern = r"(\d{4}\.\d{2}\.\d{2}\s*\d{2}:\d{2})"
        match = re.search(pattern, date_string)
        if match:
            return datetime.strptime(match.group(1), "%Y.%m.%d %H:%M")
        else:
            return None
    except ValueError:
        return None

def get_total_pages(soup):
    pagination = soup.select('.pagination a')
    if pagination:
        last_page = pagination[-1].get('href')
        total_pages = re.search(r'page=(\d+)', last_page).group(1)
        return int(total_pages)
    return 1

def get_latest_article_date(db):
    news_rookie = db['news_rookie']
    latest_article = news_rookie.find_one(
        {},
        sort=[('created_at', -1)]
    )
    return latest_article['created_at'] if latest_article else None

def should_crawl(db):
    crawl_info = db['crawl_info'].find_one({'name': 'rookie_last_crawl'})
    if not crawl_info:
        return True
    last_crawl_date = crawl_info['date']
    return datetime.now() - last_crawl_date > timedelta(days=5)

def crawl_data(query, db):
    base_url = 'https://www.rookie.co.kr/news/articleList.html'
    headers = {'User-Agent': 'Mozilla/5.0'}
    articles = []

    news_rookie = db['news_rookie']
    existing_links = set(article['link'] for article in news_rookie.find({}, {'link': 1}))

    response = requests.get(base_url, headers=headers, params={'sc_word': query, 'view_type': 'sm', 'page': 1})
    if response.status_code != 200:
        print(f"Failed to retrieve the first page: {response.status_code}")
        return []
    
    soup = BeautifulSoup(response.content, 'html.parser')
    total_pages = get_total_pages(soup)

    for page in range(1, total_pages + 1):
        params = {
            'sc_word': query,
            'view_type': 'sm',
            'page': page
        }
        print(f"Crawling page {page} from Rookie")
        response = requests.get(base_url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Failed to retrieve data for page {page}: {response.status_code}")
            continue
        
        soup = BeautifulSoup(response.content, 'html.parser')
        for item in soup.select('#section-list > ul > li'):
            title_tag = item.select_one('.titles a')
            summary_tag = item.select_one('.lead a')
            date_tag = item.select_one('.byline em:last-child')

            if title_tag:
                title = title_tag.text.strip()
                summary = summary_tag.text.strip() if summary_tag else ""
                
                # 제목에 "이소희"가 있는 기사만 처리
                if query in title:
                    link = 'https://www.rookie.co.kr' + title_tag['href']
                    
                    # 중복 체크
                    if link in existing_links:
                        print(f"Duplicate article found, skipping: {title}")
                        continue
                    
                    print(f"Found title: {title}")

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
                    existing_links.add(link)

    if articles:
        news_rookie.insert_many(articles)
        print(f"\n총 {len(articles)}개의 새로운 기사 저장됨")
    
    return articles

@newsrookie_bp.route('/api/rookie/search/', strict_slashes=False)
def search_rookie():
    db = current_app.config['db']
    news_rookie = db['news_rookie']

    # 데이터베이스가 비어있거나 5일이 지났으면 크롤링 시작
    if news_rookie.count_documents({}) == 0 or should_crawl(db):
        print("\n=== 크롤링 시작 ===")
        print("데이터베이스가 비어있거나 5일이 지나서 크롤링을 시작합니다.")
        crawl_data("이소희", db)  # 검색어 고정
        db['crawl_info'].update_one(
            {'name': 'rookie_last_crawl'},
            {'$set': {'date': datetime.now()}},
            upsert=True
        )
    
    # 저장된 모든 기사 최신순으로 반환
    articles = list(news_rookie.find().sort('created_at', -1))

    data = [
        {
            '_id': str(article['_id']),
            'title': article['title'],
            'link': article['link'],
            'summary': article['summary'],
            'image_url': article.get('image_url'),
            'created_at': article['created_at']
        } for article in articles
    ]

    return jsonify(data)
