from flask import Blueprint, request, jsonify, current_app
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

newsrookie_bp = Blueprint('newsrookie_bp', __name__)

# 날짜 파싱 함수
def parse_date(date_string):
    try:
        # 날짜와 시간을 모두 추출하는 패턴
        # "2024.09.07 20:03" 형식만 추출 (앞의 기자 이름, 소속 등은 무시)
        pattern = r"(\d{4}\.\d{2}\.\d{2}\s*\d{2}:\d{2})"
        match = re.search(pattern, date_string)
        
        if match:
            # 추출된 문자열을 datetime 객체로 변환
            return datetime.strptime(match.group(1), "%Y.%m.%d %H:%M")
        else:
            return None
    except ValueError:
        return None

# 페이지 수를 동적으로 추출하는 함수
def get_total_pages(soup):
    pagination = soup.select('.pagination a')
    if pagination:
        last_page = pagination[-1].get('href')
        total_pages = re.search(r'page=(\d+)', last_page).group(1)  # rookie.co.kr의 페이지네이션 확인
        return int(total_pages)
    return 1

def should_crawl(db):
    crawl_info = db['crawl_info'].find_one({'name': 'rookie_last_crawl'})
    if not crawl_info:
        return True
    last_crawl_date = crawl_info['date']
    return datetime.now() - last_crawl_date > timedelta(days=30)


# 크롤링 함수 수정
def crawl_data(query):
    base_url = 'https://www.rookie.co.kr/news/articleList.html'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    articles = []

    db = current_app.config['db']
    news_rookie = db['news_rookie']

    if should_crawl(db):
        print("Performing monthly crawl...")
        new_articles = crawl_data(query)
        if new_articles:
            news_rookie.insert_many(new_articles)
            db['crawl_info'].update_one(
                {'name': 'rookie_last_crawl'},
                {'$set': {'date': datetime.now()}},
                upsert=True
            )
    else:
        print("Using existing data from the last crawl.")


    # 기존에 수집된 링크들
    existing_links = set(article['link'] for article in news_rookie.find({}, {'link': 1}))

    # 첫 번째 페이지 크롤링 후, 총 페이지 수를 동적으로 추출
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
        page_articles = 0
        
        # #section-list > ul > li 구조의 기사 선택
        for item in soup.select('#section-list > ul > li'):
            title_tag = item.select_one('.titles a')
            summary_tag = item.select_one('.lead a')
            date_tag = item.select_one('.byline em:last-child')  # 날짜 정보는 .byline의 마지막 <em> 요소

            if title_tag:
                title = title_tag.text.strip()
                summary = summary_tag.text.strip() if summary_tag else ""
                
              
                if "원조 머슬녀" in title or "원조 머슬녀" in summary:
                    print(f"Excluding article with keyword: {title}")
                    continue  # 해당 기사를 제외하고 다음 기사로 넘어감

                if query in title or query in summary:
                    link = 'https://www.rookie.co.kr' + title_tag['href']
                    
                    if link in existing_links:
                        print(f"Duplicate article found, skipping: {link}")
                        continue
                    
                    print(f"Found title: {title}")

                    # 기사 페이지에서 작성 시간 파싱
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
                    existing_links.add(link)  # 중복 체크용 링크 추가
                    page_articles += 1
        print(f"Articles found on page {page} from Rookie: {page_articles}")

    # 크롤링한 기사 데이터 저장
    if articles:
        news_rookie.insert_many(articles)
    
    return articles  # 반드시 리스트를 반환


@newsrookie_bp.route('/api/rookie/search/', strict_slashes=False)
def search_rookie():
    query = request.args.get('q')
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400

    db = current_app.config['db']
    news_rookie = db['news_rookie']

    # 최신 기사의 작성일 확인
    last_article = news_rookie.find_one(sort=[("created_at", -1)])

    # 크롤링이 필요할 때만 수행 (마지막 기사의 작성일이 한 달 이상 지났을 경우)
    if not last_article or last_article['created_at'] < datetime.utcnow() - timedelta(days=30):
        print("Crawling new articles...")
        new_articles = crawl_data(query)

        if new_articles:  # 새로운 기사가 있는 경우에만 삽입
            news_rookie.insert_many(new_articles)

    # 데이터베이스에서 검색 결과 반환
    articles = list(news_rookie.find({
        '$or': [
            {'title': {'$regex': query, '$options': 'i'}}
        ]
    }).sort('created_at', -1))

    # 중복 제거 로직 추가
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
