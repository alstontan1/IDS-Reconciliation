from selenium import webdriver
from selenium.webdriver.support.ui import  WebDriverWait
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import csv
import os
import pymysql
import pandas as pd
import smtplib
import Recon_Biller as Biller

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
        cursor_name.execute(sql)
        return pd.DataFrame([i for i in cursor_name.fetchall()])
    
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
               return Biller.viatelecom(date)
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