from selenium import webdriver
from selenium.webdriver.support.ui import  WebDriverWait
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import csv
from fpdf import FPDF
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
        
    def join(self, table1, table2, match_attribute1, match_attribute2, how, columns):
        result = pd.merge(table1, table2, left_on = match_attribute1, right_on = match_attribute2, how = how)[columns]
        return result
    
    def str_date_filter(self, table, date_attribute, this_date):
        result = table[table[date_attribute].str.startswith(this_date, na=False)]
        return result

    def anti_left_join_filter_by_date(self, table1, table2, match_attribute1, match_attribute2, date_attribute1, date_attribute2, this_date, columns):
        filtered_table1 = self.str_date_filter(table=table1,date_attribute=date_attribute1,this_date=this_date)
        filtered_table2 = self.str_date_filter(table=table2,date_attribute=date_attribute2,this_date=this_date)
        result = self.join(table1=filtered_table1,table2=filtered_table2,match_attribute1=match_attribute1,match_attribute2=match_attribute2,columns=columns, how='left_anti')
        return result

    def compare_tables(self, table1, table2, match_attribute1, match_attribute2, attributes1, attributes2, attribute_data_types):
        validity = []
        inconsistency_count = 0
        inner_join = self.join(table1=table1,table2=table2,match_attribute1=match_attribute1,match_attribute2=match_attribute2,how='inner',columns=attributes1+attributes2)
        matches = len(inner_join)
        for _, row in inner_join.iterrows(): #loop through all records
            consistency = []
            for column1, column2, data_type in zip(attributes1, attributes2, attribute_data_types):
                #find inconsistencies in row
                equal = self.compare_data(data1 = row[column1], data2 = row[column2], data_type = data_type)
                consistency.append(equal)
            consistent_check = (sum(consistency) == len(consistency))
            if not consistent_check:
                inconsistency_count += 1
            validity.append({consistent_check: consistency})
        return validity, matches, inconsistency_count
    
    def find_valid_file_name(self, directory, file_name, extension='.txt'):
        name, test_extension = os.path.splitext(file_name)
        if test_extension == '':
            file_name = file_name + extension
        os.makedirs(directory, exist_ok = True)
        file_path = os.path.join(directory, file_name)
        index = 0
        while True:
            if os.path.exists(file_path):
                index += 1
                file_path = os.path.join(directory, f'{name} ({index}){extension}')
            else:
                return file_path, index, name

    def create_csv_file(self, open_directory, csv_fname, table):
        file_path, index, fname = self.find_valid_file_name(directory=open_directory, file_name=csv_fname, extension='.csv')
        table.to_csv(file_path, index = False)
        if index != 0:
            return f'{fname} ({index}).csv'
        else:
            return f'{fname}.csv'
        
    def create_pdf_file(self, open_directory, pdf_fname, text, font='Times', text_size=12, line_spacing=5):
        file_path, index, fname = self.find_valid_file_name(directory=open_directory, file_name=pdf_fname, extension='.pdf')
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font(family=font,size=text_size)
        for line in text.strip().split('\n'):
            pdf.cell(0,0,line)
            pdf.ln(line_spacing)
        pdf.output(file_path)
        if index != 0:
            return f'{fname} ({index}).pdf'
        else:
            return f'{fname}.pdf'

    def send_email(self, attachment_names, attachment_directory, sender_email, sender_password, recipient_emails, subject, body):
        html_part = MIMEText(body)
        message = MIMEMultipart()
        message['Subject'] = subject
        message['From'] = sender_email
        message['To'] = ', '.join(recipient_emails)
        message.attach(html_part)

        for name in attachment_names:
            with open(os.path.join(attachment_directory, name), 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="{name}"',
            )
            message.attach(part)

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_emails, message.as_string())

#factory method
def create_web_object(website, date):
     match website:
          case 'viatelecom' | 'via':
               return Biller.viatelecom(date)

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