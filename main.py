import re
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from fake_useragent import UserAgent
from scrapy.selector import Selector
import traceback
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter


options = Options()
options.add_argument(f"user-agent={UserAgent().chrome}")
options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_argument("--headless")
options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})


# Функция собирает информацию о товарах со страниц сайта. Если какой-либо товар является
#  смартфоном, то происходит сбор информации об этом смартфоне в отдельном окне селениума. Парсинг товаров прекращается
#  после сбора информации со страницы, содержащей 100-ый смартфон. Страницы сайта, список товаров, список смартонов и
#  детальный список смартфонов сохранятсе в папке проекта.
def parse_pages():
    browser = webdriver.Chrome("chromedriver.exe", options=options)
    driver = webdriver.Chrome("chromedriver.exe", options=options)
    pn = 1
    counter = 0
    url = 'https://www.ozon.ru/category/telefony-i-smart-chasy-15501/?sorting=rating'
    gadgets_list = []
    smartphones_list = []
    smartphones_extended_list = []
    while len(smartphones_extended_list) <= 100:
        try:
            if pn == 1:
                browser.get(url)
            else:
                browser.get(url + f'&page={pn}')
            while True:
                browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                if len(browser.find_elements_by_xpath('//*[@class="k6s"]')) >= 30:
                    break
                browser.execute_script("window.scrollTo(0, -document.body.scrollHeight);")
            with open(f'pages/page_{pn}.html', 'w', encoding='utf-8') as pg_file:
                pg_file.write(browser.page_source)
            pg = browser.page_source
            widgets = Selector(text=pg).xpath('//*[@class="k6s"]')
            for gadget in widgets:
                gadget_info = {'url': f"https://www.ozon.ru{gadget.css('a').attrib['href']}",
                               'title': gadget.css("a>span>span::text").get()}
                lines = re.split('<br>', str(gadget.xpath("span[1]/span")[0].extract()))
                gadget_info['description'] = {
                    re.split(': ', re.sub(r'<[^>]*?>', '', line))[0]: re.split(': ', re.sub(r'<[^>]*?>', '', line))[1]
                    for line in lines}
                if gadget_info['description'].get('Тип', None) == 'Смартфон':
                    smartphones_list.append(gadget_info)
                    counter += 1
                    try:
                        driver.get(gadget_info['url'])
                        while True:
                            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            time.sleep(1)
                            if len(driver.find_elements_by_xpath(
                                    '//*[@id="section-characteristics"]/div[2]/div/div[2]/dl')) > 10:
                                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                                break
                            if re.findall('deny_category_prediction=true', driver.current_url):
                                break
                            driver.execute_script("window.scrollTo(0, -document.body.scrollHeight);")
                        gd = driver.page_source
                        with open(f'pages/gadgets/gadget_{counter}.html', 'w', encoding='utf-8') as gd_file:
                            gd_file.write(driver.page_source)
                        characteristics = Selector(text=gd).xpath('//*[@id="section-characteristics"]/div[2]/div')
                        feature_info = {}
                        for feature in characteristics:
                            section_name = feature.css('div:nth-child(1)::text').get()
                            feature_info[section_name] = {}
                            for dl in feature.xpath('.//dl'):
                                parameter = dl.xpath('.//dt/span/text()').get()
                                value = dl.xpath('.//dd//text()').get()
                                feature_info[section_name][parameter] = re.split(', ', value) \
                                    if re.findall(',', value) else value
                        gadget_info['characteristics'] = feature_info
                        smartphones_extended_list.append(gadget_info)
                        driver.delete_all_cookies()
                    except Exception as error:
                        print(traceback.format_exc())
                        with open(f'smartphones_extended_list.json', 'w') as ex_file:
                            json.dump(smartphones_extended_list, ex_file)
                        with open(f'smartphones.json', 'w') as file:
                            json.dump(smartphones_list, file)
                gadgets_list.append(gadget_info)
            pn += 1
            browser.delete_all_cookies()

        except Exception as error:
            print(traceback.format_exc())
            with open(f'gadgets.json', 'w') as file:
                json.dump(gadgets_list, file)
    browser.close()
    browser.quit()
    driver.close()
    driver.quit()
    with open(f'smartphones_extended_list.json', 'w') as file:
        json.dump(smartphones_extended_list, file)
    with open(f'gadgets.json', 'w') as file:
        json.dump(gadgets_list, file)
    with open(f'smartphones.json', 'w') as file:
        json.dump(smartphones_list, file)


# Функция подсчитывает повторяемость операционных систем для сотни смартфонов из (детального)списка смартфонов, на
# основании чего строик график распределения
def get_plot():
    with open(f'smartphones_extended_list.json', 'r') as file:
        smartphones_list = json.load(file)
    os_list = []
    for smartphone in smartphones_list[:100]:
        if smartphone['description']['Тип'] == 'Смартфон':
            if smartphone['characteristics'].get('Общие') and \
                    smartphone['characteristics']['Общие'].get('Версия Android'):
                os_list.append(smartphone['characteristics']['Общие']['Версия Android'])
            elif smartphone['characteristics'].get('Основные') is not None:
                os_list.append(smartphone['characteristics']['Основные']['Версия iOS'])
    pt = dict(sorted(Counter(os_list).items(), key=lambda x: x[1], reverse=True))
    df = pd.Series(pt.values(), index=pt.keys())
    df.plot(kind='barh', color=['#7ed6df', '#e056fd', '#686de0', '#30336b', '#95afc0', '#c7ecee'])
    plt.title("График распределения моделей по версиям операционных систем")
    plt.ylabel('Операционная система', fontsize=14, fontweight="bold")
    plt.xlabel('Количество смартфонов', fontsize=14, fontweight="bold")
    plt.savefig('figure.png', dpi=1000, bbox_inches='tight')
    plt.show()
    with open(r'results.txt', 'w', encoding='utf-8') as file:
        for k, v in pt.items():
            file.write(f'{k} - {v}\n')


parse_pages()
get_plot()
