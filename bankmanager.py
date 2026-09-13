import requests
import sqlite3
from datetime import datetime
import pytz
import json
import os
import re
import traceback

def getInfo(call):
    r = requests.get(call, timeout=10)
    r.raise_for_status()
    return r.json()
def clean_name(text):
    if not text:
        return text
    return re.sub(r'§[0-9a-fk-orx]', '', text)

def job():
    conn = None
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, 'config.json')
        db_path = os.path.join(current_dir, 'bankmanager.db')

        with open(config_path, 'r') as f:
            config = json.load(f)
        uuid = config['uuid']
        API_KEY = config['api_key']

        url = f"https://api.hypixel.net/v2/skyblock/profiles?key={API_KEY}&uuid={uuid}"

        data = getInfo(url)

        conn = sqlite3.connect(db_path)
        conn.cursor().execute("""CREATE TABLE IF NOT EXISTS bankmanager
                                 (
                                     id             INTEGER PRIMARY KEY AUTOINCREMENT,
                                     timestamp      TEXT UNIQUE,
                                     amount         REAL,
                                     balance        INTEGER,
                                     change         TEXT,
                                     action         TEXT,
                                     initiator_name TEXT
                                 )
                              """)

        profile = data['profiles'][0]
        banking = profile['banking']
        balance = round(banking['balance'])
        detailed_balance = balance
        transactions = banking['transactions']
        all_transactions = len(transactions)
        balance_history = []
        new_rows_count = 0

        sql = ('''INSERT OR IGNORE INTO bankmanager (timestamp, amount, balance, change, action, initiator_name)
                  VALUES (?, ?, ?, ?, ?, ?)''')

        for i in range(0, all_transactions):
            transaction = transactions[all_transactions - 1 - i]
            balance = detailed_balance
            balance_history.append(detailed_balance)
            if transaction['action'] == "DEPOSIT":
                detailed_balance = balance - round(transaction['amount'])
            else:
                detailed_balance = balance + round(transaction['amount'])
        balance_history = list(reversed(balance_history))

        for i in range(0, all_transactions):
            transaction = transactions[i]
            timestamp = transaction['timestamp']
            utc_time = datetime.fromtimestamp(timestamp / 1000, tz=pytz.utc)
            ca_time = utc_time.astimezone(pytz.timezone('US/Pacific'))
            transaction['timestamp'] = ca_time.strftime('%D %H:%M:%S')

            transaction['amount'] = round(transaction['amount'])
            if transaction['action'] == "DEPOSIT":
                change = f"+{transaction['amount']:,}"
            else:
                change = f"-{transaction['amount']:,}"
            clean_initiator = clean_name(transaction['initiator_name'])
            data_tuple = (
                transaction['timestamp'],
                transaction['amount'],
                balance_history[i],
                change,
                transaction['action'],
                clean_initiator,
            )
            cur = conn.execute(sql, data_tuple)
            new_rows_count += cur.rowcount

        if new_rows_count > 0:
            print(f"Success: Added {new_rows_count} new transaction(s) to the database.")
        else:
            print("Database is up to date. No changes made.")
        conn.commit()
    except requests.exceptions.Timeout:
        print("Error: Request timed out.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Network/API error. {e}")
        return None
    except Exception as e:
        error_detail = traceback.format_exc()
        print(error_detail)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    job()