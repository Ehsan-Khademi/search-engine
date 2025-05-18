# فایل app.py - برای رابط کاربری تحت وب (مرحله آنلاین)
# این فایل در فاز آنلاین اجرا می‌شود و رابط کاربری تحت وب را فراهم می‌کند

from flask import Flask, render_template, request, jsonify
from elasticsearch import Elasticsearch
import time
import json
import re

app = Flask(__name__)

# تنظیمات اتصال به Elasticsearch
es = Elasticsearch(['http://localhost:9200'])
index_name = 'web_search'

# بارگذاری اطلاعات نمایه‌سازی
try:
    with open("indexing_stats.json", "r", encoding="utf-8") as f:
        indexing_stats = json.load(f)
except Exception as e:
    print(f"Error loading indexing stats: {e}")
    indexing_stats = {
        "document_count": 0,
        "indexing_time_seconds": 0,
        "index_size_mb": 0
    }


def normalize_query(query):
    """نرمال‌سازی عبارت جستجو"""
    # تبدیل ی و ک عربی به فارسی
    query = query.replace('ي', 'ی').replace('ك', 'ک')
    return query


def build_elasticsearch_query(query_string):
    """ساخت پرس‌وجوی Elasticsearch با پشتیبانی از عملگر AND"""
    # بررسی وجود عملگر AND صریح
    if "AND" in query_string:
        # تقسیم پرس‌وجو به اجزا
        terms = query_string.split("AND")
        # ساخت پرس‌وجو با عملگر AND
        should_clauses = []
        for term in terms:
            term = term.strip()
            # حذف پرانتز اضافی
            term = re.sub(r'^\(|\)', '', term).strip()
            if term:
                should_clauses.append({
                    "multi_match": {
                        "query": term,
                        "fields": ["title^3", "content"],
                        "operator": "and"
                    }
                })

        return {
            "query": {
                "bool": {
                    "must": should_clauses
                }
            }
        }
    else:
        # استفاده از عملگر AND به صورت پیش‌فرض برای تمام کلمات
        return {
            "query": {
                "multi_match": {
                    "query": query_string,
                    "fields": ["title^3", "content"],
                    "operator": "and"
                }
            }
        }


@app.route('/')
def home():
    return render_template('index.html', stats=indexing_stats)


@app.route('/search')
def search():
    query = request.args.get('q', '')
    start_time = time.time()

    if not query.strip():
        return jsonify({
            'results': [],
            'total': 0,
            'time': 0
        })

    # نرمال‌سازی پرس‌وجو
    normalized_query = normalize_query(query)

    # ساخت پرس‌وجوی Elasticsearch
    es_query = build_elasticsearch_query(normalized_query)

    # اضافه کردن بخش highlight به پرس‌وجو
    es_query.update({
        "highlight": {
            "fields": {
                "content": {
                    "fragment_size": 150,
                    "number_of_fragments": 1,
                    "pre_tags": ["<b>"],
                    "post_tags": ["</b>"]
                },
                "title": {
                    "number_of_fragments": 0,
                    "pre_tags": ["<b>"],
                    "post_tags": ["</b>"]
                }
            }
        },
        "_source": ["url", "title"],
        "size": 20
    })

    # اجرای جستجو
    response = es.search(index=index_name, body=es_query)

    end_time = time.time()
    search_time = end_time - start_time

    results = []
    for hit in response['hits']['hits']:
        # استخراج عنوان از نتیجه - با بررسی highlight اگر موجود باشد
        if 'highlight' in hit and 'title' in hit['highlight']:
            title = hit['highlight']['title'][0]
        else:
            title = hit['_source'].get('title', '')

        # اگر عنوان خالی باشد، از "بدون عنوان" استفاده می‌کنیم
        if not title or title.strip() == '':
            title = "بدون عنوان"

        url = hit['_source']['url']

        # ساخت خلاصه
        if 'highlight' in hit and 'content' in hit['highlight']:
            summary = hit['highlight']['content'][0]
        else:
            summary = "بدون خلاصه"

        results.append({
            'title': title,
            'url': url,
            'summary': summary,
            'score': hit['_score']
        })

    return jsonify({
        'results': results,
        'total': response['hits']['total']['value'],
        'time': search_time
    })


if __name__ == '__main__':
    print("Web search engine is running at http://localhost:5000")
    app.run(debug=True)