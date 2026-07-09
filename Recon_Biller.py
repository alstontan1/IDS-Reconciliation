from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.common.exceptions import ElementNotInteractableException
from datetime import date, datetime, timedelta
import os
import pandas as pd
import time

class viatelecom:
    def __init__(self, date=str(date.today() - timedelta(1)) ):
        self.date = date
        self.download_file_name = f'transaction-list-{date.replace('-','_')} - {date.replace('-','_')}.csv'
        self.my_attributes = ['Reff ID', 'Date', 'Sales Price', 'Customer Number']
        self.compared_attributes = ['supplierref', 'transactiondate', 'nominal', 'customerid']
        self.my_attribute_data_types = ['varchar(50)', 'datetime_string <by date>', 'double', 'bigint']

    def download_transactions(self, email, password, driver_name, wait_name):
        driver_name.get('https://viatelecom.id/login')
        wait_name.until(EC.presence_of_element_located((By.XPATH,'//*[@id="email"]')))
        driver_name.find_element(By.XPATH,'//*[@id="email"]').send_keys(email + Keys.TAB + password) #credentials
        driver_name.find_element(By.XPATH,'/html/body/div/div[1]/div[2]/div/div[1]/form/div[3]/div/div/label').click()
        retry_scale_factor = 0
        while 1:
            try:
                captcha_px_offset = driver_name.find_element(By.XPATH,'//*[@id="captcha-target"]').get_attribute('style').split(':')[-1].replace('px;','').replace(' ','')
                if retry_scale_factor != 0:
                    captcha_slider = driver_name.find_element(By.XPATH,'//*[@id="captcha-range"]')
                    try:
                        ActionChains(driver_name).drag_and_drop_by_offset(captcha_slider, retry_scale_factor*int(captcha_px_offset)-365, 0).perform() #tested position
                    except ElementNotInteractableException:
                        pass
                else:
                    try:
                        captcha_px_offset = int(captcha_px_offset)
                        captcha_slider = driver_name.find_element(By.XPATH,'//*[@id="captcha-range"]')
                        scale_factor = 365*2/int(captcha_slider.get_attribute('max'))
                        ActionChains(driver_name).drag_and_drop_by_offset(captcha_slider, scale_factor*int(captcha_px_offset)-365, 0).perform() #tested position
                        if not EC.element_to_be_clickable((By.XPATH,'//*[@id="captcha-range"]')):
                            retry_scale_factor = 0
                    except (ValueError, ElementNotInteractableException): #error: offset = 'none'
                        retry_scale_factor = 0
                driver_name.find_element(By.XPATH, '/html/body/div/div/div[2]/div/div[1]/form/div[4]/div/button').click()
                break
            except ElementClickInterceptedException:
                pass
        wait_name.until(EC.presence_of_element_located((By.XPATH,'//*[@id="sidebar"]/ul/li[3]/a')))
        driver_name.find_element(By.XPATH,'//*[@id="sidebar"]/ul/li[3]/a').click() #click transactions
        wait_name.until(EC.presence_of_element_located((By.XPATH,'//*[@id="date-range"]')))
        #filter
        driver_name.find_element(By.XPATH,'//*[@id="date-range"]').click() #click date range
        ActionChains(driver_name).scroll_by_amount(0, 250).perform()
        driver_name.find_element(By.XPATH,'/html/body/div[3]/div[1]/ul/li[7]').click() #click custom range
        date_obj = datetime.strptime(self.date, r"%Y-%m-%d").date()
        for i in range(12*(date.today().year-date_obj.year)+date.today().month-date_obj.month):
            driver_name.find_element(By.XPATH,'/html/body/div[3]/div[2]/div[1]/table/thead/tr[1]/th[1]').click() #click last month
        #calculate date position
        min_weeks_difference = (date_obj.day-1)//7
        days_difference = date_obj.day-(1+7*(min_weeks_difference))
        day_1 = (date(date_obj.year, date_obj.month, 1).weekday()+1)%(7)
        week_num = ((day_1+days_difference)//7)+min_weeks_difference+1
        for i in range(2):
            driver_name.find_element(By.XPATH,f'/html/body/div[3]/div[2]/div[1]/table/tbody/tr[{week_num}]/td[{(date_obj.weekday()+1)%(7)+1}]').click() #click date
        driver_name.find_element(By.XPATH,'/html/body/div[3]/div[4]/button[2]').click()
        driver_name.find_element(By.XPATH,'//*[@id="btn-filter"]').click() #click search
        driver_name.find_element(By.XPATH,'//*[@id="btn-export"]').click() #click import

    def rpa_quit(self, driver_name, download_directory, temporary_extension='.crdownload', timeout=300):
        start = time.time()
        while time.time() - start < timeout:
            if os.path.isfile(os.path.join(download_directory, self.download_file_name + temporary_extension)):
                time.sleep(1)
            elif os.path.isfile(os.path.join(download_directory, self.download_file_name)):
                break
            else:
                time.sleep(1)
        driver_name.quit()

    def format_data(self, file_path):
        return pd.read_csv(file_path)