import logging
import os
import re
import warnings

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

import create_db

warnings.simplefilter("ignore")

logging.basicConfig(
    filename="",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST", "localhost")
db_name = os.getenv("DB")
db_port = os.getenv("DB_PORT", "5432")

DATABASE_URL = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

engine = create_engine(DATABASE_URL)


def get_connection():
    return engine.connect()


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "API Reflex opérationnelle",
        "routes": [
            "GET /health",
            "GET /tables",
            "GET /table/<table_name>",
            "GET /agent/missionpropositions/<agent_id>?limit=<limit>&offset=<offset>"
        ]
    })


@app.route("/health", methods=["GET"])
def health():
    try:
        with get_connection() as connection:
            connection.execute(text("SELECT 1"))
        return jsonify({
            "status": "ok",
            "database": "connected"
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "error",
            "database": "disconnected",
            "message": str(e)
        }), 500


@app.route("/tables", methods=["GET"])
def get_tables():
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        return jsonify({
            "tables": tables
        }), 200
    except Exception as e:
        logger.error(f"Unable to list tables: {e}")
        return jsonify({
            "error": str(e)
        }), 500


@app.route("/table/<table_name>", methods=["GET"])
def get_table_content(table_name):
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)

    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        if table_name not in tables:
            return jsonify({
                "error": f"La table '{table_name}' n'existe pas"
            }), 404

        query = text(f'SELECT * FROM "{table_name}" LIMIT :limit OFFSET :offset')

        with get_connection() as connection:
            result = connection.execute(query, {
                "limit": limit,
                "offset": offset
            })
            rows = [dict(row._mapping) for row in result]

        return jsonify({
            "table": table_name,
            "count": len(rows),
            "limit": limit,
            "offset": offset,
            "data": rows
        }), 200

    except SQLAlchemyError as e:
        logger.error(f"Error while reading table {table_name}: {e}")
        return jsonify({
            "error": str(e)
        }), 500

def extraire_ids(valeur):
    if valeur is None:
        return set()

    if isinstance(valeur, list):
        return {int(v) for v in valeur if str(v).isdigit()}

    valeur = str(valeur).strip()
    if not valeur:
        return set()

    return {int(v) for v in re.findall(r"\d+", valeur)}


@app.route("/agent/missionpropositions/<agent_id>", methods=["GET"])
def get_agent_mission_propositions(agent_id):
    limit = request.args.get("limit", default=10, type=int)
    offset = request.args.get("offset", default=0, type=int)

    mission_type_id = request.args.get("mission_type_id", default=None, type=int)
    outfit_id = request.args.get("outfit_id", default=None, type=int)
    choice = request.args.get("choice", default=3, type=int)
    hourly_rate = request.args.get("hourly_rate", default=None, type=float)

    if choice not in [1, 2, 3]:
        return jsonify({"error": "choice must be 1, 2 or 3"}), 400

    try:
        with get_connection() as connection:
            requete_agent = text("""
                SELECT
                    a.uid,
                    a.firstname,
                    a.lastname,
                    a.city_code,
                    a.area_code
                FROM os_agents a
                WHERE a.uid = :agent_id
                LIMIT 1
            """)

            agent = connection.execute(requete_agent, {
                "agent_id": agent_id
            }).mappings().first()

            if not agent:
                return jsonify({"error": f"Agent {agent_id} not found"}), 404

            requete_agreements = text("""
                SELECT
                    aa.agreements_ids
                FROM os_agent_agreement aa
                WHERE aa.agent_id = :agent_id
                  AND aa.is_valid = true
                  AND (
                        aa.expiration IS NULL
                        OR aa.expiration >= CURRENT_DATE
                  )
            """)

            lignes_agreements = connection.execute(requete_agreements, {
                "agent_id": agent_id
            }).mappings().all()

            agreements_agent = set()
            for ligne in lignes_agreements:
                agreements_agent |= extraire_ids(ligne["agreements_ids"])

            requete_missions = text("""
                SELECT * FROM os_missions
            """)

            resultats = connection.execute(requete_missions, {
                "agent_city_code": agent["city_code"],
                "agent_area_code": agent["area_code"],
                "mission_type_id": mission_type_id,
                "outfit_id": outfit_id,
                "choice": choice,
                "hourly_rate": hourly_rate,
                "limit": limit,
                "offset": offset
            })

            lignes = [dict(ligne._mapping) for ligne in resultats]

        return jsonify({
            "agent_id": agent_id,
            "agent": {
                "uid": agent["uid"],
                "firstname": agent["firstname"],
                "lastname": agent["lastname"],
                "city_code": agent["city_code"],
                "area_code": agent["area_code"],
                "agreements_ids": sorted(list(agreements_agent))
            },
            "filters": {
                "mission_type_id": mission_type_id,
                "outfit_id": outfit_id,
                "choice": choice,
                "hourly_rate": hourly_rate,
                "limit": limit,
                "offset": offset
            },
            "count": len(lignes),
            "data": lignes
        }), 200

    except SQLAlchemyError as e:
        logger.error(f"Error while reading mission propositions for agent {agent_id}: {e}")
        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app_host = os.getenv("APP_HOST", "0.0.0.0")
    app_port = int(os.getenv("APP_PORT", 5000))
    app_debug = os.getenv("APP_DEBUG", "True").lower() == "true"

    app.run(host=app_host, port=app_port, debug=app_debug)