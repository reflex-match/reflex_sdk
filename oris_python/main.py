import logging
from oris import Oris
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine
import warnings

warnings.simplefilter("ignore")

logger = logging.getLogger(__name__)

def main():
    logging.basicConfig(filename='', level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    load_dotenv()
    engine = create_engine(f'postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB')}')
    
    # Check connection
    try:
        connection = engine.connect()
        logger.info("Connection to PostgreSQL established successfully!")
    except Exception as e:
        logger.error(f"Connection failed! Error: {e}")

    bdds = [
        ("Agency_Document", "doc_reflex/1_data/sdk/agency", "yes")
    ]

    client = Oris(os.getenv('ORIS_URL'))
    client.connect(os.getenv('ORIS_USER'), os.getenv('ORIS_PASSWORD'))

    for bdd in bdds:
        df = client.get_db_as_dataframe(bdd[0], bdd[1], bdd[2])
        df.to_sql(f'os_{bdd[0].lower()}', connection, if_exists='replace', index=False)

if __name__ == '__main__':
    main()