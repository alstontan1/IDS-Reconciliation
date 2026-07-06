from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import  WebDriverWait
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.common.exceptions import ElementNotInteractableException
from selenium.common.exceptions import TimeoutException
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import csv
from datetime import date, datetime, timedelta
from dotenv import find_dotenv, load_dotenv
import os
import pymysql
import pandas as pd
import smtplib
import time

class viatelecom:
    def __init__(self, date):
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

    def rpa_quit(self, download_directory, temporary_extension='.crdownload', timeout=300):
        start = time.time()
        while time.time() - start < timeout:
            if os.path.isfile(os.path.join(download_directory, self.download_file_name + temporary_extension)):
                time.sleep(1)
            elif os.path.isfile(os.path.join(download_directory, self.download_file_name)):
                break
            else:
                time.sleep(1)
        driver.quit()

    def format_data(self, file_path):
        return pd.read_csv(file_path)
            

# class web2():
#     pass

class reconciliation():
    def __init__(self):
        pass

    def find_table(self, db_name, tb_name, cursor_name):
        cursor_name.execute(f"USE {db_name}")
        sql = f"""
        SELECT * 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_SCHEMA = '{db_name}' 
        AND TABLE_NAME = '{tb_name}';
        """
        cursor_name.execute(sql)
        if cursor_name.fetchone() == None:
            return False
        return True
    
    def format_table_data(self, db_name, tb_name, cursor_name):
        cursor_name.execute(f"USE {db_name}")
        sql = f"""
        SELECT *
        FROM {tb_name}
        """
        cursor.execute(sql)
        return pd.DataFrame([i for i in cursor.fetchall()])
    
    def compare_data(self, data1, data2, data_type):
        match data_type.split('(')[0].lower():
            #sql based data types
            case 'varchar' | 'str':
                return str(data1) == str(data2)
            case 'double' | 'float':
                return float(data1) == float(data2)
            case 'bigint' | 'int':
                return int(data1) == int(data2)
            #non-sql based data types
            case 'datetime_string <by date>': #datetime stored as string data type, check by time
                return str(data1)[:10] == str(data2)[:10]
            case 'datetime_string <by time>': #datetime stored as string data type, check by time
                return str(data1)[-8:] == str(data2)[-8:]
            
    def compare_tables(self, table1, table2, match_attribute1, match_attribute2, attributes1, attributes2, attribute_data_types):
        summary = {}
        inner_join = table1.merge(table2,left_on = match_attribute1, right_on = match_attribute2, how = "inner")[[attribute for pair in zip(attributes1, attributes2) for attribute in pair]]
        matches = len(inner_join)
        for _, row in inner_join.iterrows(): #loop through all records
            inconsistency = []
            for column1, column2, data_type in zip(attributes1, attributes2, attribute_data_types):
                #find inconsistencies in row
                equal = self.compare_data(data1 = row[column1], data2 = row[column2], data_type = data_type)
                inconsistency.append(not equal)
            if sum(inconsistency) != 0: #there is an inconsistency
                #create row summary
                summary[row[match_attribute1]] = []
                for column1, column2, incorrect in zip(attributes1, attributes2, inconsistency):
                    if incorrect:
                        data_summary = f'{column1} - {column2} : {row[column1]} - {row[column2]}'
                    else:
                        data_summary = f'{column1} - {column2} : Valid'
                    summary[row[match_attribute1]].append(data_summary)
        return summary, matches
    
    def find_non_matches(self, table1, table2, match_attribute1, match_attribute2):
        summary = []
        anti_join = table1[~table1[match_attribute1].isin(table2[match_attribute2])][[match_attribute1]]
        for _, match_attribute in anti_join.itertuples():
            summary.append(match_attribute)
        return summary

    def find_non_matches_on_date(self, table1, table2, match_attribute1, match_attribute2, date_attribute, this_date): #date_attribute is datetime stored as string
        summary = []
        filtered_anti_join = table1[~table1[match_attribute1].isin(table2[match_attribute2]) & (table1[date_attribute].str.startswith(this_date, na=False))][[match_attribute1]]
        for _, match_attribute in filtered_anti_join.itertuples():
            summary.append(match_attribute)
        return summary
    
    def create_summary_file(self, open_directory, summary_file_name, text):
        os.makedirs(open_directory, exist_ok = True)
        file_path = os.path.join(open_directory, summary_file_name)
        name, extension = os.path.splitext(summary_file_name)
        index = 0
        while True:
            if os.path.exists(file_path):
                index += 1
                file_path = os.path.join(open_directory, f'{name} ({index}){extension}')
            else:
                file_object = open(file_path, 'w', newline = '', encoding = 'utf-8')
                break
        file = csv.writer(file_object)
        for line in text.strip().split('\n'):
            file.writerow([line])
        file_object.close()
        if index != 0:
            return f'{name} ({index}){extension}'
        else:
            return f'{name}{extension}'

    def send_email(self, attachment_name, attachment_directory, sender_email, sender_password, recipient_emails, subject, body):
        with open(os.path.join(attachment_directory, attachment_name), 'rb') as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename="{attachment_name}"',
        )

        html_part = MIMEText(body)
        message = MIMEMultipart()
        message['Subject'] = subject
        message['From'] = sender_email
        message['To'] = ', '.join(recipient_emails)
        message.attach(html_part)
        message.attach(part)

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_emails, message.as_string())

#factory method
def create_web_object(website, date):
     match website:
          case 'viatelecom' | 'via':
               return viatelecom(date)
        #   case 'web2':
        #        return web2(date)

def boot(user, password, database, download_directory):
        connection = pymysql.connect( 
        host = 'localhost',
        user = user,
        password = password,
        database = database,
        charset = 'utf8mb4',
        cursorclass = pymysql.cursors.DictCursor
        )
        options = webdriver.ChromeOptions()
        prefs = {'download.default_directory': download_directory}
        options.add_experimental_option('prefs', prefs)
        drv = webdriver.Chrome(options = options)
        return connection.cursor(), drv, WebDriverWait(driver = drv, timeout = 5)



if __name__ == '__main__':
    #Initialize
    load_dotenv(find_dotenv())
    this_date = str(date.today() - timedelta(1)) #'2026-05-19'
    db = os.getenv('db_name')
    tb = os.getenv('tb_name')
    open_dir = r'C:\Users\USER\Downloads'
    reconciliation_file_name = f'Rekonsiliasi_Transaksi_{this_date.replace('-','_')}.csv'
    cursor, driver, wait = boot(user=os.getenv('db_user'), password=os.getenv('db_password'), database=db, download_directory=open_dir)
    web = create_web_object(website='viatelecom', date=this_date)
    recon = reconciliation()
    
    #RPA
    web.download_transactions(email=os.getenv('web_email'), password=os.getenv('web_password'), driver_name=driver, wait_name=wait)
    web.rpa_quit(download_directory=open_dir,temporary_extension='.crdownload',timeout=300)
    biller_table = web.format_data(file_path=os.path.join(open_dir, web.download_file_name))

    #Reconciliation
    ids_table = recon.format_table_data(db_name=db,tb_name=tb,cursor_name=cursor)
    inconsistent_match_summary, match_count = recon.compare_tables(table1=biller_table,table2=ids_table,match_attribute1=web.my_attributes[0],match_attribute2=web.compared_attributes[0],attributes1=web.my_attributes,attributes2=web.compared_attributes,attribute_data_types=web.my_attribute_data_types)
    non_match_summary = {
        'biller': [],
        'ids': []
    }
    non_match_summary['biller'] = recon.find_non_matches(table1=biller_table,table2=ids_table,match_attribute1=web.my_attributes[0],match_attribute2=web.compared_attributes[0])
    non_match_summary['ids'] = recon.find_non_matches_on_date(table1=ids_table,table2=biller_table,match_attribute1=web.compared_attributes[0],match_attribute2=web.my_attributes[0],date_attribute=web.compared_attributes[1],this_date=this_date)    

    #Reconciliation summary
    str_inconsistent_matches = ''
    for (identifier, inconsistency) in inconsistent_match_summary.items():
        str_inconsistent_matches = str_inconsistent_matches + identifier + ': ' + ' / '.join(inconsistency) + '\n'
    if str_inconsistent_matches == '':
        str_inconsistent_matches = 'Tidak ada'
    reconciliation_file_name = recon.create_summary_file(open_directory=open_dir,summary_file_name=reconciliation_file_name,
                              text=f"""
Rekonsiliasi Data Transaksi Tanggal {this_date}
Jumlah baris berpasangan: {match_count}
Jumlah baris dari tabel IDS yang tidak ada pasangan: {len(non_match_summary['ids'])}
Jumlah baris dari tabel biller yang tidak ada pasangan: {len(non_match_summary['biller'])}
Baris yang tidak konsisten:
{str_inconsistent_matches.strip()}
ID dari tabel IDS yang tidak ada pasangan:
{non_match_summary['ids']}
ID dari tabel biller yang tidak ada pasangan:
{non_match_summary['biller']}
""")
    recon.send_email(attachment_name=reconciliation_file_name,attachment_directory=open_dir,sender_email=os.getenv('sender_email'),sender_password=os.getenv('sender_app_password'),recipient_emails=[os.getenv('recipient_email')],subject=f'Rekonsiliasi Tanggal {this_date}',body='')
