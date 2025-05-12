import os
import time
import subprocess
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
from pydub import AudioSegment
from tqdm import tqdm  # Import the progress bar library

# ⚠️ Set your ffmpeg path
AudioSegment.ffmpeg = "path/to/ffmpeg"

# ✅ Replace this with your actual chromedriver path
chrome_path = r"C:\Users\timur\PycharmProjects\bandcamp_wishing\chromedriver.exe"

# Input Bandcamp username
username = input("Enter your Bandcamp username: ")
username_link = f"https://bandcamp.com/{username}/wishlist"


def parse_bandcamp_collection(html):
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("li.collection-item-container")

    subscriber_exclusive = []
    regular_items = []

    for item in items:
        # Check for subscriber-exclusive items
        subscribe_link = item.find('a', href=lambda x: x and '/subscribe' in x)
        is_subscriber_only = subscribe_link is not None

        # Extract title and artist
        title_div = item.select_one(".collection-item-title")
        artist_div = item.select_one(".collection-item-artist")
        link_tag = item.select_one("a.item-link")

        if not (title_div and artist_div and link_tag):
            continue

        title = title_div.text.strip()
        artist = artist_div.text.strip().replace("by ", "")
        url = link_tag.get("href")

        item_data = {
            "title": title,
            "artist": artist,
            "url": url,
            "subscriber_only": is_subscriber_only
        }

        if is_subscriber_only:
            subscriber_exclusive.append(item_data)
            print(f"🔒 Found subscriber-exclusive: {title} by {artist}")
        else:
            regular_items.append(item_data)
    return {
        "subscriber_exclusive": subscriber_exclusive,
        "regular_items": regular_items
    }


class BandcampWishlistScraper:
    def __init__(self):
        service = Service(chrome_path)
        self.driver = webdriver.Chrome(service=service)
        self.driver.set_window_size(1200, 800)

    def close(self):
        self.driver.quit()

    def scrape_wishlist(self, username_link):
        self.driver.get(username_link)

        # Random scrolling to mimic human behavior
        for _ in range(5):
            x = random.randint(0, self.driver.execute_script("return window.innerWidth"))
            y = random.randint(0, self.driver.execute_script("return window.innerHeight"))
            self.driver.execute_script(f"window.scrollTo({x}, {y});")
            time.sleep(0.01)

        # Click "Show More" if available
        try:
            element = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#wishlist-items .show-more"))
            )
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(1)
            try:
                element.click()
            except:
                self.driver.execute_script("arguments[0].click();", element)
        except:
            pass

        # Detect how many items to scroll for
        try:
            wishlist_li = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'li[data-tab="wishlist"]'))
            )
            count_span = wishlist_li.find_element(By.CSS_SELECTOR, 'span.count')
            total_items = int(count_span.text.strip())
            scroll_times = total_items // 12
            print(f"📦 Total wishlist items: {total_items}, scrolling {scroll_times} times.")
        except Exception as e:
            print(f"❌ Could not detect wishlist count: {e}")
            scroll_times = 40

        scroll_step = 5000
        current_scroll = 0

        # Initialize progress bar
        with tqdm(total=scroll_times,
                  desc="🔄 Scrolling",
                  bar_format="{desc}: {percentage:3.0f}%|{bar}|",
                  ncols=50,
                  leave=True) as pbar:

            for _ in range(scroll_times):
                self.driver.execute_script(f"window.scrollTo(0, {current_scroll});")
                time.sleep(0.6)
                current_scroll += scroll_step
                pbar.update(1)

        print("✅ Finished scrolling. Now parsing with BeautifulSoup...")
        html = self.driver.page_source
        return parse_bandcamp_collection(html)


def convert_tmp_to_mp3(directory):
    for filename in os.listdir(directory):
        if filename.endswith(".tmp"):
            tmp_path = os.path.join(directory, filename)
            mp3_path = os.path.join(directory, filename.replace(".tmp", ".mp3"))

            try:
                audio = AudioSegment.from_file(tmp_path)
                audio.export(mp3_path, format="mp3")
                os.remove(tmp_path)
                print(f"✅ Converted: {filename} → {mp3_path}")
            except Exception as e:
                print(f"❌ Failed to convert {filename}: {e}")


def download_album(album_url, save_path="downloads"):
    os.makedirs(save_path, exist_ok=True)

    command = [
        "bandcamp-dl",
        "--base-dir", save_path,
        "--no-slugify",
        album_url
    ]

    try:
        subprocess.run(command, check=True)
        convert_tmp_to_mp3(save_path)
        print(f"✅ Download complete: {album_url}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to download album: {album_url}\nError: {e}")


if __name__ == "__main__":
    scraper = BandcampWishlistScraper()
    try:
        results = scraper.scrape_wishlist(username_link)

        print("\n=== DOWNLOADING ITEMS ===")
        for item in results["regular_items"]:
            download_album(item["url"])

        print("\n=== SUBSCRIBER-EXCLUSIVE ITEMS (NOT DOWNLOADED) ===")
        for item in results["subscriber_exclusive"]:
            print(f"🔒 Skipping subscriber-exclusive: {item['title']} by {item['artist']}")

    finally:
        scraper.close()