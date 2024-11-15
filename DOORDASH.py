import csv, json, os, re, time
import pandas as pd
from tqdm import tqdm
from DrissionPage import ChromiumPage, ChromiumOptions
from urllib.parse import unquote
import traceback
from parsel import Selector
from loguru import logger
import DrissionPage.errors
from DrissionPage.errors import PageDisconnectedError
from pprint import pprint
from datetime import datetime

current_date = datetime.now()

formatted_date = current_date.strftime('%m%d')

logger.add("D:/scraping_log.txt", rotation="500 MB")

# Store processed URLs in a set to avoid redundant scraping
processed_urls = set()
if os.path.exists('processed_urls.txt'):
    with open('processed_urls.txt', 'r', encoding='utf-8') as f:
        processed_urls = set([line.strip() for line in f.readlines()])

# Load or initialize master JSON
master_file_path = f'D:/All_Data/doordash_{formatted_date}_rawdata/master_data.json'
if os.path.exists(master_file_path):
    with open(master_file_path, 'r', encoding='utf-8') as master_file:
        master_json = json.load(master_file)
else:
    master_json = []

def clean_filename(name):
    name = unquote(name)
    name = name.lower()
    name = name.replace(" ", "-")
    name = re.sub(r'[^a-z0-9\-&]+', '', name)
    return name

def clean_url(url):
    try:
        clean_url = re.search(r'/store/(.*?)/\?cursor', url).group(1)
        return clean_url
    except AttributeError:
        logger.error(f"Failed to extract clean URL from: {url}")
        return clean_filename(url)

def reconnect_page(page):
    try:
        page.close()
    except:
        pass
    options = ChromiumOptions().set_local_port(10020)
    return ChromiumPage(options)

def find_elements_by_selectors(context, selectors):
    for selector in selectors:
        try:
            if selector['type'] == 'xpath':
                elements = context.eles(f'xpath:{selector["value"]}')
            elif selector['type'] == 'css':
                elements = context.eles(f'css:{selector["value"]}')
            if elements:
                return elements
        except DrissionPage.errors.ElementNotFoundError:
            continue
    return []  # If none of the selectors match

def convert_price_to_integer(price_str):
    try:
        # Remove currency symbols and special characters like '+'
        cleaned_price = re.sub(r'[^0-9.]', '', price_str)
        return int(float(cleaned_price) * 100)
    except ValueError:
        logger.error(f"Failed to convert price: {price_str}")
        return None

def process_restaurant(page: ChromiumPage, url, data_path):
    try:
        if url in processed_urls:
            logger.info(f"Skipping already processed URL: {url}")
            return

        page.get(url)
        time.sleep(3)
        html = page.html

        json_data = page.s_ele('@type=application/ld+json').text
        data = json.loads(json_data)

        if data['@type'] == 'Restaurant':
            restaurant_name = data['name']
            data['url'] = url

            data['address'] = re.findall(r'"displayAddress\\":\\"(.*?)\\"', html)[0]
            data['phone'] = re.findall(r'"phoneno\\":\\"(.*?)\\"', html)[0]

            doordashOperationHourInfo = (re.findall(r'"operationSchedule\\":\[(.*)\]}}(.*),\\"banners', html)[0][0]
                                         .replace('\\', "")
                                         .replace('{"__typename":"OperationHours",', "")
                                         .replace("]}", "]"))

            door_pattern = r'"dayOfWeek":"(\w+)".*?"timeSlotList":\["(.*?)"\]'
            door_matches = re.findall(door_pattern, doordashOperationHourInfo, re.DOTALL)

            doordashOperationHourInfo_result = {}
            for day, slots in door_matches:
                doordashOperationHourInfo_result[day] = [slots]

            data['doordashOperationHourInfo'] = doordashOperationHourInfo_result

            storeOperationHourInfo_tmp = (
                (re.findall(r'"operationSchedule\\":\[(.*)\]},\\"doordashOperationHourInfo', html)[0].
                 replace('\\', "").
                 replace('{"__typename":"OperationHours",', "")).
                replace("]}", "]"))

            store_pattern = r'"dayOfWeek":"(\w+)".*?"timeSlotList":\["(.*?)"\]'
            store_matches = re.findall(store_pattern, storeOperationHourInfo_tmp, re.DOTALL)

            storeOperationHourInfo_result = {}
            for day, slots in store_matches:
                storeOperationHourInfo_result[day] = [slots]

            data['storeOperationHourInfo'] = storeOperationHourInfo_result

            try:
                cuisine_element = page.ele('xpath://span[contains(@class, "iCdfhy") and contains(@class, "gZPeMs")]')
                if cuisine_element:
                    data['merchant_cuisine'] = cuisine_element.text
                else:
                    cuisine_element = page.ele('.iCdfhy.gZPeMs')
                    data['merchant_cuisine'] = cuisine_element.text if cuisine_element else "Not found"
            except Exception as e:
                logger.error(f"merchant_cuisine: {e}")
                data['merchant_cuisine'] = "Error: Unable to retrieve"

            cleaned_url = clean_url(url)
            
            dish_image_selectors = [
                {'type': 'xpath', 'value': '//img[contains(@class, "styles__StyledImg-sc-1322bgy-0")]'},
                {'type': 'css', 'value': 'img.styles__StyledImg-sc-1322bgy-0.dfviTz'},
                {'type': 'xpath', 'value': '//img[@alt]'},
            ]
            dish_images = find_elements_by_selectors(page, dish_image_selectors)

            logger.debug(f"Number of images found: {len(dish_images)}")
            if dish_images:
                img_url = dish_images[0].attr('src')
                logger.debug(f"Image URL: {img_url}")
                data['dish_image'] = img_url if img_url else ''

            for sec in data['hasMenu']['hasMenuSection'][0]:
                for menu_item in sec['hasMenuItem']:
                    menu_item_name = menu_item['name'].replace('&amp;', '&').replace('&apos;', "'").replace('&quot;', '"')
                    menu_item['image'] = data.get('dish_image', '')
                    price_str = menu_item.get('offers', {}).get('price')
                    if price_str:
                        menu_item['price'] = convert_price_to_integer(price_str) if price_str else None
                    logger.debug(f"Menu item: {menu_item_name}, Image URL assigned: {menu_item['image']}, Price: {menu_item.get('price')}")

            file_path = f'{data_path}/{cleaned_url}.json'
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            logger.info(f"Saved: {file_path}")

            # Add to master JSON list and save it immediately
            master_json.append({
                'name': restaurant_name,
                'url': url,
                'clean_url': cleaned_url
            })

            with open(master_file_path, 'w', encoding='utf-8') as master_file:
                json.dump(master_json, master_file, ensure_ascii=False, indent=4)
            logger.info(f"Updated master JSON with: {restaurant_name}")

            processed_urls.add(url)
    except json.JSONDecodeError:
        logger.error(f"JSON: {url}")
    except KeyError as e:
        logger.error(f": {url}, .: {e}")
    except DrissionPage.errors.ElementNotFoundError:
        logger.error(f"C *: {url}")
    except Exception as e:
        logger.error(f"{url} : {str(e)}")
    finally:
        with open('processed_urls.txt', 'a', encoding='utf-8') as f:
            f.write(url + '\n')

def scrape_data(page: ChromiumPage, url, data_path):
    try:
        page.get(url)
        time.sleep(3)
        tab = page.new_tab()
        city_urls = []
        nums = 5000  #
        for num in range(1, nums+1):
            logger.info(f'{num}')
            for _ in range(5):
                try:
                    url = page.ele('@aria-labelledby').attr('href')
                    break
                except DrissionPage.errors.ElementNotFoundError:
                    time.sleep(0.5)
            else:
                logger.info(f'')
                break
            city_urls.append(url)
            xpath = page.ele('@aria-labelledby').parent(2).xpath
            page.run_js(
                f'''document.evaluate('{xpath}', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue.remove()''')

        for url in city_urls:
            try:
                process_restaurant(tab, url, data_path)
            except PageDisconnectedError:
                logger.error(f"URL {url} ")
                page = reconnect_page(page)
                tab = page.new_tab()
            except Exception as e:
                logger.error(f"URL {url} : {str(e)}")

    except PageDisconnectedError:
        logger.error(f"ub{url}")
        page = reconnect_page(page)
    except Exception as e:
        logger.error(f";URL {url}: {str(e)}")

    return page  

if __name__ == '__main__':

    co = ChromiumOptions()
    options = co.set_local_port(10020)
    page = ChromiumPage(options)

    city_urls = [
        'https://www.doordash.com/food-delivery/surrey-bc-restaurants/',
        'https://www.doordash.com/food-delivery/white-rock-bc-restaurants/',
        'https://www.doordash.com/food-delivery/vancouver-bc-restaurants/',
        'https://www.doordash.com/food-delivery/langley-bc-restaurants/',
        'https://www.doordash.com/food-delivery/richmond-bc-restaurants/',
        'https://www.doordash.com/food-delivery/burnaby-bc-restaurants/',
        'https://www.doordash.com/food-delivery/coquitlam-bc-restaurants/'
    ]

    data_path = f'D:/All_Data/doordash_{formatted_date}_rawdata'

    for url in city_urls:
        cite_name = url.split('/')[-2].split('-')[0]
        rest_data_path = f'{data_path}/dd_{cite_name}'

        if not os.path.exists(rest_data_path):
            os.makedirs(rest_data_path)

        try:
            page = scrape_data(page, url, rest_data_path)
        except Exception as e:
            logger.error(f";URL {url}: {str(e)}")
            page = reconnect_page(page)
            continue

    page.close()

    # Save master JSON file
    with open(master_file_path, 'w', encoding='utf-8') as master_file:
        json.dump(master_json, master_file, ensure_ascii=False, indent=4)
    logger.info(f"Master JSON file saved: {master_file_path}")
