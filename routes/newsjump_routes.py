from flask import Blueprint, request, jsonify, current_app
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

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
    query = request.args.get('q')
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400

    db = current_app.config['db']
    news_jumpball = db['news_jumpball']

    if should_crawl(db):
        print("Performing monthly crawl...")
        total_articles = perform_crawl(query, db)
        if total_articles:
            news_jumpball.delete_many({})
            news_jumpball.insert_many(total_articles)
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
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    articles = []

    params = {
        'q': query,
        'sfld': 'subj',
        'period': 'custom',
        'startyear': year,
        'endyear': year,
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
        page_articles = extract_articles(soup, query, db)
        print(f"Articles found on page {page} for year {year}: {page_articles}")

    return articles

def extract_articles(soup, query, db):
    articles = []
    news_jumpball = db['news_jumpball']
    for item in soup.select('#listWrap .listPhoto'):
        title_tag = item.select_one('dt a')
        summary_tag = item.select_one('.conts')
        if title_tag:
            title = title_tag.text.strip()
            summary = summary_tag.text.strip() if summary_tag else ""
            if query in title or query in summary:
                print(f"Found title: {title}")
                link = 'https://jumpball.co.kr' + title_tag['href']

                article_response = requests.get(link)
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
    return articles

