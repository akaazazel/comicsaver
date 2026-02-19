import os
import argparse
import time
import requests
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from tqdm import tqdm

def setup_driver(headless=False):
    """Sets up Chrome driver in headless mode."""
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    # Suppress logging
    chrome_options.add_argument("--log-level=3")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def download_image(url, folder, filename, session=None):
    """Downloads an image and saves it to the specified folder."""
    try:
        # Check if file exists
        filepath = os.path.join(folder, filename)
        if os.path.exists(filepath):
            print(f"File exists, skipping: {filepath}")
            return True

        if session:
            response = session.get(url, stream=True)
        else:
            response = requests.get(url, stream=True)

        response.raise_for_status()

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)
        print(f"Downloaded: {filepath}")
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False

def extract_issue_links(driver, comic_url):
    """Extracts all issue links from a comic landing page."""
    print(f"Loading comic page: {comic_url}")
    driver.get(comic_url)

    # Wait for listing to appear
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.listing"))
        )
    except:
        print("Timeout waiting for listing table.")

    soup = BeautifulSoup(driver.page_source, 'html.parser')

    issue_links = []
    # Search for links that look like issues inside listing table
    listing = soup.find('table', class_='listing')
    if listing:
        for a in listing.find_all('a', href=True):
            href = a['href']
            # Avoid duplicate/irrelevant links
            if '/Issue-' in href or '/Issue_' in href or 'id=' in href:
                full_url = urljoin(comic_url, href)
                if full_url not in issue_links:
                    issue_links.append(full_url)
    else:
        # Fallback
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/Issue-' in href:
                full_url = urljoin(comic_url, href)
                if full_url not in issue_links:
                    issue_links.append(full_url)

    # Reverse to start from Issue 1
    return list(reversed(issue_links))

import concurrent.futures

def download_image_wrapper(args):
    """Wrapper for download_image to be used with ThreadPoolExecutor."""
    return download_image(*args)

def scrape_issue(driver, issue_url, output_dir, max_threads=1):
    """Scrapes images from a single issue."""
    print(f"Processing issue: {issue_url}")

    # Force "All Pages" mode
    if 'readType=1' not in issue_url:
        all_pages_url = issue_url + ('&' if '?' in issue_url else '?') + 'quality=hq&readType=1'
    else:
        all_pages_url = issue_url + ('&' if '?' in issue_url else '?') + 'quality=hq'

    driver.get(all_pages_url)


    # Scroll down the page incrementally to trigger lazy loading
    print("Scrolling to load all images...")

    last_height = driver.execute_script("return document.body.scrollHeight")

    scroll_attempts = 0
    max_attempts = 150 # Safety break
    consecutive_no_change = 0
    max_no_change = 3

    with tqdm(total=max_attempts, desc="Scrolling", unit="step") as pbar:
        while scroll_attempts < max_attempts:
            # Scroll down by window height
            driver.execute_script("window.scrollBy(0, window.innerHeight);")
            time.sleep(1) # Wait for load

            # Check heights
            new_height = driver.execute_script("return document.body.scrollHeight")
            current_scroll = driver.execute_script("return window.pageYOffset + window.innerHeight")

            if new_height == last_height and current_scroll >= new_height:
                 consecutive_no_change += 1
                 pbar.set_description(f"Scrolling (Checking bottom {consecutive_no_change}/{max_no_change})")
                 time.sleep(2)

                 # Re-check height
                 new_height = driver.execute_script("return document.body.scrollHeight")
                 if new_height == last_height:
                     if consecutive_no_change >= max_no_change:
                         pbar.write("Reached bottom of page (confirmed).")
                         break
                 else:
                     consecutive_no_change = 0 # It grew!
                     pbar.set_description("Scrolling")
            else:
                 consecutive_no_change = 0
                 pbar.set_description("Scrolling")

            last_height = new_height
            scroll_attempts += 1
            pbar.update(1)

    # Wait for images to load.
    # Logic: Wait for div#divImage img to have a src that is NOT blank.gif or loading.gif
    print("Waiting for images to settle...")
    try:
        WebDriverWait(driver, 30).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "div#divImage img[src*='blogspot']")) > 0 or
                      len(d.find_elements(By.CSS_SELECTOR, "div#divImage img[src*='googleusercontent']")) > 0
        )
        # Give a bit more time for all images to settle
        time.sleep(5)
    except Exception as e:
        print("Timeout waiting for images to load. Continuing to parse what we have...")

    # Get page source after JS execution
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Prepare session with cookies from selenium for downloading
    session = requests.Session()
    # Transfer cookies
    selenium_cookies = driver.get_cookies()
    for cookie in selenium_cookies:
        session.cookies.set(cookie['name'], cookie['value'])
    # Add User-Agent
    session.headers.update({'User-Agent': driver.execute_script("return navigator.userAgent;")})

    # Directory setup
    path_parts = [p for p in urlparse(issue_url).path.split('/') if p]
    if len(path_parts) >= 3:
        comic_name = path_parts[1]
        issue_name = path_parts[2]
    else:
        comic_name = 'UnknownComic'
        issue_name = 'UnknownIssue'

    save_dir = os.path.join(output_dir, comic_name, issue_name)
    os.makedirs(save_dir, exist_ok=True)

    image_urls = []

    # Extract images from div#divImage
    div_image = soup.find('div', id='divImage')
    if div_image:
        # User specified images are inside p tags, but generic find_all('img') inside div is robust
        imgs = div_image.find_all('img')
        for img in imgs:
            src = img.get('src')
            if src and not src.endswith('blank.gif') and not src.endswith('loading.gif'):
                 image_urls.append(src)

    image_urls = list(dict.fromkeys(image_urls)) # Unique

    if not image_urls:
        print("No images found even with Selenium!")
        return

    print(f"Found {len(image_urls)} images. Downloading with {max_threads} threads...")

    download_tasks = []
    for i, img_url in enumerate(image_urls):
        ext = 'jpg'
        if '.png' in img_url: ext = 'png'
        if '.gif' in img_url: ext = 'gif'

        filename = f"{i+1:03d}.{ext}"
        download_tasks.append((img_url, save_dir, filename, session))

    if max_threads > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
            executor.map(download_image_wrapper, download_tasks)
    else:
        for task in download_tasks:
            download_image(*task)

def main():
    parser = argparse.ArgumentParser(description="Scrape comics from readcomiconline.li")
    parser.add_argument("url", help="URL of the comic or issue")
    parser.add_argument("-o", "--output", default="Comics", help="Output directory")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("-t", "--threads", type=int, default=1, help="Number of download threads (default: 1)")

    args = parser.parse_args()

    url = args.url
    output_dir = args.output
    threads = args.threads

    if 'readcomiconline' not in url:
        print("Warning: URL might not be from readcomiconline.li")


    print("Setting up Selenium driver...")
    driver = setup_driver(args.headless)

    try:
        # Determine if Comic or Issue
        clean_url = url.split('?')[0]
        path_parts = [p for p in urlparse(clean_url).path.split('/') if p]

        is_issue = False
        if len(path_parts) >= 3 and ('Issue' in path_parts[-1] or 'issue' in path_parts[-1]):
            is_issue = True

        if is_issue:
            scrape_issue(driver, url, output_dir, max_threads=threads)
        else:
            print("Detected Comic Page. Searching for issues...")
            issues = extract_issue_links(driver, url)
            print(f"Found {len(issues)} issues.")
            for issue in issues:
                scrape_issue(driver, issue, output_dir, max_threads=threads)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
