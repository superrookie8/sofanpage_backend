from flask import Blueprint, request, jsonify, current_app
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

newsjumpball_bp = Blueprint('newsjumpball_bp', __name__)

def parse_date(date_string):
    try:
        # 정규 표현식을 이용하여 "기사승인 : YYYY-MM-DD HH:MM:SS" 부분을 추출
        pattern = r"기사승인\s*:\s*(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2}:\d{2})"
        match = re.search(pattern, date_string)
        
        if match:
            # 추출된 문자열을 datetime 객체로 변환
            date_substr = match.group(1)
            return datetime.strptime(date_substr, "%Y-%m-%d %H:%M:%S")
        else:
            return None
    except ValueError:
        return None

def crawl_jumpball(query):
    base_url = 'https://jumpball.co.kr/news/search.php'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    total_pages = 11  # 크롤링할 총 페이지 수
    articles = []

    for page in range(total_pages + 1):  # 0부터 10까지 페이지네이션 처리
        params = {
            'q': query,
            'sfld': 'subj',
            'period': 'ALL',
            'pagenum': page
        }
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

    if articles:
        db = current_app.config['db']
        news_jumpball = db['news_jumpball']
        news_jumpball.insert_many(articles)
    
    return articles  # 반드시 리스트를 반환

@newsjumpball_bp.route('/api/jumpball/search/')
def search_jumpball():
    query = request.args.get('q')
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400

    db = current_app.config['db']
    news_jumpball = db['news_jumpball']
    two_months_ago = datetime.utcnow() - timedelta(days=60)
    articles = news_jumpball.find({
        '$or': [
            {'title': {'$regex': query, '$options': 'i'}}, 
            # {'summary': {'$regex': query, '$options': 'i'}}
        ]
    }).sort('created_at', -1)
    data = [{'title': article['title'], 'link': article['link'], 'summary': article['summary'], 'image_url': article.get('image_url'),'created_at': article['created_at']} for article in articles]

    last_crawl = news_jumpball.find_one(sort=[("created_at", -1)])  # sort 인수 수정
    if not last_crawl or last_crawl['created_at'] < two_months_ago:
        new_data = crawl_jumpball(query)  # 함수 이름 수정
        if new_data:  # new_data가 None이 아닌지 및 비어있지 않은지 확인
            new_data = [{'title': article['title'], 'link': article['link'], 'summary': article['summary'], 'image_url': article.get('image_url'),'created_at': article['created_at']} for article in new_data]
            data = new_data + data

    return jsonify(data)




