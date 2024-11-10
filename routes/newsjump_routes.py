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
    db = current_app.config['db']
    news_jumpball = db['news_jumpball']

    # DB에 저장된 모든 기사를 최신순으로 가져오기
    existing_articles = list(news_jumpball.find().sort('created_at', -1))

    data = [
        {
            '_id': str(article['_id']),
            'title': article['title'],
            'link': article['link'],
            'summary': article['summary'],
            'image_url': article.get('image_url'),
            'created_at': article['created_at'].strftime("%Y-%m-%d %H:%M:%S") if article.get('created_at') else None,
            'keyword_count': article.get('keyword_count', 0)
        } for article in existing_articles
    ]

    return jsonify(data)

def perform_crawl(query, db):
    start_year = 2015
    end_year = datetime.now().year
    total_articles = []

    for year in range(start_year, end_year + 1):
        print(f"Crawling articles for the year {year}")
        new_articles = crawl_jumpball(query, year, db)
        if new_articles:
            total_articles.extend(new_articles)

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

                # 중복 체크
                if news_jumpball.find_one({'link': link}):
                    continue

                should_save = False
                keyword_count = 0
                
                if query.lower() in title.lower() or query.lower() in summary.lower():
                    should_save = True
                
                try:
                    article_response = requests.get(link, timeout=10)
                    article_soup = BeautifulSoup(article_response.content, 'html.parser')
                    content_tag = article_soup.select_one('#articleBody')
                    if content_tag:
                        content = content_tag.text.strip()
                        keyword_count = content.lower().count(query.lower())
                        if keyword_count >= 5:
                            should_save = True

                    date_tag = article_soup.select_one('.viewTitle > dl > dd')
                    date_text = date_tag.text.strip() if date_tag else ""
                    created_at = parse_date(date_text)
                    
                except Exception as e:
                    continue

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
                    
        except Exception as e:
            continue
            
    return articles

def crawl_specific_article(url):
    try:
        # 검색 페이지에서 기사 정보 찾기
        search_url = "https://jumpball.co.kr/news/search.php?q=이소희&sfld=all&period=MONTH|12"
        search_response = requests.get(search_url, headers={'User-Agent': 'Mozilla/5.0'})
        search_soup = BeautifulSoup(search_response.content, 'html.parser')
        
        # 검색 결과에서 해당 URL을 가진 기사 찾기
        article_items = search_soup.select('#listWrap .listPhoto')
        image_url = None
        summary = ""
        
        for item in article_items:
            link_tag = item.select_one('dt a')
            if link_tag and ('https://jumpball.co.kr' + link_tag['href'] == url):
                # 이미지 URL 추출
                img_tag = item.select_one('.img a')
                if img_tag and 'style' in img_tag.attrs:
                    style = img_tag['style']
                    if 'url(' in style:
                        image_url = style.split("url('")[1].split("')")[0]
                        print(f"Found matching article image: {image_url}")
                
                # 요약문 추출
                summary_tag = item.select_one('.conts')
                if summary_tag:
                    summary = summary_tag.text.strip()
                    print(f"Found article summary: {summary}")
                break
        
        # 기사 상세 페이지 크롤링
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title_tag = soup.select_one('.viewTitle h3')
            title = title_tag.text.strip() if title_tag else None
            
            date_tag = soup.select_one('.viewTitle > dl > dd')
            date_text = date_tag.text.strip() if date_tag else None
            created_at = parse_date(date_text)
            
            content_tag = soup.select_one('#articleBody')
            keyword_count = content_tag.text.lower().count('이소희') if content_tag else 0
            
            if title and created_at:
                article = {
                    'title': title,
                    'link': url,
                    'summary': summary,  # 검색 페이지에서 가져온 요약문 사용
                    'image_url': image_url,
                    'created_at': created_at,
                    'keyword_count': keyword_count
                }
                
                print(f"\n크롤링 완료:")
                print(f"제목: {title}")
                print(f"요약: {summary}")
                print(f"날짜: {created_at}")
                print(f"이미지: {image_url if image_url else '없음'}")
                return article
                
    except Exception as e:
        print(f"크롤링 중 에러 발생: {str(e)}")
        return None

@newsjumpball_bp.route('/api/jumpball/add-article/', methods=['POST'])
def add_specific_article():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400
        
    db = current_app.config['db']
    article = crawl_specific_article(url)
    
    if article:
        news_jumpball = db['news_jumpball']
        if not news_jumpball.find_one({'link': url}):
            news_jumpball.insert_one(article)
        
        return jsonify({
            'message': 'Article successfully added',
            'article': {
                'title': article['title'],
                'link': article['link'],
                'created_at': article['created_at'],
                'keyword_count': article['keyword_count']
            }
        })
    else:
        return jsonify({'error': 'Failed to add article'}), 400