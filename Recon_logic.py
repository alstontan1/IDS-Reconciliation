from datetime import date, timedelta
from dotenv import find_dotenv, load_dotenv
import os
import Recon_Functions as ReconFunctions

if __name__ == '__main__':
    #Initialize
    load_dotenv(find_dotenv())
    this_date = str(date.today() - timedelta(1)) #'2026-05-19'
    db = os.getenv('db_name')
    tb = os.getenv('tb_name')
    open_dir = r'C:\Users\USER\Downloads'
    reconciliation_file_name = f'Rekonsiliasi_Transaksi_{this_date.replace('-','_')}.csv'
    cursor, driver, wait = ReconFunctions.boot(user=os.getenv('db_user'), password=os.getenv('db_password'), database=db, download_directory=open_dir)
    web = ReconFunctions.create_web_object(website='viatelecom', date=this_date)
    recon = ReconFunctions.reconciliation()
    
    #RPA
    web.download_transactions(email=os.getenv('web_email'), password=os.getenv('web_password'), driver_name=driver, wait_name=wait)
    web.rpa_quit(driver_name=driver,download_directory=open_dir,temporary_extension='.crdownload',timeout=300)
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