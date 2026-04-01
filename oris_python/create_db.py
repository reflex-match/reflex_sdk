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
    
    defult_path = "doc_reflex/1_data/bd/"

    bdds = [
        ("Agency_Document", f"{defult_path}agency_document_gestion.ini", "no"),
        ("messages", f"{defult_path}messages_gestion.ini", "no"),
        ("agency", f"{defult_path}agency_gestion.ini", "no"),
        ("agents", f"{defult_path}agents_gestion.ini", "no"),
        ("agent_agreement", f"{defult_path}agent_agreement_gestion.ini", "no"),
        ("agent_mission", f"{defult_path}agent_mission_gestion.ini", "no"),
        ("agreement", f"{defult_path}agreement_gestion.ini", "no"),
        ("missions", f"{defult_path}missions_gestion.ini", "no"),
        ("mission_service", f"{defult_path}mission_service_gestion.ini", "no"),
        ("mission_type", f"{defult_path}mission_type_gestion.ini", "no"),
        ("outfits", f"{defult_path}outfits_gestion.ini", "no"),
        ("review_agency", f"{defult_path}review_agency_gestion.ini", "no"),
        ("review_agent", f"{defult_path}review_agent_gestion.ini", "no"),
        ("sub_missions", f"{defult_path}sub_missions_gestion.ini", "no"),
        ("unavailability", f"{defult_path}unavailability_gestion.ini", "no"),
        ("user_agence", f"{defult_path}user_agence_gestion.ini", "no")

    ]

    client = Oris(os.getenv("ORIS_URL"))
    client.connect(os.getenv("ORIS_USER"), os.getenv("ORIS_PASSWORD"))

    for bdd in bdds:
        df = client.get_db_as_dataframe(bdd[0], bdd[1], bdd[2])
        df.to_sql(f"os_{bdd[0].lower()}", con=connection, if_exists="replace", index=False)

    connection.close()
    logger.info("Process completed successfully.")

if __name__ == "__main__":
    main()