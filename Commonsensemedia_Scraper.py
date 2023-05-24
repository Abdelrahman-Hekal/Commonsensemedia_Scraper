from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait as wait
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService 
import pandas as pd
import time
import csv
import sys
import numpy as np

def initialize_bot():

    # Setting up chrome driver for the bot
    chrome_options  = webdriver.ChromeOptions()
    # suppressing output messages from the driver
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--window-size=1920,1080')
    # adding user agents
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36")
    chrome_options.add_argument("--incognito")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    # running the driver with no browser window
    chrome_options.add_argument('--headless')
    # disabling images rendering 
    prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_options.add_experimental_option("prefs", prefs)
    # installing the chrome driver
    driver_path = ChromeDriverManager().install()
    chrome_service = ChromeService(driver_path)
    # configuring the driver
    driver = webdriver.Chrome(options=chrome_options, service=chrome_service)
    driver.set_page_load_timeout(60)
    driver.maximize_window()

    return driver

def scrape_commonsensemedia(path):

    start = time.time()
    print('-'*75)
    print('Scraping commonsensemedia.com ...')
    print('-'*75)
    # initialize the web driver
    driver = initialize_bot()

    # initializing the dataframe
    data = pd.DataFrame()

    # if no books links provided then get the links
    if path == '':
        name = 'commonsensemedia_data.xlsx'
        # getting the books under each category
        links = []
        nbooks, npages = 0, 0
        while True:
            url = 'https://www.commonsensemedia.org/reviews/category/book/age/11+12+13+14+15+16+17+18/page/'
            url += str(npages)
            driver.get(url)
            try:
                # scraping books urls
                divs = wait(driver, 5).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.review-teaser.row.row--align-start")))
                for div in divs:
                    nbooks += 1
                    print(f'Scraping the url for book {nbooks}')
                    link = wait(div, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.link.link--title"))).get_attribute('href')
                    links.append(link)

                # moving to the next page
                try:
                    # check if the last page reached
                    button = wait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//a[@aria-label='Goto next page']")))
                    npages += 1
                except:
                    break
            except Exception as err:
                print('The below error occurred during the scraping from commonsensemedia.com, retrying ..')
                print('-'*50)
                print(err)
                print('-'*50)
                driver.quit()
                time.sleep(10)
                driver = initialize_bot()

        # saving the links to a csv file
        print('-'*75)
        print('Exporting links to a csv file ....')
        with open('commonsensemedia_links.csv', 'w', newline='\n', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Link'])
            for row in links:
                writer.writerow([row])

    scraped = []
    if path != '':
        df_links = pd.read_csv(path)
    else:
        df_links = pd.read_csv('target_links.csv')

    links = df_links['Link'].values.tolist()
    name = path.split('\\')[-1][:-4]
    name = name + '_data.xlsx'
    try:
        data = pd.read_excel(name)
        scraped = data['Title Link'].values.tolist()
    except:
        pass

    # scraping books details
    print('-'*75)
    print('Scraping Books Info...')
    print('-'*75)
    n = len(links)
    for i, link in enumerate(links):
        try:
            if link in scraped: continue
            # restarting the bot if the site blocked it
            driver.quit()
            driver = initialize_bot()
            driver.get(link)           
            details = {}
            print(f'Scraping the info for book {i+1}\{n}')

            # title and title link
            title_link, title = '', ''
            try:
                title_link = link
                title = wait(driver, 2).until(EC.presence_of_element_located((By.TAG_NAME, "h1"))).get_attribute('textContent').title() 
            except:
                print(f'Warning: failed to scrape the title for book: {link}')            
                
            details['Title'] = title
            details['Title Link'] = title_link

            info = wait(driver, 2).until(EC.presence_of_element_located((By.XPATH, "//div[@class='review-product-details review-view-box--text review-view-box--shadow review-view-box']")))
            # book info
            cols = ['Author', 'Genre', 'Book type', 'Publisher', 'Publication date', 'Number of pages', 'Last updated']
                
            for col in cols:
                try:
                    lis = wait(info, 2).until(EC.presence_of_all_elements_located((By.TAG_NAME, "li")))
                    for li in lis:
                        attr = li.get_attribute('textContent').split(':')[0].strip()
                        if col == attr or col+'s' == attr:
                            details[col] = li.get_attribute('textContent').split(':')[1].strip()
                            break
                except:
                    print(f'Warning: failed to scrape the {col} for book: {link}')            
                    details[col] = ''
                   
            # press all the "Read or buy" buttons
            buttons = wait(driver, 2).until(EC.presence_of_all_elements_located((By.TAG_NAME, "button")))
            for button in buttons:
                if 'Read or buy' in button.text:
                    driver.execute_script("arguments[0].click();", button)
                    time.sleep(2)
                    break

            # Amazon link
            details['Amazon link'] = ''          
            try:
                sec = wait(driver, 2).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.review-buy-links")))
                urls = wait(sec, 2).until(EC.presence_of_all_elements_located((By.TAG_NAME, "a")))
                for url in urls:
                    if 'www.amazon.com' in url.get_attribute('href'):
                        details['Amazon link'] = url.get_attribute('href')  
            except:
                print(f'Warning: failed to scrape the Amazon link for book: {link}')            
                
            # reviewed by
            summarized, age = '', ''
            try:
                sec = wait(driver, 2).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.review-view-summary.row")))
                divs = wait(sec, 2).until(EC.presence_of_all_elements_located((By.TAG_NAME, "div")))
                for div in divs:
                    text = div.get_attribute('textContent')
                    if 'Book review by' in text:
                        summarized = text.replace('Book review by', '').replace(', Common Sense Media', '').strip()
                    elif 'age' in text and '+' in text:
                        age = text.replace('age', '').strip()
            except:
                print(f'Warning: failed to scrape the reviewed by info for book: {link}')                       
            details['Reviewed By'] = summarized 
            details['Age'] = age                          

            # rating
            rating = ''          
            try:
                div = wait(driver, 2).until(EC.presence_of_element_located((By.XPATH, "//div[@class='rating rating--inline rating--xlg rating--lg']")))
                stars = wait(div, 2).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "i.icon-star-rating.active")))
                rating = len(stars)
                if rating > 5 or rating == 0:
                    rating = ''
            except:
                print(f'Warning: failed to scrape the Amazon link for book: {link}')  
                    
            details['Rating'] = rating

            # appending the output to the datafame        
            data = data.append([details.copy()])
            # saving data to csv file each 100 links
            if np.mod(i+1, 100) == 0:
                print('Outputting scraped data ...')
                data.to_excel(name, index=False)
        except:
            pass

    # optional output to excel
    data.to_excel(name, index=False)
    elapsed = round((time.time() - start)/60, 2)
    print('-'*75)
    print(f'commonsensemedia.org scraping process completed successfully! Elapsed time {elapsed} mins')
    print('-'*75)
    driver.quit()

    return data

if __name__ == "__main__":
    
    path = ''
    if len(sys.argv) == 2:
        path = sys.argv[1]
    data = scrape_commonsensemedia(path)

