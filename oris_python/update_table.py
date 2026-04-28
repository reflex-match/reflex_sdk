import logging

import requests
from oris import Oris, ensure_database_exists
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine
import warnings
import json

warnings.simplefilter("ignore")

logger = logging.getLogger(__name__)

def is_up_to_date(newDate, db):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "last_updated.json")

    with open(file_path, "r") as f:
        data = json.load(f)
        
    if db not in data:
        return False
    
    last_updated = data[db]
    return newDate == last_updated

def update_tables(bdds):
    logging.basicConfig(
        filename='',
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    load_dotenv()

    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_name = os.getenv("DB")
    db_port = os.getenv("DB_PORT", 5432)

    ensure_database_exists(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=int(db_port)
    )

    engine = create_engine(
        f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    )

    try:
        connection = engine.connect()
        logger.info("Connection to PostgreSQL established successfully!")
    except Exception as e:
        logger.error(f"Connection failed! Error: {e}")
        return

    client = Oris(os.getenv("ORIS_URL"))
    client.connect(os.getenv("ORIS_USER"), os.getenv("ORIS_PASSWORD"))

    for bdd in bdds:
        newDate = client.get_last_update(bdd[0], bdd[1])
        if not is_up_to_date(newDate, bdd[0]):
            logger.info(f'Updating table {bdd[0]}')
            df = client.get_db_as_dataframe(bdd[0], bdd[1], bdd[2])
            df.to_sql(f"os_{bdd[0].lower()}", con=connection, if_exists="replace", index=False)
        else:
            logger.debug(f'Table {bdd[0]} is already up to date')

    connection.close()
    logger.info("Process completed successfully.")