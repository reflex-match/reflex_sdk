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
        ("Achats", "doc_osmose/1_coordination/Gestion/", "no"),
        ("SAV", "doc_osmose/1_coordination/Gestion/", "no"),
        ("Stock", "doc_osmose/1_Fabrication/Stock/Projet STOCK QUADRA/", "no"),
        ("Devis", "doc_osmose/1_coordination/Gestion/", "no"),
        ("Planning", "doc_osmose/2_intranet/", "no"),
        ("Os_Prod_suivi", "doc_osmose/2_intranet/", "no"),
        ("All_Equipements", "doc_oris/1_general/", "yes"),
        ("All_Interventions", "doc_oris/1_general/", "yes"),
    ]

    client = Oris(os.getenv('ORIS_URL'))
    client.connect(os.getenv('ORIS_USER'), os.getenv('ORIS_PASSWORD'))

    for bdd in bdds:
        df = client.get_db_as_dataframe(bdd[0], bdd[1], bdd[2])
        df.to_sql(f'os_{bdd[0].lower()}', connection, if_exists='replace', index=False)

if __name__ == '__main__':
    main()