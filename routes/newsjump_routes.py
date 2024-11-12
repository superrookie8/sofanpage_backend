from flask import Blueprint, request, jsonify, current_app
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time

newsjumpball_bp = Blueprint('newsjumpball_bp', __name__)

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

@newsjumpball_bp.route('/api/jumpball/search/', strict_slashes=False)
def search_jumpball():
    try:
        db = current_app.config['db']
        news_jumpball = db['news_jumpball']
        
        # 모든 기사를 최신순으로 가져오기
        articles = list(news_jumpball.find().sort('created_at', -1))
        
        # ObjectId를 문자열로 변환
        for article in articles:
            article['_id'] = str(article['_id'])
        
        print(f"\n=== 기사 조회 결과 ===")
        print(f"총 {len(articles)}개 기사 조회됨")
        
        return jsonify(articles)

    except Exception as e:
        print(f"에러 발생: {str(e)}")
        return jsonify({'error': 'Database error'}), 500

def perform_crawl(query, db):
    start_year = 2015
    end_year = datetime.now().year
    total_articles = []
    news_jumpball = db['news_jumpball']

    print("\n=== 크롤링 및 데이터 정리 시작 ===")
    
    # 새로운 기사 크롤링
    for year in range(start_year, end_year + 1):
        print(f"\n{year}년도 기사 크롤링 중...")
        new_articles = crawl_jumpball(query, year, db)
        if new_articles:
            # 새로운 기사들을 DB에 저장
            for article in new_articles:
                try:
                    # 중복 체크 후 저장
                    if not news_jumpball.find_one({'link': article['link']}):
                        news_jumpball.insert_one(article)
                        print(f"새 기사 저장됨: {article['title']}")
                except Exception as e:
                    print(f"기사 저장 중 에러 발생: {str(e)}")
            total_articles.extend(new_articles)

    print(f"\n크롤링 완료: 총 {len(total_articles)}개의 새로운 기사 발견")
    return total_articles

def crawl_jumpball(query, year, db):
    base_url = 'https://jumpball.co.kr/news/search.php'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
        'Referer': 'https://jumpball.co.kr/'
    }
    articles = []

    params = {
        'q': query,
        'sfld': 'subj',
        'period': 'custom',
        'startyear': year,
        'endyear': year,
        'pagenum': 0
    }

    try:
        response = requests.get(base_url, headers=headers, params=params, timeout=10)
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
            page_articles = extract_articles(soup, query, db)
            articles.extend(page_articles)
            print(f"Articles found on page {page} for year {year}: {len(page_articles)}")
            time.sleep(1)  # 서버 부하 방지를 위한 딜레이

    except Exception as e:
        print(f"Error in crawl_jumpball: {str(e)}")
        return []

    return articles

def extract_articles(soup, query, db):
    articles = []
    news_jumpball = db['news_jumpball']
    for item in soup.select('#listWrap .listPhoto'):
        try:
            title_tag = item.select_one('dt a')
            summary_tag = item.select_one('.conts')
            if title_tag:
                title = title_tag.text.strip()
                summary = summary_tag.text.strip() if summary_tag else ""
                link = 'https://jumpball.co.kr' + title_tag['href']

                # 중복 체크를 먼저 수행
                if news_jumpball.find_one({'link': link}):
                    print(f"Duplicate article found, skipping: {link}")
                    continue

                should_save = False
                keyword_count = 0
                
                # 조건 1: 제목이나 요약에 키워드가 포함된 경우
                if query.lower() in title.lower() or query.lower() in summary.lower():
                    print(f"Found matching title/summary: {title}")
                    should_save = True
                
                # 조건 2: 기사 본문에 키워드가 5번 이상 포함된 경우
                try:
                    article_response = requests.get(link, timeout=10)
                    article_soup = BeautifulSoup(article_response.content, 'html.parser')
                    content_tag = article_soup.select_one('#articleBody')
                    if content_tag:
                        content = content_tag.text.strip()
                        keyword_count = content.lower().count(query.lower())
                        if keyword_count >= 5:
                            print(f"Found article with {keyword_count} keyword occurrences: {title}")
                            should_save = True

                    date_tag = article_soup.select_one('.viewTitle > dl > dd')
                    date_text = date_tag.text.strip() if date_tag else ""
                    created_at = parse_date(date_text)
                    
                except Exception as e:
                    print(f"Error checking article content: {str(e)}")
                    continue

                # 둘 중 하나라도 조건을 만족하면 저장
                if should_save:
                    image_tag = item.select_one('.img a')
                    image_url = image_tag['style'].split("url('")[1].split("')")[0] if image_tag else None

                    article = {
                        'title': title, 
                        'link': link,
                        'summary': summary,
                        'image_url': image_url,
                        'created_at': created_at,
                        'keyword_count': keyword_count
                    }

                    articles.append(article)
                    print(f"Saved article: {title} (keyword count: {keyword_count})")
                    
        except Exception as e:
            print(f"Error processing article: {str(e)}")
            continue
            
    return articles

def crawl_specific_article(url):
    try:
        # 1. 먼저 검색 페이지에서 해당 기사의 정보를 찾습니다
        search_url = "https://jumpball.co.kr/news/search.php?q=이소희&sfld=all&period=MONTH|12"
        search_response = requests.get(search_url, headers={'User-Agent': 'Mozilla/5.0'})
        search_soup = BeautifulSoup(search_response.content, 'html.parser')
        
        # 2. 검색 결과에서 해당 URL을 가진 기사 찾기
        article_items = search_soup.select('.listPhoto')
        target_article = None
        
        for item in article_items:
            link_tag = item.select_one('dt a')
            if link_tag and link_tag.get('href'):
                article_url = 'https://jumpball.co.kr' + link_tag['href']
                if article_url == url:
                    # 썸네일 이미지 찾기
                    img_div = item.select_one('.img')
                    if img_div and img_div.select_one('a'):
                        style = img_div.select_one('a').get('style', '')
                        image_url = style.split("url('")[-1].split("')")[0] if "url('" in style else None
                    
                    # 요약 텍스트 찾기
                    summary = item.select_one('.txt')
                    summary_text = summary.text.strip() if summary else ""
                    
                    target_article = {
                        'image_url': image_url,
                        'summary': summary_text
                    }
                    break
        
        if not target_article:
            print("검색 결과에서 해당 기사를 찾을 수 없습니다.")
            return None
            
        # 3. 기사 상세 페이지 크롤링
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title_tag = soup.select_one('.viewTitle h3')
            title = title_tag.text.strip() if title_tag else None
            
            date_tag = soup.select_one('.viewTitle > dl > dd')
            date_text = date_tag.text.strip() if date_tag else None
            created_at = parse_date(date_text)
            
            if title and created_at:
                article = {
                    'title': title,
                    'link': url,
                    'summary': target_article['summary'],
                    'image_url': target_article['image_url'],
                    'created_at': created_at,
                    'keyword_count': target_article['summary'].lower().count('이소희')
                }
                
                print(f"\n크롤링 완료:")
                print(f"제목: {title}")
                print(f"날짜: {created_at}")
                print(f"이미지: {target_article['image_url']}")
                return article
                
    except Exception as e:
        print(f"크롤링 중 에러 발생: {str(e)}")
        return None

@newsjumpball_bp.route('/api/jumpball/add-article/', methods=['POST'])
def add_specific_article():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400
        
    try:
        db = current_app.config['db']
        news_jumpball = db['news_jumpball']
        
        # 1. 먼저 잘못된 기사 삭제
        news_jumpball.delete_many({
            'title': {'$regex': '샤크.*덩크.*간다', '$options': 'i'}
        })
        
        # 2. 새 기사 크롤링
        article = crawl_specific_article(url)
        
        if article:
            # 3. DB에 저장 시도
            try:
                # 중복 체크
                existing = news_jumpball.find_one({'link': url})
                if existing:
                    print(f"이미 존재하는 기사입니다: {existing['title']}")
                    return jsonify({
                        'message': 'Article already exists',
                        'article': existing
                    })
                
                # 새 문서 저장
                result = news_jumpball.insert_one(article)
                
                # 저장 확인
                saved = news_jumpball.find_one({'_id': result.inserted_id})
                if not saved:
                    raise Exception("저장 실패: DB에서 문서를 찾을 수 없음")
                
                print(f"\n=== 저장 성공 ===")
                print(f"제목: {saved['title']}")
                print(f"ID: {saved['_id']}")
                
                return jsonify({
                    'message': 'Article successfully added',
                    'article': {
                        '_id': str(saved['_id']),
                        'title': saved['title'],
                        'link': saved['link'],
                        'created_at': saved['created_at'],
                        'keyword_count': saved['keyword_count']
                    }
                })
                
            except Exception as e:
                print(f"DB 저장 중 에러: {str(e)}")
                return jsonify({'error': f'Database error: {str(e)}'}), 500
        else:
            return jsonify({'error': 'Failed to crawl article'}), 400
            
    except Exception as e:
        print(f"전체 프로세스 에러: {str(e)}")
        return jsonify({'error': str(e)}), 500