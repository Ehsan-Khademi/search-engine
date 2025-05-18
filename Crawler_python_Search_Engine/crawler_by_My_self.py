import logging
import re
from collections import deque
from urllib.request import urlopen
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time
import requests
from urllib.robotparser import RobotFileParser
class Crawler:
    def __init__(self,max_crawl_pages,start_url):
        self.max_crawl_pages=max_crawl_pages
        self.start_url=start_url
        self.visited_urls=set()
        self.current_urls=deque()

    def fetching_urls(self,url):
        try:
            # data = urlopen(url,timeout=10).read()
            data=requests.get(url, timeout=10)
            data.encoding="utf-8"
            return data.text
            # Set timeout to 10 seconds
        except Exception as e:
            print("Error of fetching⛔\n")
            return "Empty"


    def parse_url(self,url):
        try:
            robots_url = f"{url}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            if rp.can_fetch("*", url):
                # fromat_urls = urlopen(url,timeout=10)

                fromat_urls = requests.get(url, timeout=10)  # Set timeout to 10 seconds
                fromat_urls.raise_for_status()
                soup = BeautifulSoup(fromat_urls.text, 'html.parser')
                # print(soup)
                print(fromat_urls)
                print("Allowed to crawl...⏸️")
        # urls = []
                for link in soup.find_all('a'):
                    self.current_urls.appendleft(link.get('href'))
            else:
                print("Blocked by robots.txt⛔\n")
                return "Empty"
        except Exception as e:
            print('the error of parsing⛔\n')
            return "Empty"

    def checker(self,url):
        if url in self.visited_urls:
            print('this url is already visited❗❗\n')
            return True
    def save_metadata(self,data,index):
        print(f"the page {index} saved ✅ ...\n")
        with open(f"page{index}.html","w",encoding="utf-8") as f:
            f.write(data)

    def validate_url(self,url):
        new_url=url
        if not url:
            return "Invalid"
        elif url is not None and url.startswith("//"):
            new_url = "https:" + url
        elif url is not None and  url.startswith("/"):
            new_url=self.start_url+url
        else:
            pass
        regex = re.compile(
            r'^(?:http|ftp)s?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        if re.match(regex, new_url) is not None:
            return new_url
        return "Invalid"



    def run(self):
        self.current_urls.appendleft(self.start_url)
        # print(self.start_url)
        count=1
        seen_url_numbers=0
        while count<=self.max_crawl_pages:
            new_url=self.current_urls.pop()
            # if new_url.startswith("//"):
            #     new_url = "https:" + new_url
            new_url=self.validate_url(new_url)
            if new_url=="Invalid":
              continue
            print(new_url)
            seen_url_numbers+=1
            parsing_return=self.parse_url(new_url)
            # if parsing_return=="Empty":
            #     continue
            data = self.fetching_urls(new_url)
            if self.checker(new_url):
                # self.current_urls.remove(new_url)
                continue
            self.visited_urls.add(new_url)
            if data=="Empty":
                continue

            self.save_metadata(data,count)
            count+=1
        print(f"the total number of visited urls is {seen_url_numbers}")





if __name__ == '__main__':
    crawler=Crawler(4000,"https://wikipedia.org/")
    begin=time.time()
    crawler.run()
    end=time.time()
    print("all of pages were saved 🌟")
    print(f"the total time taken is {end-begin} ⏳")


