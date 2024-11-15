import time 
import os
import re
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

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

# Function to sanitize filenames
def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', '', name)

# Setup Chrome options
options = webdriver.ChromeOptions()
# options.add_argument("--headless")  # Uncomment this if you want to run headless
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")  # Set a larger window size

# Initialize the WebDriver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Base URL
base_url = 'https://www.skipthedishes.com'

# Global set to track processed merchants
processed_merchants_global = set()

# Function to scroll down incrementally
def scroll_down(driver, scroll_pause_time=0.5, scroll_increment=500):
    driver.execute_script(f"window.scrollBy(0, {scroll_increment});")
    time.sleep(scroll_pause_time)

# Function to scrape a single merchant page using your correct inner code
def scrape_merchant(merchant_url, error_log, city, save_directory, base_save_directory):
    if merchant_url in processed_merchants_global:
        print(f"Merchant already scraped: {merchant_url}")
        return

    try:
        # Open a new tab
        driver.execute_script("window.open('');")
        # Switch to the new tab
        driver.switch_to.window(driver.window_handles[-1])
        # Navigate to the merchant URL
        driver.get(merchant_url)
        wait = WebDriverWait(driver, 10)

        # Scroll to load all content
        def scroll_to_bottom(driver, scrolls=200):
            for _ in range(scrolls):
                driver.execute_script("window.scrollBy(0, 400);")  # Scroll down by 200 pixels
                time.sleep(0.1)  # Wait for new content to load

        scroll_to_bottom(driver)

        # Scrape clean URL for the merchant
        clean_url = merchant_url.split("/")[-1]

        # Scrape merchant name
        merchant_name_selectors = [
            {'type': 'xpath', 'value': '//*[@id="partner-details-wrapper"]/div/div[1]/div/h1'},
            {'type': 'css', 'value': '#partner-details-wrapper > div > div.sc-bbf989ce-2.gwyuah > div > h1'},
        ]
        merchant_name_element = find_element_by_selectors(driver, merchant_name_selectors)
        if merchant_name_element:
            merchant_name = merchant_name_element.text.strip()
        else:
            merchant_name = "Not found"
            print(f"Merchant name not found at {merchant_url}")

        # Scrape address
        address_selectors = [
            {'type': 'xpath', 'value': '//*[@id="partner-details-wrapper"]/div/div[1]/div/div/span[1]'},
            {'type': 'css', 'value': '#partner-details-wrapper > div > div.sc-bbf989ce-2.gwyuah > div > div > span.sc-7e19ab74-3.kmUxCA'},
        ]
        address_element = find_element_by_selectors(driver, address_selectors)
        if address_element:
            address = address_element.text.strip()
        else:
            address = "Not found"
            print(f"Address not found at {merchant_url}")

        # Scrape banner image
        banner_image_selectors = [
            {'type': 'xpath', 'value': '//*[@id="__next"]/div/main/div[2]/img'},
            {'type': 'css', 'value': '#__next > div > main > div.sc-c8e71b1-0.dYcQJi > img'},
        ]
        image_elements = find_elements_by_selectors(driver, banner_image_selectors)
        if image_elements:
            banner_image_url = image_elements[0].get_attribute('src')
        else:
            banner_image_url = "Not found"
            print(f"Banner image not found at {merchant_url}")

        # Initialize the menu dictionary
        menu = {}

        # Find all category containers
        category_selectors = [
            {'type': 'xpath', 'value': '//div[@id and .//h2[@class="sc-8992fe5b-3 ljZFdy"]]'},
        ]

        categories = find_elements_by_selectors(driver, category_selectors)

        if not categories:
            print(f"No categories found at {merchant_url}")
        else:
            for category in categories:
                # Extract category name
                category_name_selectors = [
                    {'type': 'xpath', 'value': './/h2[@class="sc-8992fe5b-3 ljZFdy"]'},
                    {'type': 'css', 'value': 'h2.sc-8992fe5b-3.ljZFdy'},
                ]
                category_name_element = find_element_by_selectors(category, category_name_selectors)
                if category_name_element:
                    category_name = category_name_element.text.strip()
                else:
                    category_name = "Uncategorized"

                # Initialize the list for dishes in this category
                menu[category_name] = []

                # Find all dish items within this category
                dish_item_selectors = [
                    {'type': 'xpath', 'value': './/div[contains(@class, "sc-fUnMCh sc-87c0b655-0")]'},
                    {'type': 'css', 'value': 'div.sc-fUnMCh.sc-87c0b655-0'},
                ]
                dish_items = find_elements_by_selectors(category, dish_item_selectors)

                for dish in dish_items:
                    dish_name = "Not found"
                    dish_price = None
                    dish_description = ""
                    dish_img_url = ""

                    # Dish name
                    dish_name_selectors = [
                        {'type': 'xpath', 'value': './/h3[@class="sc-87c0b655-1 jscDUi"]'},
                        {'type': 'css', 'value': 'h3.sc-87c0b655-1.jscDUi'},
                    ]
                    dish_name_element = find_element_by_selectors(dish, dish_name_selectors)
                    if dish_name_element:
                        dish_name = dish_name_element.text.strip()
                    else:
                        print(f"Dish name not found at {merchant_url}")

                    # Dish price
                    dish_price_selectors = [
                        {'type': 'xpath', 'value': './/h4[@class="sc-87c0b655-3 fXBchI"]'},
                        {'type': 'css', 'value': 'h4.sc-87c0b655-3.fXBchI'},
                    ]
                    dish_price_element = find_element_by_selectors(dish, dish_price_selectors)
                    if dish_price_element:
                        price_text = dish_price_element.text.strip()
                        # Process the price text to extract numerical value
                        price_text = re.sub(r'[^\d\.]', '', price_text)
                        try:
                            dish_price = int(float(price_text) * 100)  # Convert to cents
                        except ValueError:
                            print(f"Could not convert price: {price_text} at {merchant_url}")
                            dish_price = "sold out"
                    else:
                        print(f"Dish price not found for {dish_name} at {merchant_url}")

                    # Dish description
                    dish_description_selectors = [
                        {'type': 'xpath', 'value': './/p'},
                        {'type': 'css', 'value': 'p'},
                    ]
                    dish_description_element = find_element_by_selectors(dish, dish_description_selectors)
                    if dish_description_element:
                        dish_description = dish_description_element.text.strip()
                    else:
                        dish_description = ""

                    # Dish image
                    dish_image_selectors = [
                        {'type': 'xpath', 'value': './/img[@class="sc-87c0b655-7 hcMNRH"]'},
                        {'type': 'css', 'value': 'img.sc-87c0b655-7.hcMNRH'},
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

        # Prepare to save the data
        # Ensure save_directory exists
        os.makedirs(save_directory, exist_ok=True)

        # Use the clean URL for filename
        filename = sanitize_filename(clean_url)

        # Full path to save the JSON file
        file_path = os.path.join(save_directory, f"{filename}.json")

        # Create a data structure to save
        data_to_save = {
            'merchant_name': merchant_name,
            'address': address,
            'menu': menu,
            'city': city,
            'merchant_url': merchant_url,
            'banner_image_url': banner_image_url
        }

        # Save the data to a JSON file
        with open(file_path, 'w', encoding='utf-8') as json_file:
            json.dump(data_to_save, json_file, ensure_ascii=False, indent=2)

        print(f"Merchant data saved to {file_path}")

        # Add merchant information to the master list
        merchant_info = {
            'merchant_name': merchant_name,
            'url': merchant_url,
            'address': address,
            'merchant_icon': banner_image_url,
            'clean_url': clean_url
        }
        all_merchants.append(merchant_info)
        processed_merchants_global.add(merchant_url)

        # Update the master list JSON
        master_list_path = os.path.join(base_save_directory, "all_merchants.json")
        with open(master_list_path, 'w', encoding='utf-8') as master_file:
            json.dump(all_merchants, master_file, ensure_ascii=False, indent=2)

    except Exception as e:
        error_log.append(f"Failed to scrape merchant at {merchant_url}: {e}")
        print(f"Failed to scrape merchant at {merchant_url}: {e}")
    finally:
        # Close the merchant tab and switch back to the main window
        driver.close()
        driver.switch_to.window(driver.window_handles[0])

# Main function to scrape merchants for a list of cities
def main():
    global all_merchants, base_save_directory
    all_merchants = []  # Initialize a list to store all merchants' data
    cities = [
        "richmond",
        "vancouver",
        "burnaby",
        "east-vancouver",
        "coquitlam",
        "langley",
        "maple-ridge",
        "new-westminster",
        "north-langley",
        "north-vancouver",
        "port-coquitlam",
        "surrey",
        "delta",
        "vancouver-west-side",
        "white-rock"
    ]
    error_log = []

    # Base directory where the JSON files will be saved
    base_save_directory = r'D:\skip\Skip_menu'  # Update the path as needed

    # Create the master list JSON file at the start
    master_list_path = os.path.join(base_save_directory, "all_merchants.json")
    with open(master_list_path, 'w', encoding='utf-8') as master_file:
        json.dump(all_merchants, master_file, ensure_ascii=False, indent=2)

    total_cities = len(cities)
    for city_index, city in enumerate(cities):
        print(f"\nProcessing city: {city} ({city_index + 1}/{total_cities})")

        # Create a save directory for the city
        save_directory = os.path.join(base_save_directory, city)
        os.makedirs(save_directory, exist_ok=True)

        # Open the city restaurants page
        city_url = f'{base_url}/{city}/restaurants'
        driver.get(city_url)
        time.sleep(5)  # Wait for the page to load

        # Initialize variables
        scroll_times = 0
        max_scroll_times = 500  # Adjust as needed

        while scroll_times < max_scroll_times:
            scroll_times += 1
            print(f"Scrolling down... ({scroll_times}/{max_scroll_times})")
            # Scroll down to load new merchants
            scroll_down(driver, scroll_pause_time=1, scroll_increment=500)

            # Find all merchant links currently visible
            merchant_xpath = '//*[@id="root"]/div/main/div/div/div/div/div[3]/div[2]/div/a'
            merchant_elements = driver.find_elements(By.XPATH, merchant_xpath)

            # Extract merchant URLs
            current_merchant_urls = []
            for element in merchant_elements:
                href = element.get_attribute('href')
                if href and href not in processed_merchants_global:
                    if href.startswith('/'):
                        full_url = base_url + href
                    elif href.startswith('http'):
                        full_url = href
                    else:
                        full_url = base_url + '/' + href
                    current_merchant_urls.append(full_url)

            if not current_merchant_urls:
                print("No new merchants found in this scroll.")
                continue

            print(f"Found {len(current_merchant_urls)} new merchants.")

            # For each new merchant, open in a new tab and scrape data
            for merchant_index, merchant_url in enumerate(current_merchant_urls):
                percentage_done = ((city_index + merchant_index / len(current_merchant_urls)) / total_cities) * 100
                print(f"Scraping merchant ({merchant_index + 1}/{len(current_merchant_urls)}) - Progress: {percentage_done:.2f}%")
                scrape_merchant(merchant_url, error_log, city, save_directory, base_save_directory)

        print(f"Finished processing city: {city}")

    # Close the WebDriver
    driver.quit()

    # Report errors
    if error_log:
        print("\nErrors encountered during scraping:")
        for error in error_log:
            print(error)
    else:
        print("\nNo errors encountered during scraping.")

if __name__ == "__main__":
    main()
