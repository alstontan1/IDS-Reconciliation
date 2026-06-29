#cd 'C:\Users\USER\OneDrive\Desktop\Work\Python project'
#.\.venv\Scripts\activate
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
import smtplib
import sys
import time



def err_fix_msg(err, fix):
    print('----Error----')
    print('    ' + err.replace('\n','\n    ').strip())
    print('---- Fix ----')
    print('    ' + fix.replace('\n','\n    ').strip())

def check_tb_exist(db_name,tb_name,cursor_name):
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

def data_recon(data1, data2, tp):
    match tp[:3]:
        case 'str':
            if str(data1) == str(data2):
                return True
        case 'int':
            if int(data1) == int(data2):
                return True
        case 'flt':
            precision = int(tp[4:len(tp)])
            if f'{float(data1):.{precision}f}' == f'{float(data2):.{precision}f}':
                return True
        case 'dte':
            if str(data1)[:10] == str(data2)[:10]: #by same date
                return True
    return False

def import_csv(db_name,tb_name,cursor_name,data_fpath,conn):
    cursor_name.execute(f"USE {db_name}")
    cursor_name.execute(f"DELETE FROM `{tb_name}`")  #replace old data

    sql = f"""
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = '{db_name}'
    AND table_name = '{tb_name}';
    """
    cursor_name.execute(sql)
    columns = cursor_name.fetchone()['COUNT(*)']
    cursor_name.execute(f"USE {db_name}")
    sql = f"""
    INSERT INTO `{tb_name}`
    VALUES({','.join(['%s'] * columns)});
    """
    try:
        file = open(data_fpath) 
    except FileNotFoundError:
        return 0

    file_contents = csv.reader(file)
    next(file_contents)
    for row in file_contents:
        row = [None if data == '' else data for data in row]
        try:
            cursor_name.execute(sql, row)
        except TypeError:
            return 1
    conn.commit()
    file.close()

def ensure_tb_exist(db_name,tb_name,cursor_name):
    try: #create table to import into
        cursor_name.execute(f"USE {db_name}")
        sql = f"""
        CREATE TABLE {tb_name}(
        `TRX ID` VARCHAR(50),
        `Customer Number` BIGINT,
        Date VARCHAR(50),
        `Final Status Date` VARCHAR(50),
        Category VARCHAR(50),
        Operator VARCHAR(50),
        `Product ID` INT,
        `Product Code` VARCHAR(50),
        `Product Name` VARCHAR(50),
        Qty VARCHAR(50),
        `Sales Price` DOUBLE,
        Status VARCHAR(50),
        SN VARCHAR(50),
        `Reff ID` VARCHAR(50),
        Remarks VARCHAR(100),
        Merchant VARCHAR(50)
        );
        """
        cursor_name.execute(sql)
    except pymysql.err.OperationalError: #table already exists
        pass

def check_pairs(db_name,tb_1,att_1,tb_2,att_2,cursor_name):
    try: #match pairs
        cursor_name.execute(f"USE {db_name}")
        sql = f"""
        SELECT {', '.join(f'a.`{x}`, b.`{y}`'for x, y in zip(att_1, att_2))}
        FROM `{tb_1}` a JOIN `{tb_2}` b 
        ON a.`{att_1[0]}` = b.`{att_2[0]}`;
        """ #supplierref = Reff ID : group by first attribute
        cursor_name.execute(sql)
        return cursor_name.fetchall()
    except pymysql.err.OperationalError:
        return False

def check_attributes(db_name,tb_name,att_list,cursor_name):
    cursor_name.execute(f"USE {db_name}")
    sql = f"""
    SELECT *
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
    AND table_name = '{tb_name}';
    """
    cursor_name.execute(sql)
    existing_attributes = set()
    for j in cursor_name.fetchall():
        existing_attributes.add(j['COLUMN_NAME'])
    check_attributes = set(att_list)
    return sorted(check_attributes-existing_attributes)

def solve_captcha(driver_name,wait_name,retry_scale_factor):
    captcha_px_offset = driver_name.find_element(By.XPATH,'//*[@id="captcha-target"]').get_attribute('style').split(':')[-1].replace('px;','').replace(' ','')
    if retry_scale_factor:
        captcha_slider = driver_name.find_element(By.XPATH,'//*[@id="captcha-range"]')
        ActionChains(driver_name).drag_and_drop_by_offset(captcha_slider, retry_scale_factor*int(captcha_px_offset)-365, 0).perform() #tested position
        return retry_scale_factor
    try:
        captcha_px_offset = int(captcha_px_offset)
        captcha_slider = driver_name.find_element(By.XPATH,'//*[@id="captcha-range"]')
        scale_factor = 365*2/int(captcha_slider.get_attribute('max'))
        wait_name.until(EC.element_to_be_clickable((By.XPATH,'//*[@id="captcha-range"]')))
        ActionChains(driver_name).drag_and_drop_by_offset(captcha_slider, scale_factor*int(captcha_px_offset)-365, 0).perform() #tested position
        if not EC.element_to_be_clickable((By.XPATH,'//*[@id="captcha-range"]')):
            return 0
        else:
            return scale_factor
    except (ValueError, ElementNotInteractableException): #error: offset = 'none'
        return 0

def login(email,password,driver_name,wait_name):
    wait_name.until(EC.presence_of_element_located((By.XPATH,'//*[@id="email"]')))
    driver_name.find_element(By.XPATH,'//*[@id="email"]').send_keys(email + Keys.TAB + password) #credentials
    driver_name.find_element(By.XPATH,'/html/body/div/div[1]/div[2]/div/div[1]/form/div[3]/div/div/label').click()
    retry_scale_factor = 0
    while 1:
        try:
            retry_scale_factor = solve_captcha(driver_name,wait_name,retry_scale_factor)
            wait_name.until(EC.element_to_be_clickable((By.XPATH,'/html/body/div/div/div[2]/div/div[1]/form/div[4]/div/button')))
            driver_name.find_element(By.XPATH, '/html/body/div/div/div[2]/div/div[1]/form/div[4]/div/button').click()
            break
        except ElementClickInterceptedException:
            pass
        
def transaction_dl(date_obj,driver_name,wait_name):
    wait_name.until(EC.presence_of_element_located((By.XPATH,'//*[@id="sidebar"]/ul/li[3]/a')))
    driver_name.find_element(By.XPATH,'//*[@id="sidebar"]/ul/li[3]/a').click() #click transactions
    wait_name.until(EC.presence_of_element_located((By.XPATH,'//*[@id="date-range"]')))
    #filter
    driver_name.find_element(By.XPATH,'//*[@id="date-range"]').click() #click date range
    ActionChains(driver_name).scroll_by_amount(0, 250).perform()
    driver_name.find_element(By.XPATH,'/html/body/div[3]/div[1]/ul/li[7]').click() #click custom range
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

def file_dl_wait(fpath,temp='.crdownload',refresh=1,timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        if os.path.isfile(fpath + temp):
            time.sleep(refresh)
        elif os.path.isfile(fpath):
            return True
        else:
            time.sleep(refresh)
    return False

def send_email(attachment_name, attachment_fpath, sender_email, sender_password, recipient_email, subject, body):
    with open(attachment_fpath, 'rb') as attachment:
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
    message['To'] = recipient_email
    message.attach(html_part)
    message.attach(part)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, message.as_string())





if __name__ == '__main__':

    dotenv_path = find_dotenv()
    if not load_dotenv(dotenv_path):
        err_fix_msg(err = f"""
.env not found.
""", fix = f"""
Import the correct .env file into the directory.
""")
        sys.exit()

    driver = webdriver.Chrome()
    driver.get('https://viatelecom.id/login')
    wait = WebDriverWait(driver, timeout=5)

    #initialization
    date_h1 = str(date.today() - timedelta(1))
    #date_h1 = string, format: 'yyyy-mm-dd'
    CMP_dir = f'C:\\Users\\USER\\Downloads'
    CMP_fpath = f'{CMP_dir}\\transaction-list-{date_h1.replace('-','_')} - {date_h1.replace('-','_')}.csv'
    recon_file_name = f'Rekonsiliasi_Transaksi_{date_h1.replace('-','_')}.csv'

    try:
        connection = pymysql.connect( 
        host = 'localhost',
        user = os.getenv('db_user'),
        password = os.getenv('db_password'),
        database = 'ppobprod',
        charset = 'utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
        )
        cursor = connection.cursor()
    except pymysql.err.OperationalError:
        err_fix_msg(err = f"""
Connection not found.
""", fix = f"""
Activate the database server.
""")
        sys.exit()
    cursor.execute(f"USE ppobprod")    



    #RPA
    login('impiandib@gmail.com', os.getenv('via_password'), driver, wait)
    transaction_dl(datetime.strptime(date_h1, r"%Y-%m-%d").date(),driver,wait)
    if not file_dl_wait(CMP_fpath):
        err_fix_msg(err = f"""
    File download exceeded timeout.
    """, fix = f"""
    The file may not have downloaded; re-run the program.
    Otherwise, if the download had occured but was incomplete, increase the timeout.
    If the issue persists, ensure there are no other files with the same file name.
    Ensure sufficient file storage space.
    """)
        
    driver.close()



    #cek adanya tabel 'tb_r_logpaydata'
    if not check_tb_exist('ppobprod', 'tb_r_logpaydata', cursor):
        err_fix_msg(err = f"""
Table 'tb_r_logpaydata' not found.
""", fix = f"""
Input an existing table name from database 'ppobprod'
for 'IDS_tb'
""")
        sys.exit()

    ensure_tb_exist('ppobprod','transaction_list',cursor)
    match import_csv('ppobprod','transaction_list',cursor,CMP_fpath,connection):
        case 0:
            err_fix_msg(err = f"""
        File from path {CMP_fpath}
        does not exist.
        """, fix = f"""
        Change the file path in 'CMP_fpath'
        to the file path of 'transaction-list-{date_h1.replace('-','_')} - {date_h1.replace('-','_')}.csv'
        after the automated download.
        Ensure there are no other files with the same file name.
        Ensure sufficient file storage space.
        """)
            sys.exit()
        case 1:
            err_fix_msg(err = f"""
Number of attributes from '{CMP_fpath}'
and number of attributes from 'transaction_list'
are different.
""", fix = f"""
Recreate table 'transaction_list'
with more / less attributes.
""")
            sys.exit()

    data_to_check = check_pairs('ppobprod','tb_r_logpaydata',['supplierref', 'transactiondate', 'nominal', 'customerid'],'transaction_list',['Reff ID', 'Date', 'Sales Price', 'Customer Number'],cursor)

    if data_to_check == False: #error checking
        false_attributes = {
            'tb_r_logpaydata' : [],
            'transaction_list' : []
        }
        for i,j in [('tb_r_logpaydata',['supplierref', 'transactiondate', 'nominal', 'customerid']), ('transaction_list',['Reff ID', 'Date', 'Sales Price', 'Customer Number'])]:
            false_attributes[i].extend(check_attributes('ppobprod',i,j,cursor))
        err_fix_msg(err = f"""
The attributes {false_attributes['tb_r_logpaydata']}
and the attributes {false_attributes['transaction_list']}
do not exist.
""", fix = f"""
Replace the attributes with attributes that exist in 'ppobprod' for each table.
""")
        sys.exit()



    #hitung pasangan dan non-pasangan
    counts = {
        'matches' : 0,
        'CMP_tb_rows' : 0,
        'IDS_tb_rows_h-1' : 0
    }
    unused_id = {
        'CMP_tb' : [],
        'IDS_tb' : []
    }    
    sql = f"""
    SELECT COUNT(*)
    FROM tb_r_logpaydata a JOIN transaction_list b 
    ON a.supplierref = b.`Reff ID`
    WHERE a.transactiondate LIKE '{date_h1}%';    
    """
    cursor.execute(sql)
    counts['matches'] = cursor.fetchall()[0]['COUNT(*)']

    sql = f"""
    SELECT COUNT(*)
    FROM `transaction_list`;
    """
    cursor.execute(sql)
    counts['CMP_tb_rows'] = cursor.fetchall()[0]['COUNT(*)']

    sql = f"""
    SELECT COUNT(*)
    FROM tb_r_logpaydata
    WHERE transactiondate LIKE '{date_h1}%';
    """
    cursor.execute(sql)
    counts['IDS_tb_rows_h-1'] = cursor.fetchall()[0]['COUNT(*)']

    sql = f"""
    SELECT a.`Reff ID`
    FROM transaction_list a LEFT JOIN tb_r_logpaydata b
    ON a.`Reff ID` = b.supplierref
    WHERE b.supplierref IS NULL;
    """
    cursor.execute(sql)
    for i in cursor.fetchall():
        unused_id['CMP_tb'].append(i['Reff ID'])

    sql = f"""
    SELECT a.supplierref
    FROM tb_r_logpaydata a LEFT JOIN transaction_list b
    ON a.supplierref = b.`Reff ID`
    WHERE b.`Reff ID` IS NULL
    AND a.transactiondate LIKE '{date_h1}%';    
    """
    cursor.execute(sql)
    for i in cursor.fetchall():
        unused_id['IDS_tb'].append(i['supplierref'])
            


    #reconciliation
    inconsistent_rows = {}
    
    attributes_IDS = ['supplierref', 'transactiondate', 'nominal', 'customerid']
    attributes_CMP = ['Reff ID', 'Date', 'Sales Price', 'Customer Number']
    attributes_type = ['str', 'dte', 'int', 'str']
    #pilihan tipe: 'str', 'int', 'flt [dp]', 'dte'
    #str = varchar (i.e. 'ABC123'), dte = date/datetime (i.e. 01-01-01)
    #int = int/bigint (i.e. 12345), flt [3] = dec(x, 3) (i.e. 3.14159 -> 3.142)

    attribute_number = int((len(attributes_CMP)+len(attributes_IDS))/2)
    for row in data_to_check:
        inconsistency_index = []
        for index in range(attribute_number):
            inconsistency_index.append(not data_recon(row[attributes_IDS[index]], row[attributes_CMP[index]], attributes_type[index]))
        if not inconsistency_index == [0 for i in range(attribute_number)]:
            inconsistent_rows[row['Reff ID']] = [f'{attributes_IDS[i]} - {attributes_CMP[i]} : {row[attributes_IDS[i]]} - {row[attributes_CMP[i]]}' if inconsistency_index[i] == 1 else f'{attributes_IDS[i]} - {attributes_CMP[i]} : Valid' for i in range(1,attribute_number)]



    #send and create file
    try:
        os.makedirs(CMP_dir, exist_ok = True)
        filename = os.path.join(CMP_dir, recon_file_name)
        filepath = open(filename, 'w', newline = '', encoding = 'utf-8')
    except PermissionError:
        err_fix_msg(err = f"""
    File name '{recon_file_name}' already exists.
    """, fix = f"""
    Delete or move the existing file as to not overwrite data.
    """
        )
        sys.exit()
    file = csv.writer(filepath)
    file.writerow([f'Rekonsiliasi Data Transaksi Tanggal ({date_h1})'])
    file.writerow([f'Jumlah baris pasangan: {counts['matches']}'])
    file.writerow([f'Jumlah baris dari tabel \'tb_r_logpaydata\' yang tidak ada pasangan (H-1): {len(unused_id['IDS_tb'])}'])
    file.writerow([f'Jumlah baris dari tabel \'transaction_list\' yang tidak ada pasangan: {len(unused_id['CMP_tb'])}'])
    file.writerow(['ID baris yang tidak konsisten:'])
    if len(inconsistent_rows) == 0:
        file.writerow([])
    for (id, inconsistency) in inconsistent_rows.items():
        file.writerow([id])
        file.writerow(inconsistency)
        file.writerow([])
    file.writerow([f'ID dari tabel \'tb_r_logpaydata\' yang tidak ada pasangan (H-1):'])
    file.writerow(unused_id['IDS_tb'])
    file.writerow([f'ID dari tabel \'transaction_list\' yang tidak ada pasangan:']) 
    file.writerow(unused_id['CMP_tb'])
    filepath.close()

    send_email(recon_file_name,f'{CMP_dir}\\{recon_file_name}',os.getenv('sender_email'),os.getenv('sender_app_password'),os.getenv('recipient_email'),f'Rekonsiliasi tanggal {date_h1}','')
