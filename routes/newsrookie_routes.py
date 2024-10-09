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

def should_crawl(db):
    crawl_info = db['crawl_info'].find_one({'name': 'rookie_last_crawl'})
    if not crawl_info:
        return True
    last_crawl_date = crawl_info['date']
    return datetime.now() - last_crawl_date > timedelta(days=30)

def crawl_data(query, db):
    base_url = 'https://www.rookie.co.kr/news/articleList.html'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
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
        page_articles = extract_articles(soup, query, existing_links, articles)
        print(f"Articles found on page {page} from Rookie: {page_articles}")

    if articles:
        news_rookie.insert_many(articles)
    
    return articles

def extract_articles(soup, query, existing_links, articles):
    page_articles = 0
    for item in soup.select('#section-list > ul > li'):
        title_tag = item.select_one('.titles a')
        summary_tag = item.select_one('.lead a')
        date_tag = item.select_one('.byline em:last-child')

        if title_tag:
            title = title_tag.text.strip()
            summary = summary_tag.text.strip() if summary_tag else ""
            
            if "원조 머슬녀" in title or "원조 머슬녀" in summary:
                print(f"Excluding article with keyword: {title}")
                continue

            if query in title or query in summary:
                link = 'https://www.rookie.co.kr' + title_tag['href']
                
                if link in existing_links:
                    print(f"Duplicate article found, skipping: {link}")
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
                page_articles += 1
    return page_articles

@newsrookie_bp.route('/api/rookie/search/', strict_slashes=False)
def search_rookie():
    query = request.args.get('q')
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400

    db = current_app.config['db']
    news_rookie = db['news_rookie']

    if should_crawl(db):
        print("Performing monthly crawl...")
        crawl_data(query, db)
        db['crawl_info'].update_one(
            {'name': 'rookie_last_crawl'},
            {'$set': {'date': datetime.now()}},
            upsert=True
        )
    else:
        print("Using existing data from the last crawl.")

    articles = list(news_rookie.find({
        '$or': [
            {'title': {'$regex': query, '$options': 'i'}}
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
