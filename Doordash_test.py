import csv, json, os, re, time
import pandas as pd
from tqdm import tqdm
from DrissionPage import ChromiumPage, ChromiumOptions
from urllib.parse import unquote
import traceback
# from parsel import Selector
from loguru import logger
import DrissionPage.errors
from DrissionPage.errors import PageDisconnectedError
from pprint import pprint
from datetime import datetime


current_date = datetime.now()


formatted_date = current_date.strftime('%m%d')


logger.add("D:/scraping_log.txt", rotation="500 MB")


# Title cleaning function
def title_format(title: str):
    title = "".join(title).lower()
    title = re.sub(r',', ' ', title)
    title = re.sub(r'[\n\t\r]', ' ', title)
    return title


def remove_non_english(text):
    if isinstance(text, dict):
        return {k: remove_non_english(v) for k, v in text.items()}
    elif isinstance(text, list):
        return [remove_non_english(item) for item in text]
    elif isinstance(text, str):
        return re.sub(r'[^\x00-\x7F]+', '', text)
    else:
        return text


def clean_filename(name):
    name = unquote(name)
    name = name.lower()
    name = name.replace(" ", "-")
    name = re.sub(r'[^a-z0-9\-&]+', '', name)
    return name


def reconnect_page(page):
    try:
        page.close()
    except:
        pass
    options = ChromiumOptions().set_local_port(10020)
    return ChromiumPage(options)


def process_restaurant(page: ChromiumPage, url, data_path):
    try:
        page.get(url)
        time.sleep(3)
        html = page.html

        json_data = page.s_ele('@type=application/ld+json').text
        data = json.loads(json_data)

        if data['@type'] == 'Restaurant':
            restaurant_name = data['name']

            data['url'] = url

            # data['address'] = re.findall('\"displayAddress\":(.+?)"', page.html)[0][1:]
            data['address'] = re.findall(r'\"displayAddress\\":\\"(.*?)\\"', html)[0]
            data['phone'] = re.findall(r'\"phoneno\\":\\"(.*?)\\"', html)[0]

            # data['phone'] = page.ele('@aria-label=Restaurant phone number link').ele('tag:span').text
            # print(data['phone'])

            doordashOperationHourInfo = (re.findall(r'\"operationSchedule\\":\[(.*)\]}}(.*),\\"banners', html)[0][0]
                                         .replace('\\', "")
                                         .replace('{"__typename":"OperationHours",', "")
                                         .replace("]}", "]"))

            door_pattern = r'"dayOfWeek":"(\w+)".*?"timeSlotList":\["(.*?)"\]'
            door_matches = re.findall(door_pattern, doordashOperationHourInfo, re.DOTALL)

            #
            doordashOperationHourInfo_result = {}
            for day, slots in door_matches:
                doordashOperationHourInfo_result[day] = [slots]

            data['doordashOperationHourInfo'] = doordashOperationHourInfo_result
            # data['doordashOperationHourInfo'] = json.loads(
            #     re.findall(r'"doordashOperationHourInfo":(.+),"dayOfWeek"', html)[0][:-1])

            storeOperationHourInfo_tmp = (
                (re.findall(r'\"operationSchedule\\":\[(.*)\]},\\"doordashOperationHourInfo', html)[0].
                 replace('\\', "").
                 replace('{"__typename":"OperationHours",', "")).
                replace("]}", "]"))

            storeOperationHourInfo = json.loads(json.dumps(storeOperationHourInfo_tmp))

            store_pattern = r'"dayOfWeek":"(\w+)".*?"timeSlotList":\["(.*?)"\]'
            store_matches = re.findall(store_pattern, storeOperationHourInfo, re.DOTALL)

            
            storeOperationHourInfo_result = {}
            for day, slots in store_matches:
                storeOperationHourInfo_result[day] = [slots]

            data['storeOperationHourInfo'] = storeOperationHourInfo_result

            # pprint(data)
            # 
            try:
                cuisine_element = page.ele('xpath://span[contains(@class, "iCdfhy") and contains(@class, "gZPeMs")]')
                if cuisine_element:
                    data['merchant_cuisine'] = cuisine_element.text
                else:
                    cuisine_element = page.ele('.iCdfhy.gZPeMs')
                    data['merchant_cuisine'] = cuisine_element.text if cuisine_element else "Not found"
            except Exception as e:
                logger.error(f"ՕՇmerchant_cuisine: {e}")
                data['merchant_cuisine'] = "Error: Unable to retrieve"

            cleaned_filename = clean_filename(restaurant_name)

            img_map = dict()
            # Find images using XPath and CSS selectors
            dish_images = page.eles('xpath:/html/body/div[1]/div[1]/div/main/div[3]/div[3]/div/div[6]/div[2]/div[7]/div[1]/div[2]/div/div/div/div/div/div/div/picture/source[1]')
            logger.debug(f"Number of images found: {len(dish_images)}")
            for img in dish_images:
                img_name = img.attr('alt')  # Assuming 'alt' attribute contains the name of the dish
                img_url = img.attr('srcset') or img.attr('src')
                logger.debug(f"Image Name: {img_name}, Image URL: {img_url}")
                if img_name and img_url:
                    img_map[img_name] = img_url

            for sec in data['hasMenu']['hasMenuSection'][0]:
                for menu_item in sec['hasMenuItem']:
                    menu_item_name = menu_item['name'].replace('&amp;', '&').replace('&apos;', "'").replace('&quot;', '"')
                    menu_item['image'] = img_map.get(menu_item_name, '')
                    logger.debug(f"Menu item: {menu_item_name}, Image URL assigned: {menu_item['image']}")

            # file_path = f'./data_doordash_{formatted_date}_coquitlam/{cleaned_filename}.json'
            file_path = f'{data_path}/{cleaned_filename}.json'
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            logger.info(f"Saved: {file_path}")
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
        # page.close_tabs(page.tab_ids[1:])
        # page.set.activate()
        page.get(url)
        time.sleep(3)
        tab = page.new_tab()
        urls = []
        # nums = int(input("pls input nums:>>>>").strip())
        nums = 5000  #
        for num in range(1, nums+1):
            logger.info(f'{num}')
            for _ in range(5):
                try:
                    url = page.ele('@aria-labelledby').attr('href')
                    break
                except DrissionPage.errors.ElementNotFoundError:
                    time.sleep(0.5)
                    # continue
            else:
                logger.info(f'')
                break
            urls.append(url)
            xpath = page.ele('@aria-labelledby').parent(2).xpath
            page.run_js(
                f'''document.evaluate('{xpath}', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue.remove()''')

        for url in urls:
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

    urls = [
        # 'https://www.doordash.com/food-delivery/surrey-bc-restaurants/',
        #'https://www.doordash.com/food-delivery/white-rock-bc-restaurants/',
        'https://www.doordash.com/food-delivery/vancouver-bc-restaurants/',
        #'https://www.doordash.com/food-delivery/langley-bc-restaurants/',
        # 'https://www.doordash.com/food-delivery/richmond-bc-restaurants/',
        # 'https://www.doordash.com/food-delivery/burnaby-bc-restaurants/',
        #'https://www.doordash.com/food-delivery/coquitlam-bc-restaurants/'
    ]

    data_path = f'D:/All_Data/doordash_{formatted_date}_rawdata'


    for url in urls:
        cite_name = url.split('/')[-2].split('-')[0]
        # print("cite_name:::",cite_name)
        rest_data_path = f'{data_path}/dd_{cite_name}'

        if not os.path.exists(rest_data_path):
            os.makedirs(rest_data_path)

        try:
            page = scrape_data(page, url ,rest_data_path)
        except Exception as e:
            logger.error(f";URL {url}: {str(e)}")
            page = reconnect_page(page)
            continue

    page.close()