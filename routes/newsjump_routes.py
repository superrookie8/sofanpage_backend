from flask import Blueprint, request, jsonify
import requests
from bs4 import BeautifulSoup

newsjump_bp = Blueprint('newsjump_bp', __name__)

def crawl_data(query):
    base_url =""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    total_pages = 40
    articles = []

    for page in range(1, total_pages + 1 ):
        params = {
            'sc_word' : query, 
            'view_type' : 'sm', 
            'page' :page
        }
        print(f"Crawling page {page}")
        response = requests.get(base_url, headers=headers, params=params)
        if response.status_code !=200:
            print(f"Failed to retrieve data for page {page}: {response.status_code}")
            continue

        soup = BeautifulSoup(response.content, 'html.parser')
        page_articles = 0
        for item in soup.select('#section-list > ul > li'):
            title_tag = item.select_one('.titles a')
            if title_tag :
                title = title_tag.text.strip()
                if query in title:
                    print(f"Found title: {title}")
                    link = 'https://www.rookie.co.kr' + title_tag['href']

                    summary_tag = item.select_one('.lead a')
                    summary = summary_tag.text.strip() if summary_tag else 'No summary available'

                    articles.append({'title':title, 'link':link, 'summary':summary})
                    page_articles += 1
        print(f"Articles found on page {page}: {page_articles}")

        articles.sort(key=lambda x: x['link'], reverse= True)
        print(f"Total articles found: {len(articles)}")
        return articles 

@newsjump_bp.route('/api/search')
def search_jumpball():
    query = request.args.get('q')
    if not query:
        return jsonify({'error' : 'Query parameter is required'}), 400

        crawl_data(query)
        jsonify(data)

