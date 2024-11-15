#innercodeforsinglemerchant

import time
import json
import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Setup Chrome options
options = webdriver.ChromeOptions()
# options.add_argument("--headless")  # Uncomment this if you want to run headless
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")  # Set a larger window size

# Initialize the WebDriver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Define the URL of the merchant's website
# You can replace this URL with any Uber Eats merchant URL you want to scrape
url = 'https://www.ubereats.com/ca/store/jufeng-yuan-restaurant/D0veocUKWIGQjG7McqkW_g?srsltid=AfmBOooBLi9VNtA6Y-bYlysDkPsokmNmjviLo02dpkvPqJAd2bneVAXJ'
driver.get(url)

# Adding a wait to ensure the page has fully loaded
time.sleep(3)  # Initial wait time to allow loading

# Function to incrementally scroll down the page until no more content loads
def scroll_to_bottom(driver, scrolls=100):
    for _ in range(scrolls):
        driver.execute_script("window.scrollBy(0, 200);")  # Scroll down by 200 pixels
        time.sleep(0.1)  # Wait for new content to load
# Execute the scrolling function to load all dishes
scroll_to_bottom(driver)

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

# Function to find multiple elements using multiple selectors
def find_elements_by_selectors(context, selectors):
    for selector in selectors:
        try:
            if selector['type'] == 'xpath':
                elements = context.find_elements(By.XPATH, selector['value'])
            elif selector['type'] == 'css':
                elements = context.find_elements(By.CSS_SELECTOR, selector['value'])
            if elements:
                return elements
        except NoSuchElementException:
            continue
    return []  # If none of the selectors match

# Scrape merchant name
merchant_name_selectors = [
    {'type': 'css', 'value': 'h1'},
    {'type': 'xpath', 'value': '//h1'},
]
merchant_name_element = find_element_by_selectors(driver, merchant_name_selectors)
if merchant_name_element:
    merchant_name = merchant_name_element.text.strip()
else:
    merchant_name = "Not found"
    print("Merchant name not found")

# Scrape address
address_selectors = [
    {'type': 'xpath', 'value': '//*[@id="main-content"]/div/div[2]/div/div/div[3]/div/section/ul/button[1]/div[2]/div[1]/p[1]'},
    {'type': 'css', 'value': 'address'},
    {'type': 'xpath', 'value': '//button[@data-testid="store-info-address"]'},
]
address_element = find_element_by_selectors(driver, address_selectors)
if address_element:
    address = address_element.text.strip()
else:
    address = "Not found"
    print("Address not found")

# Scrape banner image
banner_image_selectors = [
    {'type': 'xpath', 'value': '//*[@id="main-content"]/div/div[1]/div/div[1]/img'},
    {'type': 'css', 'value': 'img[data-test-id="store-banner-image"]'},
    {'type': 'xpath', 'value': '//img[contains(@class, "ce ce")]'},
]
image_element = find_element_by_selectors(driver, banner_image_selectors)
if image_element:
    banner_image_url = image_element.get_attribute('src')
else:
    banner_image_url = "Not found"
    print("Banner image not found")

# Dictionary to hold all categories and their dishes
menu = {}

# List of category names to exclude
categories_to_exclude = ["Buy 1, Get 1 Free", "Offers"]

# Selectors to find all category containers
category_selectors = [
    {'type': 'xpath', 'value': '//*[@id="main-content"]/div/div[7]/div/div/div/div/ul/li'},
    {'type': 'xpath', 'value': '//*[@id="main-content"]/div/div[6]/div/div/div/div/ul/li'},
    {'type': 'xpath', 'value': '//div[@data-test="store-menu-category"]'},
    {'type': 'xpath', 'value': '//ul[contains(@class, "c9 c2 c8")]/li'},
    {'type': 'xpath', 'value': '//h3/ancestor::div[contains(@class, "store-menu-section")]'},
]

# Wait for the categories to be present
try:
    categories = find_elements_by_selectors(driver, category_selectors)
    if not categories:
        print("No categories found")
    else:
        for category in categories:
            # Extract category name
            category_name_selectors = [
                {'type': 'xpath', 'value': './/div/div/div/div[1]/div/h3'},
                {'type': 'xpath', 'value': './/h3'},
                {'type': 'css', 'value': 'h3'},
            ]
            category_name_element = find_element_by_selectors(category, category_name_selectors)
            if category_name_element:
                category_name = category_name_element.text.strip()
            else:
                category_name = "Uncategorized"

            # Skip the category if it's in the exclusion list
            if category_name in categories_to_exclude:
                print(f"Skipping category: {category_name}")
                continue  # Skip to the next category

            # Initialize the list for dishes in this category
            menu[category_name] = []

            # Selectors to find all dish items within this category
            dish_item_selectors = [
                {'type': 'xpath', 'value': './/div/ul/li'},
                {'type': 'xpath', 'value': './/ul/li'},
                {'type': 'xpath', 'value': './/div[@role="listitem"]'},
            ]
            dish_items = find_elements_by_selectors(category, dish_item_selectors)

            for dish in dish_items:
                dish_name = "Not found"
                dish_price = None  # Initialize as None
                dish_description = ""
                dish_img_url = ""

                # Dish name selectors
                dish_name_selectors = [
                    {'type': 'xpath', 'value': './/a/div/div[1]/div[1]/div[1]/span'},
                    {'type': 'xpath', 'value': './/h4'},
                    {'type': 'xpath', 'value': './/span[contains(@class, "c1e c1f")]'},
                    {'type': 'css', 'value': 'a > div > div > div > div > span'},
                ]
                dish_name_element = find_element_by_selectors(dish, dish_name_selectors)
                if dish_name_element:
                    dish_name = dish_name_element.text.strip()
                else:
                    print("Dish name not found")

                # Dish price selectors
                dish_price_selectors = [
                    {'type': 'xpath', 'value': './/a/div/div[1]/div[1]/div[2]/span'},
                    {'type': 'xpath', 'value': './/div[contains(@class, "c1i")]/span'},
                    {'type': 'css', 'value': 'a > div > div > div > div > span[data-test="menu-item-price"]'},
                    {'type': 'xpath', 'value': './/span[contains(@data-test, "menu-item-price")]'},
                ]
                dish_price_element = find_element_by_selectors(dish, dish_price_selectors)
                if dish_price_element:
                    try:
                        price_text = dish_price_element.text
                        price_text = price_text.replace('$', '').replace('£', '').replace('€', '').replace(',', '').strip()
                        dish_price = int(float(price_text) * 100)
                    except Exception as e:
                        print(f"Dish price not found or could not be processed: {e}")
                        dish_price = None
                else:
                    print("Dish price element not found")

                # Dish description selectors
                dish_description_selectors = [
                    {'type': 'xpath', 'value': './/a/div/div[1]/div[1]/div[3]/div/span'},
                    {'type': 'xpath', 'value': './/a/div/div[1]/div[1]/div[2]/div/span'},
                    {'type': 'xpath', 'value': './/p[contains(@class, "menu-item-description")]'},
                    {'type': 'xpath', 'value': './/div[contains(@class, "c1h c1k")]/span'},
                    {'type': 'css', 'value': 'a > div > div > div > div > div > span'},
                ]
                dish_description_element = find_element_by_selectors(dish, dish_description_selectors)
                if dish_description_element:
                    dish_description = dish_description_element.text.strip()
                else:
                    dish_description = ""

                # Dish image selectors
                dish_image_selectors = [
                    {'type': 'xpath', 'value': './/a/div/div[1]/div[2]/div[1]/picture/img'},
                    {'type': 'xpath', 'value': './/img[contains(@class, "c1l")]'},
                    {'type': 'css', 'value': 'img[data-test="menu-item-image"]'},
                    {'type': 'xpath', 'value': './/img[contains(@src, "menu-items")]'},
                ]
                dish_img_element = find_element_by_selectors(dish, dish_image_selectors)
                if dish_img_element:
                    dish_img_url = dish_img_element.get_attribute('src')
                else:
                    dish_img_url = ""

                # Add the dish to the category list
                menu[category_name].append({
                    'dish_name': dish_name,
                    'dish_description': dish_description,
                    'dish_img_url': dish_img_url,
                    'dish_price': dish_price
                })

except Exception as e:
    print(f"Error locating categories or dishes: {e}")

# Close the WebDriver
driver.quit()

# Prepare to save the menu as a JSON file
def sanitize_filename(name):
    # Remove or replace invalid characters
    return re.sub(r'[<>:"/\\|?*]', '', name)

# Directory where the JSON file will be saved
save_directory = r'E:\Uber\Uber_menu'

# Ensure the directory exists
os.makedirs(save_directory, exist_ok=True)

# Sanitize merchant name for filename
filename = sanitize_filename(merchant_name)

# Full path to save the JSON file
file_path = os.path.join(save_directory, f"{filename}.json")

# Create a data structure to save, including merchant details and menu
data_to_save = {
    'merchant_name': merchant_name,
    'address': address,
    'banner_image_url': banner_image_url,
    'menu': menu
}

# Save the data to a JSON file
with open(file_path, 'w', encoding='utf-8') as json_file:
    json.dump(data_to_save, json_file, ensure_ascii=False, indent=2)

print(f"Menu data saved to {file_path}")