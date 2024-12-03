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

def crawl_data(query, db, is_first_run=False):
    base_url = 'https://www.rookie.co.kr/news/articleList.html'
    headers = {'User-Agent': 'Mozilla/5.0'}
    new_articles = []

    news_rookie = db['news_rookie']
    
    # 최신 기사 날짜 가져오기
    latest_date = get_latest_article_date(db)
    print(f"\n=== 크롤링 시작 ===")
    print(f"최신 기사 날짜: {latest_date}")

    response = requests.get(base_url, headers=headers, params={'sc_word': query, 'view_type': 'sm', 'page': 1})
    if response.status_code != 200:
        print(f"Failed to retrieve the first page: {response.status_code}")
        return []
    
    soup = BeautifulSoup(response.content, 'html.parser')
    total_pages = get_total_pages(soup)
    should_continue = True

    for page in range(1, total_pages + 1):
        if not should_continue:
            break

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
            try:
                title_tag = item.select_one('.titles a')
                summary_tag = item.select_one('.lead a')
                date_tag = item.select_one('.byline em:last-child')

                if not title_tag:
                    continue

                title = title_tag.text.strip()
                
                # 제외할 기사 필터링
                if '원조 머슬녀' in title:
                    print(f"제외 기사 발견, 건너뜀: {title}")
                    continue
                
                # 제목에 키워드가 있는 기사만 처리
                if query in title:
                    link = 'https://www.rookie.co.kr' + title_tag['href']
                    
                    # 중복 체크
                    if news_rookie.find_one({'link': link}):
                        print(f"중복 기사 발견, 건너뜀: {title}")
                        continue
                        
                    date_text = date_tag.text.strip() if date_tag else ""
                    created_at = parse_date(date_text)

                    if not created_at:
                        print(f"날짜 파싱 실패, 건너뜀: {title}")
                        continue

                    # 증분 업데이트 시 날짜 체크
                    if latest_date and created_at <= latest_date:
                        print(f"이미 저장된 기사 날짜 발견, 크롤링 중단: {title}")
                        should_continue = False
                        break

                    summary = summary_tag.text.strip() if summary_tag else ""
                    image_tag = item.select_one('.thumb img')
                    image_url = image_tag['src'] if image_tag else None
                    
                    article = {
                        'title': title, 
                        'link': link,
                        'summary': summary,
                        'image_url': image_url,
                        'created_at': created_at
                    }
                    
                    new_articles.append(article)
                    print(f"새 기사 발견: {title}")

            except Exception as e:
                print(f"기사 처리 중 에러 발생: {str(e)}")
                continue

    if new_articles:
        try:
            # 새 기사만 저장 (중복 방지)
            for article in new_articles:
                news_rookie.update_one(
                    {'link': article['link']},  # 링크로 중복 체크
                    {'$setOnInsert': article},  # 없을 때만 삽입
                    upsert=True
                )
            print(f"\n총 {len(new_articles)}개의 새로운 기사 처리됨")
        except Exception as e:
            print(f"저장 중 에러 발생: {str(e)}")
    else:
        print("\n새로운 기사가 없습니다.")
    
    return new_articles

@newsrookie_bp.route('/api/rookie/search/', strict_slashes=False)
def search_rookie():
    """기존 데이터 조회만 수행하는 엔드포인트"""
    try:
        db = current_app.config['db']
        news_rookie = db['news_rookie']
        
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

    except Exception as e:
        print(f"Error in search_rookie: {str(e)}")
        return jsonify({'error': str(e)}), 500

@newsrookie_bp.route('/api/rookie/crawl/', methods=['POST'])
def crawl_rookie():
    """크롤링을 수행하는 별도 엔드포인트"""
    try:
        db = current_app.config['db']
        
        # 마지막 크롤링 시간 체크
        if not should_crawl(db):
            return jsonify({'message': '마지막 크롤링 후 5일이 지나지 않았습니다.'})

        # 증분 크롤링 시작
        print("\n=== 증분 크롤링 시작 ===")
        new_articles = crawl_data("이소희", db)
        
        # 마지막 크롤링 시간 업데이트
        db['crawl_info'].update_one(
            {'name': 'rookie_last_crawl'},
            {'$set': {'date': datetime.now()}},
            upsert=True
        )
        
        return jsonify({
            'message': f'크롤링 완료: {len(new_articles)}개의 새로운 기사 처리됨'
        })

    except Exception as e:
        print(f"Error in crawl_rookie: {str(e)}")
        return jsonify({'error': str(e)}), 500
