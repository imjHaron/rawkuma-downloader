import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from time import sleep
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
import contextlib
import threading
from tkinter import Tk, Label, Button, Text, filedialog, Entry, END, StringVar, ttk, Scrollbar, VERTICAL, RIGHT, Y

BASE_OUTPUT_DIR = "E:/Manga/Rawkuma"
LANGUAGE = "en"
_driver_lock = threading.Lock()


def sanitize_filename(name):
    return re.sub(r'[^\w\-. ]', '_', name)

def setup_browser():
    with _driver_lock:
        options = uc.ChromeOptions()
        options.headless = True
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        return uc.Chrome(options=options)

def download_chapter(chapter_url, series_title="Unknown_Series"):
    try:
        driver = setup_browser()
        try:
            driver.get(chapter_url)
            sleep(1.5)
            previous_height = 0
            stable_count = 0
            while True:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                sleep(1)
                current_height = driver.execute_script("return document.body.scrollHeight")
                if current_height == previous_height:
                    stable_count += 1
                    if stable_count >= 2:
                        break
                else:
                    stable_count = 0
                    previous_height = current_height

            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img.ts-main-image"))
            )

            match = re.search(r"-chapter-([\d.]+)", chapter_url)
            chapter_number = match.group(1) if match else "unknown"
            chapter_folder = os.path.join(BASE_OUTPUT_DIR, series_title, f"chapter {chapter_number}")

            if os.path.exists(chapter_folder):
                existing_files = [f for f in os.listdir(chapter_folder) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
                if existing_files:
                    update_log(f"Skipped (exists): chapter {chapter_number}\n")
                    return

            os.makedirs(chapter_folder, exist_ok=True)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            images = driver.find_elements(By.CSS_SELECTOR, 'img.ts-main-image')
            image_urls = [img.get_attribute("src") for img in images if img.get_attribute("src")]

            total = len(image_urls)
            for idx, url in enumerate(image_urls, 1):
                ext = os.path.splitext(urlparse(url).path)[-1] or ".jpg"
                filename = os.path.join(chapter_folder, f"{idx:03}{ext}")
                try:
                    img_data = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}).content
                    with open(filename, "wb") as f:
                        f.write(img_data)
                    progress = int((idx / total) * 100)
                    progress_var.set(progress)
                    progress_bar.update_idletasks()
                except:
                    update_log(f"Failed to download image {idx} in chapter {chapter_number}\n")

        finally:
            with contextlib.suppress(Exception):
                driver.quit()

        update_log(f"Done: chapter {chapter_number}\n")

    except:
        update_log(f"Failed: {chapter_url}\n")

def extract_chapter_number(link):
    match = re.search(r"-chapter-([\d.]+)", link)
    return float(match.group(1)) if match else 0

def get_all_chapter_links(series_url):
    driver = setup_browser()
    try:
        driver.get(series_url)
        sleep(3)
        html = driver.page_source
        with open("debug_rawkuma.html", "w", encoding="utf-8") as f:
            f.write(html)
        soup = BeautifulSoup(html, "html.parser")
    finally:
        with contextlib.suppress(Exception):
            driver.quit()

    series_title_tag = soup.select_one("h1.entry-title")
    series_title = sanitize_filename(series_title_tag.get_text(strip=True)) if series_title_tag else "Unknown_Series"

    chapter_links = [a["href"] for a in soup.select("ul.clstyle li .eph-num a[href]")]
    chapter_links = sorted(set(chapter_links), key=extract_chapter_number)
    return series_title, chapter_links

def update_log(message):
    log_output.insert(END, message)
    log_output.see(END)

def select_folder():
    global BASE_OUTPUT_DIR
    folder = filedialog.askdirectory()
    if folder:
        BASE_OUTPUT_DIR = folder
        folder_label.config(text=f"Save to: {BASE_OUTPUT_DIR}")

def start_download():
    url = url_entry.get().strip()
    if not url:
        return
    log_output.delete(1.0, END)
    update_log("Fetching chapters...\n")
    series_title, chapter_list = get_all_chapter_links(url)
    update_log(f"Total: {len(chapter_list)} chapters\n")

    def run():
        for chapter_url in chapter_list:
            progress_var.set(0)
            download_chapter(chapter_url, series_title)
        update_log("All done!\n")

    threading.Thread(target=run).start()

def reset_gui():
    log_output.delete(1.0, END)
    url_entry.delete(0, END)
    progress_var.set(0)

root = Tk()
root.title("Rawkuma Downloader Lite")

Label(root, text="Rawkuma URL:").pack()
url_entry = Entry(root, width=80)
url_entry.pack()

Button(root, text="Choose Folder", command=select_folder).pack()
folder_label = Label(root, text=f"Save to: {BASE_OUTPUT_DIR}")
folder_label.pack()

Button(root, text="Start", command=start_download).pack(side="left")
Button(root, text="Reset", command=reset_gui).pack(side="left")

progress_var = StringVar()
progress_var.set(0)
progress_bar = ttk.Progressbar(root, variable=progress_var, maximum=100, length=400)
progress_bar.pack(pady=5)

log_output = Text(root, height=20, width=100)
log_output.pack()
scrollbar = Scrollbar(root, command=log_output.yview, orient=VERTICAL)
scrollbar.pack(side=RIGHT, fill=Y)
log_output.config(yscrollcommand=scrollbar.set)

root.mainloop()
