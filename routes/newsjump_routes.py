from flask import Blueprint, request, jsonify, current_app
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

newsjumpball_bp = Blueprint('newsjumpball_bp', __name__)

# 날짜 파싱 함수 개선
def parse_date(date_string):
    try:
        pattern = r"(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2}:\d{2})"
        match = re.search(pattern, date_string)
        if match:
            return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
        else:
            return None
    except ValueError:
        return None

# 페이지 수를 동적으로 추출하는 함수
def get_total_pages(soup):
    pagination = soup.select('.pagination a')
    if pagination:
        last_page = pagination[-1].get('href')
        total_pages = re.search(r'pagenum=(\d+)', last_page).group(1)
        return int(total_pages)
    return 1

def should_crawl(db):
    last_crawl = db['crawl_info'].find_one({'name': 'jumpball_last_crawl'})
    if not last_crawl:
        return True
    last_crawl_date = last_crawl['date']
    return datetime.now() - last_crawl_date > timedelta(days=30)

# 크롤링 함수
@newsjumpball_bp.route('/api/jumpball/search/', strict_slashes=False)
def search_jumpball():
    query = request.args.get('q')
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400

    db = current_app.config['db']
    news_jumpball = db['news_jumpball']

    if should_crawl(db):

        print("Performing monthly crawl...")

    # 2015년부터 현재까지의 기사를 가져오도록 설정
    start_year = 2015
    end_year = datetime.now().year
    total_articles = []

    for year in range(start_year, end_year + 1):
        print(f"Crawling articles for the year {year}")
        new_articles = crawl_jumpball(query, year)

        if new_articles:
            total_articles.extend(new_articles)

    if total_articles:
        news_jumpball.delete_many({})  # 기존 데이터 삭제
        news_jumpball.insert_many(total_articles)  # 새 데이터 저장

        db['crawl_info'].update_one(
            {'name': 'jumpball_last_crawl'},
            {'$set': {'date': datetime.now()}},
            upsert=True
        )
    else:
        print("Using existing data from the last crawl.")
    

    articles = list(news_jumpball.find({
        '$or': [
            {'title': {'$regex': query, '$options': 'i'}},
        ]
    }).sort('created_at', -1))

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

# 크롤링 함수에서 특정 연도에 맞춰 기간 설정 추가
def crawl_jumpball(query, year):
    base_url = 'https://jumpball.co.kr/news/search.php'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    articles = []

    db = current_app.config['db']
    news_jumpball = db['news_jumpball']

    # 각 연도에 맞춰 기간을 설정
    params = {
        'q': query,
        'sfld': 'subj',
        'period': 'custom',  # 사용자 정의 기간
        'startyear': year,  # 시작 연도 설정
        'endyear': year,  # 끝 연도 설정
        'pagenum': 0
    }

    response = requests.get(base_url, headers=headers, params=params)
    if response.status_code != 200:
        print(f"Failed to retrieve data for the year {year}: {response.status_code}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    total_pages = get_total_pages(soup)

    for page in range(total_pages + 1):
        params['pagenum'] = page
        print(f"Crawling page {page} from Jumpball for year {year}")
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
        print(f"Articles found on page {page} for year {year}: {page_articles}")

    return articles

