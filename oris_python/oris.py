import logging
import requests
import xml.etree.ElementTree as ET
import pandas as pd

logger = logging.getLogger(__name__)

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
    
class Oris:
    """Python client for Oris
    """
    def __init__(self, url="https://reflex.link", verify_ssl=True):
        """Init Oris client

        Args:
            url (str, optional): URL to Oris. Defaults to "https://www.x-oris.com".
            verify_ssl (bool, optional): verify if connection is secure. Defaults to True.
        """
        self._url = url
        self._verify_ssl = verify_ssl
        self._id = None

    def connect(self, user: str, passwd: str):
        """Connect to oris backend

        Args:
            user (str): username
            passwd (str): password

        Returns:
            str: token id
        """

        response = requests.get(f"{self._url}/form0001?user={user}&pass={passwd}&xml=true", verify=self._verify_ssl)
        root = ET.fromstring(response.text)
        self._id = root.get("id")
        if(self._id == None):
            logger.warning(f'Unable to connect {user} to Oris')
        else:
            logger.info(f'{user} connected to Oris')

    def get_db(self, db: str, db_path: str, archives = "no"):
        headers = {
            "User-Agent": "Python",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "X-Oris-Basepath": f"{self._url}/{self._id}/{db_path}",
            "Referer": f"{self._url}/{self._id}/doc_vegarw/4_Acces/Parametrage/"
        }

        response = requests.get(f"{self._url}/rest/{db}s?glob={archives}", headers=headers)
        if(response.status_code == 200):
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
            "Referer": f"{self._url}/{self._id}/doc_vegarw/4_Acces/Parametrage/"
        }

        response = requests.get(f"{self._url}/rest/{db}s?readparam=true", headers=headers)
        if(response.status_code == 200):
            logger.info(f'{db} parameters received')
        else:
            logger.error(f'Unable to get {db} parameters at {db_path}')

        # logger.debug(params)
        return response.json().get("champs")
    
    def get_db_as_dataframe(self, db: str, db_path: str, archives = "no"):
        params = self.get_db_params(db, db_path)
        
        col_idx = {}
        col_date_idx = []
        col_number_idx = []
        col_bool_idx = []
        col_formule_idx = []
        
        for champ in params:
            col_name = champ.get('name').lower().replace(" ", "_").replace("'","") + '_' +champ.get('id')
            col_idx[champ.get('idrest')] = col_name
            if(champ.get("type") == "date"):
                col_date_idx.append(col_name)
            if(champ.get("type") == "bool"):
                col_bool_idx.append(col_name)
            if(champ.get("type") == "bcd" or champ.get("type") == "heure"):
                col_number_idx.append(col_name)
            if(champ.get("type") == "formule"):
                col_formule_idx.append(col_name)
        
        logger.debug(f'column indexes: {col_idx}')
        logger.debug(f'date columns: {col_date_idx}')
        logger.debug(f'number columns: {col_number_idx}')
        logger.debug(f'boolean columns: {col_bool_idx}')
        logger.debug(f'formule columns: {col_formule_idx}')

        data = self.get_db(db, db_path, archives)
        df = pd.DataFrame.from_records(data, index="id")
        df.rename(columns=col_idx, inplace=True)
        df.drop(columns=["tri"], inplace=True)
        df[col_date_idx] = df[col_date_idx].replace(",", "").apply(lambda x: pd.to_datetime(x, errors="coerce", dayfirst=True))
        df[col_bool_idx] = df[col_bool_idx].apply(pd.to_numeric, errors="coerce").astype(bool)
        df[col_number_idx] = df[col_number_idx].apply(safe_to_numeric)
        df[col_formule_idx] = df[col_formule_idx].apply(infer_formule_type)
        return df
