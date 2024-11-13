import time
import os
import random
import json
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Setup Chrome options
options = webdriver.ChromeOptions()
# options.add_argument("--headless")  # Uncomment this if you want to run headless
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")  # Set a larger window size

# Initialize the WebDriver
driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()), options=options
)

# Function to find an element using multiple selectors
def find_element_by_selectors(context, selectors):
    for selector in selectors:
        try:
            if selector['type'] == 'xpath':
                return context.find_element(By.XPATH, selector['value'])
            elif selector['type'] == 'css':
                return context.find_element(By.CSS_SELECTOR, selector['value'])
        except NoSuchElementException:
            continue
    return None  # If none of the selectors match

# Function to scrape merchants
def scrape_merchants(driver):
    # XPath for all merchant containers
    merchant_containers_xpath = '//*[@id="scrollableDiv"]/div[1]/div/div/div/div'
    merchant_containers = driver.find_elements(By.XPATH, merchant_containers_xpath)

    merchants = []
    for container in merchant_containers:
        try:
            name_element = container.find_element(By.XPATH, './/div/div/div/a/div/div[2]/div[1]')
            name = name_element.text.strip()
            url_element = find_element_by_selectors(container, [
                {'type': 'xpath', 'value': './/div/div/div/a'},
                {'type': 'css', 'value': 'a'}
            ])
            url = url_element.get_attribute('href') if url_element else ""
            description_element = find_element_by_selectors(container, [
                {'type': 'xpath', 'value': './/div/div[2]/span[3]'},
                {'type': 'css', 'value': 'div.info > div.others > span.stateLabel'}
            ])
            description = description_element.text.strip() if description_element else "No description available"
            merchants.append({'name': name, 'url': url, 'description': description})
        except NoSuchElementException:
            continue

    return merchants

# Main scraping function
def scrape_category(category_url, save_directory):
    try:
        driver.get(category_url)

        # Adding an explicit wait to ensure the page has fully loaded
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "scrollableDiv")))

        time.sleep(120)
        # Check for graphic verification code (CAPTCHA)
        try:
            captcha_element = driver.find_element(By.XPATH, '//div[contains(@class, "captcha")]')
            print("Graphic verification code detected. Please solve it manually and press Enter to continue...")
            input("Press Enter after solving the captcha...")
        except NoSuchElementException:
            pass

        # Scrape merchant information
        merchants = scrape_merchants(driver)

        # Save results to an Excel file
        if not os.path.exists(save_directory):
            os.makedirs(save_directory)
        excel_path = os.path.join(save_directory, 'merchants_chinese.xlsx')

        # Append new data if the file already exists
        if os.path.exists(excel_path):
            existing_df = pd.read_excel(excel_path)
            new_df = pd.DataFrame(merchants)
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            # Remove duplicates based on the 'url' column
            combined_df.drop_duplicates(subset='url', keep='first', inplace=True)
            combined_df.to_excel(excel_path, index=False)
        else:
            df = pd.DataFrame(merchants)
            df.to_excel(excel_path, index=False)

        print(f"Scraped {len(merchants)} merchants.")

    except (TimeoutException, WebDriverException) as e:
        print(f"Error occurred: {e}")

    finally:
        driver.quit()

# URL of the category page to scrape
category_url = "https://www.fantuanorder.com/zh-CN/city/white-rock-bc"
save_directory = "E:/scraped_data"

# Run the scraping function
scrape_category(category_url, save_directory)