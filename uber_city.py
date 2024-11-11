import time
import json
import os
import re
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
    # Remove or replace invalid characters
    return re.sub(r'[<>:"/\\|?*]', '', name)

# Function to sanitize city names for URL construction
def format_city_name_for_url(city_name):
    formatted_name = city_name.lower()
    formatted_name = re.sub(r'\s+', '-', formatted_name)  # Replace spaces with hyphens
    formatted_name = re.sub(r'[^\w\-]', '', formatted_name)  # Remove non-alphanumeric characters except hyphens
    return formatted_name

# Initialize the set to keep track of processed merchants
processed_merchants = set()

# Function to scrape a single merchant
def scrape_merchant(merchant_url, error_log, city, save_directory):
    # Check if the merchant has already been processed
    if merchant_url in processed_merchants:
        print(f"Merchant already processed: {merchant_url}")
        return
    try:
        driver.get(merchant_url)

        # Adding a wait to ensure the page has fully loaded
        time.sleep(3)  # Initial wait time to allow loading

        # Function to incrementally scroll down the page until no more content loads
        def scroll_to_bottom(driver, scrolls=100):
            for _ in range(scrolls):
                driver.execute_script("window.scrollBy(0, 200);")  # Scroll down by 200 pixels
                time.sleep(0.1)  # Wait for new content to load

        # Execute the scrolling function to load all dishes
        scroll_to_bottom(driver)

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
            error_log.append(f"Error locating categories or dishes in {merchant_url}: {e}")
            return  # Exit the function if categories cannot be found

        # Create a data structure to save, including merchant details and menu
        data_to_save = {
            'merchant_name': merchant_name,
            'address': address,
            'banner_image_url': banner_image_url,
            'menu': menu,
            'cities': [city]  # Initialize with the current city
        }

        # Sanitize merchant name for filename
        filename = sanitize_filename(merchant_name)

        # Full path to save the JSON file
        file_path = os.path.join(save_directory, f"{filename}.json")

        # Save the data to a JSON file
        with open(file_path, 'w', encoding='utf-8') as json_file:
            json.dump(data_to_save, json_file, ensure_ascii=False, indent=2)

        print(f"Merchant data saved to {file_path}")

        # Add the merchant to the set of processed merchants
        processed_merchants.add(merchant_url)

    except (WebDriverException, Exception) as e:
        error_log.append(f"Failed to scrape merchant at {merchant_url}: {e}")
        print(f"Failed to scrape merchant at {merchant_url}: {e}")
        return  # Exit the function if any exception occurs

# Function to scrape all merchants in a category
def scrape_category(category_url, error_log, city, save_directory):
    try:
        driver.get(category_url)

        # Adding a wait to ensure the page has fully loaded
        time.sleep(3)  # Initial wait time to allow loading

        # Scroll to load all merchants
        def scroll_to_load_merchants(driver, scrolls=50):
            for _ in range(scrolls):
                driver.execute_script("window.scrollBy(0, 400);")  # Scroll down by 400 pixels
                time.sleep(0.1)  # Wait for new content to load

        scroll_to_load_merchants(driver)

        # Selectors to find all merchant links
        merchant_link_selectors = [
            {'type': 'xpath', 'value': '//*[@id="main-content"]/div[4]/div/div/a'},
            {'type': 'css', 'value': 'a[data-testid="store-card"]'},
            {'type': 'xpath', 'value': '//a[contains(@href, "/ca/store/")]'},
        ]

        # Find all merchant links
        merchant_links = find_elements_by_selectors(driver, merchant_link_selectors)

        if not merchant_links:
            print(f"No merchants found on the category page: {category_url}")
            return

        # Extract the URLs from the merchant links
        merchant_urls = []
        for link in merchant_links:
            href = link.get_attribute('href')
            if href:
                merchant_urls.append(href)

        # Remove duplicate URLs
        merchant_urls = list(set(merchant_urls))

        # Iterate over each merchant URL
        for index, merchant_url in enumerate(merchant_urls):
            print(f"Scraping merchant {index + 1}/{len(merchant_urls)} in category {category_url}: {merchant_url}")
            try:
                scrape_merchant(merchant_url, error_log, city, save_directory)
            except Exception as e:
                error_log.append(f"Unexpected error with merchant at {merchant_url}: {e}")
                print(f"Unexpected error with merchant at {merchant_url}: {e}")

    except Exception as e:
        error_log.append(f"Failed to scrape category at {category_url}: {e}")
        print(f"Failed to scrape category at {category_url}: {e}")

# Main logic to traverse categories on the main page
def main():
    # List of cities to process
    cities = [
        'abbotsford',
        'richmond',
        'vancouver'
        # Add more city names as needed
    ]

    # Base URL format
    city_url_template = 'https://www.ubereats.com/ca/category/{}-bc/'

    # Base directory where the JSON files will be saved
    base_save_directory = r'E:\Uber\Uber_menu'

    # Ensure the base directory exists
    os.makedirs(base_save_directory, exist_ok=True)

    # List to store errors
    error_log = []

    # Iterate over each city
    for city in cities:
        formatted_city = format_city_name_for_url(city)
        print(f"\nProcessing city: {city}")

        # Construct the city URL
        main_category_url = city_url_template.format(formatted_city)

        # Create a save directory for the city
        save_directory = os.path.join(base_save_directory, city)
        os.makedirs(save_directory, exist_ok=True)

        try:
            driver.get(main_category_url)

            # Adding a wait to ensure the page has fully loaded
            time.sleep(3)  # Initial wait time to allow loading

            # Scroll to load all categories
            def scroll_to_load_categories(driver, scrolls=10):
                for _ in range(scrolls):
                    driver.execute_script("window.scrollBy(0, 400);")  # Scroll down by 400 pixels
                    time.sleep(0.1)  # Wait for new content to load

            scroll_to_load_categories(driver)

            # Selectors to find all category links
            category_link_selectors = [
                {'type': 'xpath', 'value': '//*[@id="main-content"]/div[2]/div[3]/a'},
                {'type': 'css', 'value': 'a[data-test]'},
                {'type': 'xpath', 'value': '//a[contains(@href, "/ca/category/")]'},
            ]

            # Find all category links
            category_links = find_elements_by_selectors(driver, category_link_selectors)

            if not category_links:
                print(f"No categories found on the main category page for {city}.")
                continue  # Skip to the next city

            # Extract the URLs from the category links
            category_urls = []
            for link in category_links:
                href = link.get_attribute('href')
                if href:
                    # Construct the full URL if necessary
                    if href.startswith('/'):
                        href = 'https://www.ubereats.com' + href
                    category_urls.append(href)

            # Remove duplicate URLs
            category_urls = list(set(category_urls))

            # Iterate over each category URL
            for index, category_url in enumerate(category_urls):
                print(f"\nScraping category {index + 1}/{len(category_urls)} in {city}: {category_url}")
                try:
                    scrape_category(category_url, error_log, city, save_directory)
                except Exception as e:
                    error_log.append(f"Unexpected error with category at {category_url}: {e}")
                    print(f"Unexpected error with category at {category_url}: {e}")

        except Exception as e:
            error_log.append(f"Failed to process city {city}: {e}")
            print(f"Failed to process city {city}: {e}")

    # Close the WebDriver
    driver.quit()
    print("\nScraping completed.")

    # Report errors after the scraping is done
    if error_log:
        print("\nErrors encountered during scraping:")
        for error in error_log:
            print(error)
    else:
        print("\nNo errors encountered during scraping.")

if __name__ == "__main__":
    main()