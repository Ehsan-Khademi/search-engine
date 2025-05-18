import requests
from bs4 import BeautifulSoup
import json
import time
import random
import os
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor
import logging
from tqdm import tqdm
import argparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("crawler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("WebCrawler")


class WebCrawler:
    def __init__(self, start_url, max_pages=4000, output_file="crawled_data.json",
                 delay_min=1, delay_max=3, max_workers=10):
        self.start_url = start_url
        self.max_pages = max_pages
        self.output_file = output_file
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_workers = max_workers

        # Parse domain from start URL
        parsed_url = urlparse(start_url)
        self.domain = parsed_url.netloc

        # Set for visited URLs to avoid duplicates
        self.visited_urls = set()
        # Queue of URLs to crawl
        self.url_queue = [start_url]
        # List to store crawled data
        self.crawled_data = []

        # User agent rotation to avoid blocks
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0'
        ]

    def get_random_user_agent(self):
        """Return a random user agent from the list"""
        return random.choice(self.user_agents)

    def fetch_url(self, url):
        """Fetch and parse a URL, respecting rate limits"""
        # Add random delay to avoid overloading the server
        time.sleep(random.uniform(self.delay_min, self.delay_max))

        headers = {'User-Agent': self.get_random_user_agent()}

        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.text
            else:
                logger.warning(f"Failed to fetch {url}: Status code {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None

    def parse_page(self, url, html_content):
        """Parse the HTML content to extract title, content, and links"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract title
            title = soup.title.string.strip() if soup.title else "No Title"

            # Extract content (text from paragraphs, removing scripts, styles, etc.)
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            # Get text from main content elements
            content_tags = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'article', 'section', 'div.content'])
            content = " ".join([tag.get_text().strip() for tag in content_tags])
            content = " ".join(content.split())  # Normalize whitespace

            # Extract links for further crawling
            links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                # Convert relative URLs to absolute
                absolute_url = urljoin(url, href)
                # Only include URLs from the same domain
                if urlparse(absolute_url).netloc == self.domain:
                    links.append(absolute_url)

            return {
                "title": title,
                "url": url,
                "content": content,
                "links": links
            }
        except Exception as e:
            logger.error(f"Error parsing {url}: {str(e)}")
            return {
                "title": "Error",
                "url": url,
                "content": "",
                "links": []
            }

    def process_url(self, url):
        """Process a single URL: fetch, parse, and extract data"""
        html_content = self.fetch_url(url)
        if html_content:
            parsed_data = self.parse_page(url, html_content)

            # Save the parsed data without links
            page_data = {
                "title": parsed_data["title"],
                "url": url,
                "content": parsed_data["content"]
            }

            # Return both the data to save and links to crawl
            return page_data, parsed_data["links"]
        return None, []

    def save_data(self):
        """Save the crawled data to a JSON file"""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.crawled_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.crawled_data)} pages to {self.output_file}")
        except Exception as e:
            logger.error(f"Error saving data: {str(e)}")

    def crawl(self):
        """Start the crawling process"""
        logger.info(f"Starting crawl from {self.start_url}, targeting {self.max_pages} pages")

        pbar = tqdm(total=self.max_pages, desc="Pages crawled")

        try:
            while self.url_queue and len(self.crawled_data) < self.max_pages:
                # Take a batch of URLs to process in parallel
                batch_size = min(self.max_workers, self.max_pages - len(self.crawled_data), len(self.url_queue))
                if batch_size <= 0:
                    break

                current_batch = []
                for _ in range(batch_size):
                    if not self.url_queue:
                        break
                    url = self.url_queue.pop(0)
                    if url not in self.visited_urls:
                        current_batch.append(url)
                        self.visited_urls.add(url)

                if not current_batch:
                    continue

                # Process the batch in parallel
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    results = list(executor.map(self.process_url, current_batch))

                # Process results and update the queue
                for page_data, links in results:
                    if page_data:
                        self.crawled_data.append(page_data)
                        pbar.update(1)

                        # Save periodically
                        if len(self.crawled_data) % 100 == 0:
                            self.save_data()

                        # Add new links to the queue
                        for link in links:
                            if link not in self.visited_urls and link not in self.url_queue:
                                self.url_queue.append(link)

                # Log progress
                logger.info(f"Crawled {len(self.crawled_data)} pages, {len(self.url_queue)} URLs in queue")

                # Check if we have reached the target
                if len(self.crawled_data) >= self.max_pages:
                    break

            # Final save
            self.save_data()
            pbar.close()
            logger.info(f"Crawling completed. Saved {len(self.crawled_data)} pages to {self.output_file}")

        except KeyboardInterrupt:
            logger.warning("Crawling interrupted by user")
            self.save_data()
            pbar.close()
        except Exception as e:
            logger.error(f"Error during crawling: {str(e)}")
            self.save_data()
            pbar.close()


def main():
    parser = argparse.ArgumentParser(description='Web Crawler')
    parser.add_argument('start_url', help='The URL to start crawling from')
    parser.add_argument('--max-pages', type=int, default=4000, help='Maximum number of pages to crawl (default: 4000)')
    parser.add_argument('--output', default='crawled_data.json', help='Output JSON file (default: crawled_data.json)')
    parser.add_argument('--delay-min', type=float, default=1.0,
                        help='Minimum delay between requests in seconds (default: 1.0)')
    parser.add_argument('--delay-max', type=float, default=3.0,
                        help='Maximum delay between requests in seconds (default: 3.0)')
    parser.add_argument('--max-workers', type=int, default=10, help='Maximum number of worker threads (default: 10)')

    args = parser.parse_args()

    crawler = WebCrawler(
        start_url=args.start_url,
        max_pages=args.max_pages,
        output_file=args.output,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        max_workers=args.max_workers
    )

    crawler.crawl()


if __name__ == "__main__":
    main()