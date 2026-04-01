import logging
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import psycopg2
from psycopg2 import sql
import json

logger = logging.getLogger(__name__)

def ensure_database_exists(
    dbname: str,
    user: str,
    password: str,
    host: str = "localhost",
    port: int = 5432,
):
    conn = psycopg2.connect(
        dbname="postgres",
        user=user,
        password=password,
        host=host,
        port=port,
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (dbname,))
            if cur.fetchone() is None:
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
                logger.info(f'Database "{dbname}" created')
            else:
                logger.debug(f'Database "{dbname}" already exists')
    finally:
        conn.close()

def safe_to_numeric(ser: pd.Series):
    try:
        tmp = ser.str.replace("-", "0")
        tmp = tmp.str.replace(",", ".", regex=True)
        tmp = pd.to_numeric(tmp, errors="coerce")
        return tmp
    except Exception as e:
        logger.warning(f'{e} for {ser.name}')
        return ser

def infer_formule_type(ser: pd.Series):
    try:
        tmp = ser.str.replace(",", ".", regex=True)
        tmp = pd.to_numeric(tmp)
        logger.debug(f'Formule "{ser.name}" is numeric')
        return tmp
    except:
        pass

    try:
        tmp = ser.str.replace(",", "").replace(".", "")
        tmp = pd.to_datetime(tmp, dayfirst=True)
        logger.debug(f'Formule "{ser.name}" is date')
        return tmp
    except:
        logger.debug(f'Formule "{ser.name}" is string')
        return ser
    
def infer_list_type(ser: pd.Series):
    def parse_value(val):
        if pd.isna(val):
            return []

        val = str(val).strip()

        if val == "":
            return []

        parts = [p.strip() for p in val.split(",") if p.strip() != ""]

        result = []
        for p in parts:
            try:
                result.append(int(p))
            except:
                try:
                    result.append(float(p))
                except:
                    result.append(p)

        return result

    parsed = ser.apply(parse_value)

    logger.debug(f'List "{ser.name}" parsed as list')

    return parsed

def save_last_updated(db: str, last_updated):
    with open("last_updated.json", "r") as f:
        data = json.load(f)

    data[db] = last_updated

    with open("last_updated.json", "w") as f:
        json.dump(data, f, indent=4)

class Oris:
    """Python client for Oris
    """
    def __init__(self, url="https://reflex.link", verify_ssl=True):
        self._url = url
        self._verify_ssl = verify_ssl
        self._id = None

    def connect(self, user: str, passwd: str):
        response = requests.get(
            f"{self._url}/form0001?user={user}&pass={passwd}&xml=true",
            verify=self._verify_ssl
        )
        root = ET.fromstring(response.text)
        self._id = root.get("id")
        if self._id is None:
            logger.warning(f'Unable to connect {user} to Oris')
        else:
            logger.info(f'{user} connected to Oris')

    def get_last_update(self, db: str, db_path: str):
        headers = {
            "User-Agent": "Python",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "X-Oris-Basepath": f"{self._url}/{self._id}/{db_path}",
            "Referer": f"{self._url}/{self._id}"
        }

        response = requests.get(f"{self._url}/{self._id}/rest/system_database/date?base={db_path}", headers=headers)
        if response.status_code == 200:
            logger.info(f'{db} last update received')
        else:
            logger.error(f'Unable to get {db} last update at {db_path}')
            
        return response.json().get("date")

    def get_db(self, db: str, db_path: str, archives="no"):
        headers = {
            "User-Agent": "Python",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "X-Oris-Basepath": f"{self._url}/{self._id}/{db_path}",
            "Referer": f"{self._url}/{self._id}"
        }

        url = f"{self._url}/{self._id}/{db_path}?json=true"

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            logger.info(f'{db} received')
        else:
            logger.error(f'Unable to get {db} at {db_path}')

        return response.json().get(f'{db.lower()}s')

    def get_db_params(self, db: str, db_path: str):
        headers = {
            "User-Agent": "Python",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "X-Oris-Basepath": f"{self._url}/{self._id}/{db_path}",
            "Referer": f"{self._url}/{self._id}"
        }

        response = requests.get(f"{self._url}/{self._id}/{db_path}?readparam=true&json=true", headers=headers)
        if response.status_code == 200:
            logger.info(f'{db} parameters received')
        else:
            logger.error(f'Unable to get {db} parameters at {db_path}')

        return response.json().get("champs")
    
    
    def get_db_as_dataframe(self, db: str, db_path: str, archives="no"):
        params = self.get_db_params(db, db_path)

        date = self.get_last_update(db, db_path)

        save_last_updated(db, date)

        col_idx = {}
        col_date_idx = []
        col_number_idx = []
        col_bool_idx = []
        col_formule_idx = []
        col_list_idx = []

        for champ in params:
            col_name = champ.get('name').lower().replace(" ", "_").replace("'", "")
            col_idx[champ.get('idrest')] = col_name
            if champ.get("type") == "date":
                col_date_idx.append(col_name)
            if champ.get("type") == "bool":
                col_bool_idx.append(col_name)
            if champ.get("type") == "bcd" or champ.get("type") == "heure":
                col_number_idx.append(col_name)
            if champ.get("type") == "formule":
                col_formule_idx.append(col_name)
            if champ.get("type") == "liste" or champ.get("type") == "champ":
                col_list_idx.append(col_name)

        logger.debug(f'column indexes: {col_idx}')
        logger.debug(f'date columns: {col_date_idx}')
        logger.debug(f'number columns: {col_number_idx}')
        logger.debug(f'boolean columns: {col_bool_idx}')
        logger.debug(f'formule columns: {col_formule_idx}')
        logger.debug(f'list columns: {col_list_idx}')

        data = self.get_db(db, db_path, archives)
        df = pd.DataFrame.from_records(data, index="id")
        df.rename(columns=col_idx, inplace=True)
        df.drop(columns=["tri"], inplace=True)
        df[col_date_idx] = df[col_date_idx].replace(",", "").apply(lambda x: pd.to_datetime(x, errors="coerce", dayfirst=True))
        df[col_bool_idx] = df[col_bool_idx].apply(pd.to_numeric, errors="coerce").astype(bool)
        df[col_number_idx] = df[col_number_idx].apply(safe_to_numeric)
        df[col_formule_idx] = df[col_formule_idx].apply(infer_formule_type)
        df[col_list_idx] = df[col_list_idx].apply(infer_list_type)
        return df