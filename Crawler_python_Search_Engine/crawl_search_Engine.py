import requests
from bs4 import BeautifulSoup
import urllib.parse
from urllib.robotparser import RobotFileParser
import time
import os
import json
from collections import deque
import re
import logging


class Crawler:
    def __init__(self, start_url, max_pages=4000, delay=1, output_dir='crawled_pages'):
        # تنظیمات اولیه خزشگر
        self.start_url = start_url
        self.max_pages = max_pages
        self.delay = delay
        self.output_dir = output_dir

        # استخراج دامنه از URL شروع
        parsed_url = urllib.parse.urlparse(start_url)
        self.domain = parsed_url.netloc
        self.scheme = parsed_url.scheme

        # ساختارهای داده مورد نیاز
        self.queue = deque([start_url])  # صف URLs برای بررسی
        self.visited_urls = set()  # مجموعه URLs بازدید شده
        self.url_to_id = {}  # نگاشت URL به شناسه عددی
        self.page_count = 0  # شمارنده صفحات دانلود شده

        # تنظیم لاگر
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("crawler.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

        # ایجاد دایرکتوری خروجی اگر وجود ندارد
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            os.makedirs(os.path.join(output_dir, 'html'))

        # تنظیم robots.txt parser
        self.robots_parser = RobotFileParser()
        robots_url = f"{self.scheme}://{self.domain}/robots.txt"
        self.robots_parser.set_url(robots_url)
        try:
            self.robots_parser.read()
            self.logger.info(f"robots.txt خوانده شد از {robots_url}")
        except Exception as e:
            self.logger.warning(f"خطا در خواندن robots.txt: {e}")

    def is_valid_url(self, url):
        """بررسی اعتبار URL برای خزش"""
        try:
            parsed = urllib.parse.urlparse(url)

            # بررسی اینکه URL از همان دامنه باشد
            if parsed.netloc != self.domain:
                return False

            # بررسی پسوند فایل - فقط صفحات HTML
            path = parsed.path.lower()
            invalid_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.css', '.js',
                                  '.zip', '.tar', '.gz', '.mp3', '.mp4', '.avi', '.mov']

            if any(path.endswith(ext) for ext in invalid_extensions):
                return False

            # بررسی مجوز robots.txt
            if not self.robots_parser.can_fetch("*", url):
                self.logger.info(f"URL توسط robots.txt مسدود شده است: {url}")
                return False

            return True
        except Exception as e:
            self.logger.warning(f"خطا در بررسی اعتبار URL {url}: {e}")
            return False

    def fetch_page(self, url):
        """دریافت صفحه از URL (Fetcher)"""
        try:
            headers = {
                'User-Agent': 'PythonWebCrawler/1.0',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'fa,en;q=0.9',
            }

            response = requests.get(url, headers=headers, timeout=10)

            # بررسی کد وضعیت HTTP
            if response.status_code != 200:
                self.logger.warning(f"کد وضعیت نامعتبر ({response.status_code}) برای {url}")
                return None

            # بررسی نوع محتوا - فقط HTML
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type.lower():
                self.logger.info(f"نوع محتوای نامعتبر ({content_type}) برای {url}")
                return None

            return response.text
        except Exception as e:
            self.logger.warning(f"خطا در دریافت {url}: {e}")
            return None

    def parse_page(self, html_content, base_url):
        """تجزیه صفحه HTML برای استخراج لینک‌ها (Parser)"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            links = []

            # استخراج تمام لینک‌ها
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']

                # تبدیل URL نسبی به URL مطلق
                absolute_url = urllib.parse.urljoin(base_url, href)

                # حذف انکرها (#) از URL
                absolute_url = re.sub(r'#.*$', '', absolute_url)

                if self.is_valid_url(absolute_url) and absolute_url not in self.visited_urls:
                    links.append(absolute_url)

            return links
        except Exception as e:
            self.logger.warning(f"خطا در تجزیه HTML برای {base_url}: {e}")
            return []

    def save_page(self, url, html_content):
        """ذخیره صفحه HTML دانلود شده"""
        try:
            # ایجاد شناسه منحصر به فرد برای URL
            page_id = self.page_count
            self.url_to_id[url] = page_id

            # ذخیره محتوای HTML
            html_path = os.path.join(self.output_dir, 'html', f"{page_id}.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            self.logger.info(f"صفحه {page_id} ذخیره شد: {url}")
            return True
        except Exception as e:
            self.logger.warning(f"خطا در ذخیره {url}: {e}")
            return False

    def save_metadata(self):
        """ذخیره فراداده‌ها شامل نگاشت URL به شناسه"""
        try:
            metadata = {
                'total_pages': self.page_count,
                'domain': self.domain,
                'url_mapping': {str(v): k for k, v in self.url_to_id.items()}
            }

            metadata_path = os.path.join(self.output_dir, 'metadata.json')
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            self.logger.info(f"فراداده‌ها با موفقیت ذخیره شدند")
        except Exception as e:
            self.logger.warning(f"خطا در ذخیره فراداده‌ها: {e}")

    def start(self):
        """شروع فرآیند خزش"""
        self.logger.info(f"خزش شروع شد از {self.start_url}")
        self.logger.info(f"حداکثر تعداد صفحات: {self.max_pages}")

        start_time = time.time()

        while self.queue and self.page_count < self.max_pages:
            # برداشتن URL از صف
            current_url = self.queue.popleft()

            # بررسی اینکه آیا قبلاً بازدید شده است
            if current_url in self.visited_urls:
                continue

            self.logger.info(f"در حال بررسی {self.page_count + 1}/{self.max_pages}: {current_url}")

            # دریافت صفحه
            html_content = self.fetch_page(current_url)

            if not html_content:
                # اضافه کردن به لیست بازدید شده در صورت شکست
                self.visited_urls.add(current_url)
                continue

            # ذخیره صفحه
            saved = self.save_page(current_url, html_content)

            if saved:
                # افزایش شمارنده صفحات
                self.page_count += 1

                # تجزیه صفحه برای یافتن لینک‌های جدید
                new_links = self.parse_page(html_content, current_url)

                # اضافه کردن لینک‌های جدید به صف
                for link in new_links:
                    if link not in self.visited_urls and link not in self.queue:
                        self.queue.append(link)

            # اضافه کردن به لیست بازدید شده
            self.visited_urls.add(current_url)

            # تأخیر برای رعایت ادب
            # time.sleep(self.delay)

            # گزارش وضعیت دوره‌ای
            if self.page_count % 100 == 0:
                elapsed = time.time() - start_time
                self.logger.info(f"وضعیت: {self.page_count} صفحه در {elapsed:.2f} ثانیه - {len(self.queue)} URL در صف")

        # ذخیره فراداده‌ها در پایان
        self.save_metadata()

        elapsed = time.time() - start_time
        self.logger.info(f"خزش به پایان رسید. {self.page_count} صفحه در {elapsed:.2f} ثانیه دانلود شد.")
        self.logger.info(f"تعداد کل URLهای بازدید شده: {len(self.visited_urls)}")


# مثال استفاده
if __name__ == "__main__":
    # دامنه مورد نظر خود را اینجا قرار دهید
    start_url = "https://huggingface.co"

    crawler = Crawler(
        start_url=start_url,
        max_pages=10,  # حداکثر 4000 صفحه
        delay=1,  # تأخیر 1 ثانیه بین درخواست‌ها
        output_dir='crawled_pages'  # دایرکتوری خروجی
    )

    crawler.start()
