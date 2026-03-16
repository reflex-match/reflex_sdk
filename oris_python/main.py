import logging
from oris import Oris, ensure_database_exists
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine
import warnings

warnings.simplefilter("ignore")

logger = logging.getLogger(__name__)

def main():
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

    bdds = [
        ("Agency_Document", "doc_reflex/1_data/bd/agency", "no")
    ]

    client = Oris(os.getenv("ORIS_URL"))
    client.connect(os.getenv("ORIS_USER"), os.getenv("ORIS_PASSWORD"))

    for bdd in bdds:
        df = client.get_db_as_dataframe(bdd[0], bdd[1], bdd[2])
        df.to_sql(f"os_{bdd[0].lower()}", connection, if_exists="replace", index=False)

    connection.close()
    logger.info("Process completed successfully.")

if __name__ == "__main__":
    main()