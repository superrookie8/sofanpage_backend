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
    return datetime.now() - last_crawl_date > timedelta(days=1)

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

def get_latest_article_date(db):
    """DB에서 가장 최신 기사의 날짜를 가져옴"""
    latest_article = db['news_jumpball'].find_one(
        {},  # 모든 문서 대상
        sort=[('created_at', -1)]  # created_at 기준 내림차순
    )
    if latest_article:
        print(f"Latest article in DB: {latest_article['title']} ({latest_article['created_at']})")
        return latest_article['created_at']
    return None

def crawl_data(query, db):
    print(f"\n=== 크롤링 시작 ===")
    
    news_jumpball = db['news_jumpball']
    new_articles = []
    
    # 11월 12일 이후 기사만 가져오기 위한 기준 날짜
    cutoff_date = datetime(2024, 11, 12)
    
    articles = crawl_jumpball(query, None, db)
    
    for article in articles:
        # 11월 12일 이후이고, 제목에 "이소희"가 있는 기사만 처리
        if article['created_at'] > cutoff_date and query in article['title']:
            # 중복 체크
            if not news_jumpball.find_one({'link': article['link']}):
                new_articles.append(article)
                print(f"새 기사 발견: {article['title']} ({article['created_at']})")
    
    if new_articles:
        try:
            news_jumpball.insert_many(new_articles)
            print(f"\n총 {len(new_articles)}개의 새로운 기사 저장됨")
            for article in new_articles:
                print(f"- {article['title']}")
        except Exception as e:
            print(f"저장 중 에러 발생: {str(e)}")
    else:
        print("\n새로운 기사가 없습니다.")
    
    return new_articles

def crawl_jumpball(query, year, db):
    base_url = 'https://jumpball.co.kr/news/search.php'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    params = {
        'q': query,
        'sfld': 'subj',
        'x': '0',
        'y': '0'
    }

    try:
        print(f"\n=== 검색 URL: {base_url}?q={query} ===")
        response = requests.get(base_url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            print(f"Failed to retrieve data: {response.status_code}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        articles = []
        
        for item in soup.select('.listPhoto'):
            try:
                # 제목과 링크 추출
                title_tag = item.select_one('dt a')
                if not title_tag:
                    continue
                    
                title = title_tag.text.strip()
                if query not in title:
                    continue
                    
                link = 'https://jumpball.co.kr' + title_tag['href']
                
                # 상세 페이지에서 정확한 작성 시간 가져오기
                article_response = requests.get(link, headers=headers, timeout=10)
                article_soup = BeautifulSoup(article_response.content, 'html.parser')
                date_tag = article_soup.select_one('#main > div.viewTitle > dl > dd')
                
                if date_tag:
                    date_text = date_tag.text.strip()
                    # "입력 : 2024-12-05 16:22:51" 형식에서 날짜와 ��� 추출
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', date_text)
                    if date_match:
                        created_at = datetime.strptime(date_match.group(1), '%Y-%m-%d %H:%M:%S')
                    else:
                        continue
                else:
                    continue
                
                # 이미지 URL 추출
                img_div = item.select_one('.img a')
                image_url = None
                if img_div and 'style' in img_div.attrs:
                    style = img_div['style']
                    if "url('" in style:
                        image_url = style.split("url('")[1].split("')")[0]
                
                # 요약 추출
                summary_tag = item.select_one('.conts')
                summary = summary_tag.text.strip() if summary_tag else ""

                article = {
                    'title': title,
                    'link': link,
                    'summary': summary,
                    'image_url': image_url,
                    'created_at': created_at
                }
                
                articles.append(article)
                print(f"Found article: {title} ({created_at})")
                time.sleep(1)  # 서버 부하 방지
                
            except Exception as e:
                print(f"Error extracting article: {str(e)}")
                continue

        return articles

    except Exception as e:
        print(f"Error in crawl_jumpball: {str(e)}")
        return []

def crawl_specific_article(url):
    try:
        # 1. 먼저 검색 페이지에서 해당 기사의 정보를 찾습니다
        search_url = "https://jumpball.co.kr/news/search.php?q=이소희&sfld=all&period=MONTH|12"
        search_response = requests.get(search_url, headers={'User-Agent': 'Mozilla/5.0'})
        search_soup = BeautifulSoup(search_response.content, 'html.parser')
        
        # 2. 검색 결과에서 해당 URL을 진 기사 찾기
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
        
        # 2. 새 기사 크롤링링
        article = crawl_specific_article(url)
        
        if article:
            # 3. DB에 저장 시도
            try:
                # 중복 체크크
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

@newsjumpball_bp.route('/api/jumpball/crawl/', methods=['POST'])
def start_crawl():
    try:
        db = current_app.config['db']
        query = "이소희"  # 기본 검색어
        
        if should_crawl(db):
            crawl_data(query, db)
            # 크롤링 완료 후 마지막 크롤링 시간 업데이트
            db['crawl_info'].update_one(
                {'name': 'jumpball_last_crawl'},
                {'$set': {'date': datetime.now()}},
                upsert=True
            )
            return jsonify({'message': 'Crawling completed successfully'})
        else:
            return jsonify({'message': 'Crawling skipped - last crawl was within 30 days'})

    except Exception as e:
        print(f"Crawling error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@newsjumpball_bp.route('/api/jumpball/delete-specific/', methods=['POST'])
def delete_specific_article():
    try:
        db = current_app.config['db']
        news_jumpball = db['news_jumpball']
        
        # 11월 10일 기사 찾기
        target_date = datetime(2024, 11, 10)
        
        # 삭제할 기사 확인
        to_delete = list(news_jumpball.find({'created_at': target_date}))
        
        if to_delete:
            print("\n=== 삭제할 기사 ===")
            for article in to_delete:
                print(f"- {article['title']} ({article['created_at']})")
            
            # 삭제 실행
            result = news_jumpball.delete_many({'created_at': target_date})
            
            print(f"\n{result.deleted_count}개 기사 삭제됨")
            return jsonify({
                'message': f'{result.deleted_count} article deleted',
                'deleted_articles': len(to_delete)
            })
        else:
            return jsonify({'message': 'No article found to delete'})

    except Exception as e:
        print(f"Delete error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@newsjumpball_bp.route('/api/jumpball/restore-specific/', methods=['POST'])
def restore_specific_article():
    try:
        db = current_app.config['db']
        news_jumpball = db['news_jumpball']
        
        # 먼저 검색 페이지에서 기� 정보 가져오기
        search_url = "https://jumpball.co.kr/news/search.php"
        target_url = "https://jumpball.co.kr/news/newsview.php?ncode=1065539839641968"
        
        params = {
            'q': '이소희',
            'sfld': 'all',
            'period': 'MONTH|12'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(search_url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            return jsonify({'error': 'Failed to fetch search page'}), 500
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 검색 결과에서 해당 기사 찾기
        for item in soup.select('.listPhoto'):
            link_tag = item.select_one('dt a')
            if not link_tag:
                continue
                
            link = 'https://jumpball.co.kr' + link_tag['href']
            if link == target_url:
                title = link_tag.text.strip()
                
                # 이미지 URL 추출
                img_div = item.select_one('.img a')
                image_url = None
                if img_div and 'style' in img_div.attrs:
                    style = img_div['style']
                    if "url('" in style:
                        image_url = style.split("url('")[1].split("')")[0]
                
                # 요약 추출
                summary_tag = item.select_one('.conts')
                summary = summary_tag.text.strip() if summary_tag else ""
                
                # 상세 페이지에서 정확한 작성 시간 가져오기
                article_response = requests.get(link, headers=headers, timeout=10)
                if article_response.status_code == 200:
                    article_soup = BeautifulSoup(article_response.content, 'html.parser')
                    date_tag = article_soup.select_one('#main > div.viewTitle > dl > dd')
                    if date_tag:
                        date_text = date_tag.text.strip()
                        date_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', date_text)
                        if date_match:
                            created_at = datetime.strptime(date_match.group(1), '%Y-%m-%d %H:%M:%S')
                
                article = {
                    'title': title,
                    'link': link,
                    'summary': summary,
                    'image_url': image_url,
                    'created_at': created_at
                }
                
                # DB에 저장
                result = news_jumpball.update_one(
                    {'link': link},
                    {'$set': article},
                    upsert=True
                )
                
                print(f"\n=== 기사 복구 완료 ===")
                print(f"제목: {title}")
                print(f"작성일시: {created_at}")
                
                return jsonify({'message': 'Article restored successfully'})
        
        return jsonify({'error': 'Article not found in search results'}), 404

    except Exception as e:
        print(f"Restore error: {str(e)}")
        return jsonify({'error': str(e)}), 500



