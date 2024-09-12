from flask import Blueprint, request, jsonify, current_app
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

newsjumpball_bp = Blueprint('newsjumpball_bp', __name__)

# 날짜 파싱 함수 개선
def parse_date(date_string):
    try:
        # 날짜와 시간을 모두 추출하는 패턴 (예: "2024-09-10 15:30:00")
        pattern = r"(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2}:\d{2})"
        match = re.search(pattern, date_string)
        
        if match:
            # 추출된 문자열을 datetime 객체로 변환
            return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
        else:
            return None
    except ValueError:
        return None

# 페이지 수를 동적으로 추출하는 함수
def get_total_pages(soup):
    # 페이지 네이션 숫자 중 가장 큰 값 찾기
    pagination = soup.select('.pagination a')
    if pagination:
        last_page = pagination[-1].get('href')
        total_pages = re.search(r'pagenum=(\d+)', last_page).group(1)
        return int(total_pages)
    return 1

# 크롤링 함수 수정
def crawl_jumpball(query):
    base_url = 'https://jumpball.co.kr/news/search.php'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    articles = []

    db = current_app.config['db']
    news_jumpball = db['news_jumpball']

    # 첫 페이지 가져와서 페이지 수 동적으로 계산
    params = {
        'q': query,
        'sfld': 'subj',
        'period': 'ALL',
        'pagenum': 0
    }
    
    response = requests.get(base_url, headers=headers, params=params)
    if response.status_code != 200:
        print(f"Failed to retrieve data for the first page: {response.status_code}")
        return []
    
    soup = BeautifulSoup(response.content, 'html.parser')
    total_pages = get_total_pages(soup)

    for page in range(total_pages + 1):  # 0부터 마지막 페이지까지 크롤링
        params['pagenum'] = page
        print(f"Crawling page {page} from Jumpball")
        response = requests.get(base_url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Failed to retrieve data for page {page}: {response.status_code}")
            continue
        
        soup = BeautifulSoup(response.content, 'html.parser')
        page_articles = 0
        for item in soup.select('#listWrap .listPhoto'):
            title_tag = item.select_one('dt a')
            summary_tag = item.select_one('.conts')
            if title_tag:
                title = title_tag.text.strip()
                summary = summary_tag.text.strip() if summary_tag else ""
                if query in title or query in summary:
                    print(f"Found title: {title}")
                    link = 'https://jumpball.co.kr' + title_tag['href']

                    # 기사 페이지에서 작성 시간 파싱
                    article_response = requests.get(link, headers=headers)
                    article_soup = BeautifulSoup(article_response.content, 'html.parser')
                    date_tag = article_soup.select_one('.viewTitle > dl > dd')
                    date_text = date_tag.text.strip() if date_tag else ""
                    created_at = parse_date(date_text)

                    image_tag = item.select_one('.img a')
                    image_url = image_tag['style'].split("url('")[1].split("')")[0] if image_tag else None
                    
                    # 중복 확인: 이미 있는 링크인지 확인
                    if news_jumpball.find_one({'link': link}):
                        print(f"Duplicate article found, skipping: {link}")
                        continue
                    
                    article = {
                        'title': title, 
                        'link': link,
                        'summary': summary,
                        'image_url': image_url,
                        'created_at': created_at
                    }
                    
                    articles.append(article)
                    page_articles += 1
        print(f"Articles found on page {page} from Jumpball: {page_articles}")

    # 중복 제거 후 데이터베이스에 삽입
    if articles:
        news_jumpball.insert_many(articles)
    
    return articles  # 반드시 리스트를 반환

@newsjumpball_bp.route('/api/jumpball/search/', strict_slashes=False)
def search_jumpball():
    query = request.args.get('q')
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400

    db = current_app.config['db']
    news_jumpball = db['news_jumpball']

    # 최신 기사의 작성일 확인
    last_article = news_jumpball.find_one(sort=[("created_at", -1)])

    # 크롤링이 필요할 때만 수행 (마지막 기사의 작성일이 한 달 이상 지났을 경우)
    if not last_article or last_article['created_at'] < datetime.utcnow() - timedelta(days=30):
        print("Crawling new articles...")
        new_articles = crawl_jumpball(query)

        if new_articles:  # 새로운 기사가 있는 경우에만 삽입
            news_jumpball.insert_many(new_articles)

    # 데이터베이스에서 검색 결과 반환
    articles = list(news_jumpball.find({
        '$or': [
            {'title': {'$regex': query, '$options': 'i'}},
        ]
    }).sort('created_at', -1))

    # 중복 제거 및 결과 처리
    seen_links = set()
    unique_articles = []
    for article in articles:
        if article['link'] not in seen_links:
            seen_links.add(article['link'])
            unique_articles.append(article)

    data = [
        {
            '_id': str(article['_id']),
            'title': article['title'],
            'link': article['link'],
            'summary': article['summary'],
            'image_url': article.get('image_url'),
            'created_at': article['created_at']
        } for article in unique_articles
    ]

    return jsonify(data)
