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
    StaleElementReferenceException,
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

# Initialize the WebDriver
options = webdriver.ChromeOptions()
# options.add_argument("--headless")  # Uncomment this if you want to run headless
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")  # Set a larger window size
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Base URL
base_url = 'https://www.skipthedishes.com'

# Set to keep track of processed merchant URLs
processed_merchants = set()

# Function to scroll down incrementally
def scroll_down(driver, scroll_pause_time=0.5, scroll_increment=500):
    driver.execute_script(f"window.scrollBy(0, {scroll_increment});")
    time.sleep(scroll_pause_time)

# Function to scrape the merchant page using the correct inner code
def scrape_merchant(merchant_url, error_log, city, save_directory):
    try:
        # Open a new tab
        driver.execute_script("window.open('');")
        # Switch to the new tab
        driver.switch_to.window(driver.window_handles[-1])
        # Navigate to the merchant URL
        driver.get(merchant_url)
        wait = WebDriverWait(driver, 10)

        # Scroll to load all content
        def scroll_to_bottom(driver, scrolls=100):
            for _ in range(scrolls):
                driver.execute_script("window.scrollBy(0, 200);")  # Scroll down by 200 pixels
                time.sleep(0.1)  # Wait for new content to load

        scroll_to_bottom(driver)

        # Scrape merchant name
        merchant_name_selectors = [
            {'type': 'xpath', 'value': '//*[@id="partner-details-wrapper"]/div/div[1]/div/h1'},
            {'type': 'css', 'value': '#partner-details-wrapper > div > div.sc-bbf989ce-2.gwyuah > div > h1'},
            {'type': 'xpath', 'value': '//h1[@data-testid="restaurant-name"]'},
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
            {'type': 'xpath', 'value': '//div[@data-testid="restaurant-address"]'},
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
            {'type': 'xpath', 'value': '//img[@data-testid="restaurant-image"]'},
        ]
        image_elements = find_elements_by_selectors(driver, banner_image_selectors)
        if image_elements:
            banner_image_url = image_elements[0].get_attribute('src')
        else:
            banner_image_url = ""
            print(f"Banner image not found at {merchant_url}")

        # Initialize the menu dictionary
        menu = {}

        # Find all category containers
        category_selectors = [
            {'type': 'xpath', 'value': '//div[@id and .//h2]'},
            {'type': 'css', 'value': 'div.menu-category'},
        ]

        categories = find_elements_by_selectors(driver, category_selectors)

        if not categories:
            print(f"No categories found at {merchant_url}")
        else:
            for category in categories:
                # Extract category name
                category_name_selectors = [
                    {'type': 'xpath', 'value': './/h2'},
                    {'type': 'css', 'value': 'h2'},
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
                    {'type': 'xpath', 'value': './/div[contains(@class, "menu-item")]'},
                    {'type': 'css', 'value': 'div.menu-item'},
                ]
                dish_items = find_elements_by_selectors(category, dish_item_selectors)

                for dish in dish_items:
                    dish_name = "Not found"
                    dish_price = None
                    dish_description = ""
                    dish_img_url = ""

                    # Dish name
                    dish_name_selectors = [
                        {'type': 'xpath', 'value': './/h3'},
                        {'type': 'css', 'value': 'h3'},
                    ]
                    dish_name_element = find_element_by_selectors(dish, dish_name_selectors)
                    if dish_name_element:
                        dish_name = dish_name_element.text.strip()
                    else:
                        print(f"Dish name not found in category {category_name} at {merchant_url}")

                    # Dish price
                    dish_price_selectors = [
                        {'type': 'xpath', 'value': './/span[contains(@class, "price-amount")]'},
                        {'type': 'css', 'value': 'span.price-amount'},
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
                            dish_price = None
                    else:
                        print(f"Dish price not found for {dish_name} in category {category_name} at {merchant_url}")

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
                        {'type': 'xpath', 'value': './/img'},
                        {'type': 'css', 'value': 'img'},
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

        # Close the merchant tab and switch back to the main window
        driver.close()
        driver.switch_to.window(driver.window_handles[0])

        # Prepare to save the data
        filename = sanitize_filename(merchant_name)
        file_path = os.path.join(save_directory, f"{filename}.json")
        data_to_save = {
            'merchant_name': merchant_name,
            'address': address,
            'banner_image_url': banner_image_url,
            'menu': menu,
            'city': city,
            'merchant_url': merchant_url,
        }

        # Save the data to a JSON file
        with open(file_path, 'w', encoding='utf-8') as json_file:
            json.dump(data_to_save, json_file, ensure_ascii=False, indent=2)

        print(f"Merchant data saved to {file_path}")

    except Exception as e:
        error_log.append(f"Failed to scrape merchant at {merchant_url}: {e}")
        print(f"Failed to scrape merchant at {merchant_url}: {e}")
        # Close the merchant tab if it's still open
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])

# Main function to scrape merchants for a list of cities
def main():
    cities = ['richmond', 'vancouver']  # Add more cities as needed
    error_log = []

    # Base directory where the JSON files will be saved
    base_save_directory = r'D:\skip\Uber_menu'  # Update the path as needed

    for city in cities:
        print(f"\nProcessing city: {city}")

        # Create a save directory for the city
        save_directory = os.path.join(base_save_directory, city)
        os.makedirs(save_directory, exist_ok=True)

        # Open the city restaurants page
        city_url = f'{base_url}/{city}/restaurants'
        driver.get(city_url)
        time.sleep(5)  # Wait for the page to load

        # Initialize variables
        processed_merchants = set()
        scroll_times = 0
        max_scroll_times = 50  # Adjust as needed

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
                if href and href not in processed_merchants:
                    if href.startswith('/'):
                        full_url = base_url + href
                    elif href.startswith('http'):
                        full_url = href
                    else:
                        full_url = base_url + '/' + href
                    current_merchant_urls.append(full_url)
                    processed_merchants.add(href)

            if not current_merchant_urls:
                print("No new merchants found in this scroll.")
                continue

            print(f"Found {len(current_merchant_urls)} new merchants.")

            # For each new merchant, open in a new tab and scrape data
            for merchant_url in current_merchant_urls:
                scrape_merchant(merchant_url, error_log, city, save_directory)

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