from datetime import date, timedelta
from dotenv import find_dotenv, load_dotenv
import os
import pandas as pd
import Recon_Functions as ReconFunctions
import time

if __name__ == '__main__':
    start_time = time.perf_counter()

    #Initialize
    load_dotenv(find_dotenv())
    this_date = '2026-05-19'#str(date.today() - timedelta(1)) 
    db = os.getenv('db_name')
    tb = os.getenv('tb_name')
    open_dir = r'C:\Users\USER\Downloads'
    reconciliation_file_name = f'Rekonsiliasi_Transaksi_{this_date.replace('-','_')}'
    cursor, driver, wait = ReconFunctions.boot(user=os.getenv('db_user'), password=os.getenv('db_password'), database=db, download_directory=open_dir)
    web = ReconFunctions.create_web_object(website='viatelecom', date=this_date)
    recon = ReconFunctions.reconciliation()
    
    #RPA
    web.download_transactions(email=os.getenv('web_email'), password=os.getenv('web_password'), driver_name=driver, wait_name=wait)
    web.rpa_quit(driver_name=driver,download_directory=open_dir,temporary_extension='.crdownload',timeout=300)
    biller_table = web.format_data(file_path=os.path.join(open_dir, web.download_file_name))
    biller_table.to_csv('Biller.csv',index=False)
    ids_table = recon.format_table_data(db_name=db,tb_name=tb,cursor_name=cursor)

    #Reconciliation
    non_match_summary = {
        'biller_count': 0,
        'ids_count': 0
    }
    status = []
    column_order = [attribute for pair in zip(web.my_attributes, web.compared_attributes) for attribute in pair]
    inner_join = recon.join(table1=biller_table,table2=ids_table,match_attribute1=web.my_attributes[0],match_attribute2=web.compared_attributes[0],how='inner',columns=column_order)
    validities, match_count, inconsistency_count= recon.compare_tables(table1=biller_table,table2=ids_table,match_attribute1=web.my_attributes[0],match_attribute2=web.compared_attributes[0],attributes1=web.my_attributes,attributes2=web.compared_attributes,attribute_data_types=web.my_attribute_data_types)
    for row_validity in validities:
        if next(iter(row_validity.keys())) == True:
            status.append('Valid')
        else:
            status.append('Invalid')
    left_anti_join_biller = recon.join(table1=biller_table,table2=ids_table,match_attribute1=web.my_attributes[0],match_attribute2=web.compared_attributes[0],how='left_anti',columns=column_order)
    non_match_summary['biller_count'] = len(left_anti_join_biller)
    left_anti_join_ids = recon.anti_left_join_filter_by_date(table1=ids_table,table2=biller_table,match_attribute1=web.compared_attributes[0],match_attribute2=web.my_attributes[0],date_attribute1=web.compared_attributes[1],date_attribute2=web.my_attributes[1],this_date=this_date,columns=column_order)
    non_match_summary['ids_count'] = len(left_anti_join_ids)
    status += ['No matches']*(sum(non_match_summary.values()))
    status = pd.DataFrame({'Status': status})
    summary_table = pd.concat([inner_join,left_anti_join_biller,left_anti_join_ids], ignore_index=True)
    summary_table = pd.concat([summary_table,status], axis=1)

    #Reconciliation summary
    csv_file_name = recon.create_csv_file(open_directory=open_dir,csv_fname=reconciliation_file_name,table=summary_table)
    pdf_file_name = recon.create_pdf_file(open_directory=open_dir,pdf_fname=reconciliation_file_name,
                                          text=f"""
Rekonsiliasi Data Transaksi Tanggal [{this_date}]
Jumlah baris berpasangan: {match_count}
Jumlah baris berpasangan invalid: {inconsistency_count}
Jumlah baris dari tabel IDS yang tidak ada pasangan: {non_match_summary['ids_count']}
Jumlah baris dari tabel biller yang tidak ada pasangan: {non_match_summary['biller_count']}
""",
font='Times',text_size=12,line_spacing=10)
    recon.send_email(attachment_names=[csv_file_name, pdf_file_name],attachment_directory=open_dir,sender_email=os.getenv('sender_email'),sender_password=os.getenv('sender_app_password'),recipient_emails=[os.getenv('recipient_email')],subject=f'Rekonsiliasi Tanggal {this_date}',body='')

    end_time = time.perf_counter()
    execution_time = end_time-start_time
    print(f'Execution time: {execution_time:.2f} seconds')