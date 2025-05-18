import os
import json
import time
import re
from bs4 import BeautifulSoup
from elasticsearch import Elasticsearch

# import hazm

# تنظیمات اتصال به Elasticsearch
es = Elasticsearch(['http://localhost:9200'])

# تنظیمات نمایه
index_name = 'web_search'
index_settings = {
    'settings': {
        'number_of_shards': 1,
        'number_of_replicas': 0,
        'analysis': {
            'char_filter': {
                'zero_width_spaces': {
                    'type': 'mapping',
                    'mappings': [
                        '\\u200C=> '  # تبدیل نیم‌فاصله به فاصله
                    ]
                }
            },
            'filter': {
                'persian_stop': {
                    'type': 'stop',
                    'stopwords': '_persian_'
                },
                'persian_normalization': {
                    'type': 'persian_normalization'
                }
            },
            'analyzer': {
                'persian_analyzer': {
                    'tokenizer': 'standard',
                    'char_filter': [
                        'zero_width_spaces'
                    ],
                    'filter': [
                        'lowercase',
                        'decimal_digit',
                        'persian_normalization',
                        'persian_stop'
                    ]
                }
            }
        }
    },
    'mappings': {
        'properties': {
            'url': {'type': 'keyword'},
            'title': {
                'type': 'text',
                'analyzer': 'persian_analyzer'
            },
            'content': {
                'type': 'text',
                'analyzer': 'persian_analyzer'
            }
        }
    }
}

# ایجاد نمایه اگر وجود نداشته باشد
if not es.indices.exists(index=index_name):
    es.indices.create(index=index_name, body=index_settings)
    print(f"Index '{index_name}' created successfully")


def normalize_text(text):
    """نرمال‌سازی متن فارسی"""
    if not text:
        return ""

    # تبدیل ی و ک عربی به فارسی
    text = text.replace('ي', 'ی').replace('ك', 'ک')

    # حذف کاراکترهای اضافی
    text = re.sub(r'[^\w\s\u0600-\u06FF]', ' ', text)

    # حذف فاصله‌های اضافی
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def extract_text_from_html(html_content):
    """استخراج عنوان و متن از محتوای HTML"""
    soup = BeautifulSoup(html_content, 'lxml')

    # استخراج عنوان
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string
    # اگر تگ title خالی بود، سعی کنیم از h1 استفاده کنیم
    elif soup.h1 and soup.h1.text:
        title = soup.h1.text
    # اگر h1 هم نبود، از متا تگ‌ها استفاده کنیم
    else:
        meta_title = soup.find('meta', {'name': 'title'}) or soup.find('meta', {'property': 'og:title'})
        if meta_title and meta_title.get('content'):
            title = meta_title.get('content')

    # استخراج متن اصلی
    for script in soup(['script', 'style']):
        script.extract()

    text = soup.get_text()

    # نرمال‌سازی متن
    title = normalize_text(title)
    text = normalize_text(text)

    return title, text


def read_crawled_data(file_path):
    """خواندن داده‌های خزش شده از فایل"""
    documents = []

    try:
        # بررسی فرمت فایل ورودی
        # این قسمت باید با توجه به فرمت داده‌های خزش شده تغییر کند

        if file_path.endswith('.jsonl') or file_path.endswith('.json'):
            # فرمت JSONL یا JSON
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.endswith('.jsonl'):
                    # هر خط یک سند JSON
                    for line in f:
                        if line.strip():
                            doc = json.loads(line)
                            documents.append(doc)
                else:
                    # کل فایل یک آرایه JSON
                    data = json.load(f)
                    if isinstance(data, list):
                        documents = data
                    else:
                        documents = [data]
        else:
            # فرمت های دیگر
            print(f"Unsupported file format: {file_path}")
            return []

    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return []

    print(f"Read {len(documents)} documents from {file_path}")
    return documents


def index_documents(documents):
    """نمایه‌سازی اسناد در Elasticsearch"""
    start_time = time.time()
    count = 0

    # حذف نمایه قبلی برای اطمینان از بازسازی کامل
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
        print(f"Existing index '{index_name}' deleted")

    # ایجاد نمایه جدید
    es.indices.create(index=index_name, body=index_settings)
    print(f"Index '{index_name}' created successfully")

    for doc in documents:
        try:
            # اطمینان از وجود فیلدهای url و content
            if 'url' not in doc or 'content' not in doc:
                continue

            url = doc['url']
            html_content = doc['content']

            title, content = extract_text_from_html(html_content)

            # اطمینان از اینکه عنوان خالی نباشد
            if not title or title.strip() == '':
                # اگر عنوان خالی است، بخشی از محتوا را به عنوان عنوان استفاده کنیم
                if content:
                    # استفاده از 50 کاراکتر اول محتوا به عنوان عنوان
                    title = content[:50] + "..." if len(content) > 50 else content
                else:
                    # اگر محتوا هم خالی است، از URL به عنوان عنوان استفاده کنیم
                    title = url

            # ذخیره سند در Elasticsearch
            es.index(
                index=index_name,
                document={
                    'url': url,
                    'title': title,
                    'content': content
                }
            )

            count += 1
            if count % 100 == 0:
                print(f"Indexed {count} documents...")

        except Exception as e:
            print(f"Error processing document: {e}")

    # رفرش کردن نمایه
    es.indices.refresh(index=index_name)

    end_time = time.time()
    elapsed_time = end_time - start_time

    print(f"Indexing completed. {count} documents indexed in {elapsed_time:.2f} seconds.")

    # محاسبه حجم نمایه
    stats = es.indices.stats(index=index_name)
    index_size_bytes = stats['_all']['total']['store']['size_in_bytes']
    index_size_mb = index_size_bytes / (1024 * 1024)

    print(f"Index size: {index_size_mb:.2f} MB")

    return count, elapsed_time, index_size_mb


# اجرای نمایه‌سازی
if __name__ == "__main__":
    # مسیر فایل خروجی خزش
    crawl_output_file = input("Enter the path to the crawled data file: ")

    # خواندن داده‌های خزش شده
    documents = read_crawled_data(crawl_output_file)

    if documents:
        # انجام نمایه‌سازی
        doc_count, indexing_time, index_size = index_documents(documents)

        # ذخیره اطلاعات نمایه‌سازی برای استفاده بعدی
        with open("indexing_stats.json", "w", encoding="utf-8") as f:
            json.dump({
                "document_count": doc_count,
                "indexing_time_seconds": indexing_time,
                "index_size_mb": index_size,
                "timestamp": time.time()
            }, f, ensure_ascii=False, indent=2)

        print("Indexing statistics saved to indexing_stats.json")