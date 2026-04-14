import logging
import os
import re
import warnings

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from sqlalchemy import create_engine, inspect, text, bindparam
from sqlalchemy.exc import SQLAlchemyError

from update_table import update_tables

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
            "GET /agent/missionpropositions/<agent_id>?limit=<limit>&offset=<offset>&mission_type_ids=<mission_type_ids>&outfit_ids=<outfit_ids>&distance=<distance>&hourly_rate=<hourly_rate>"
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

    defult_path = "doc_reflex/1_data/bd/"

    update_tables([
        ("agents", f"{defult_path}agents_gestion.ini", "no"),
        ("agent_agreement", f"{defult_path}agent_agreement_gestion.ini", "no"),
        ("agent_mission", f"{defult_path}agent_mission_gestion.ini", "no"),
        ("agreement", f"{defult_path}agreement_gestion.ini", "no"),
        ("missions", f"{defult_path}missions_gestion.ini", "no"),
        ("mission_service", f"{defult_path}mission_service_gestion.ini", "no"),
        ("mission_type", f"{defult_path}mission_type_gestion.ini", "no"),
        ("outfits", f"{defult_path}outfits_gestion.ini", "no"),
        ("sub_missions", f"{defult_path}sub_missions_gestion.ini", "no"),
        ("unavailability", f"{defult_path}unavailability_gestion.ini", "no")
    ])

    limit = request.args.get("limit", default=10, type=int)
    offset = request.args.get("offset", default=0, type=int)

    mission_type_ids = request.args.getlist("mission_type_ids", type=int)
    outfit_ids = request.args.getlist("outfit_ids", type=int)

    distance = request.args.get("distance", default=3, type=int)
    hourly_rate = request.args.get("hourly_rate", default=None, type=float)

    if distance not in [1, 2, 3]:
        return jsonify({"error": "distance must be 1, 2 or 3"}), 400

    has_mission_type_filter = len(mission_type_ids) > 0
    has_outfit_filter = len(outfit_ids) > 0
    has_hourly_rate_filter = hourly_rate is not None

    if not has_mission_type_filter:
        mission_type_ids = [-1]

    if not has_outfit_filter:
        outfit_ids = [-1]

    try:
        with get_connection() as connection:
            requete_agent = text("""
                SELECT *
                FROM os_agents a
                WHERE a.uid = :agent_id
                LIMIT 1
            """)

            result_agent = connection.execute(requete_agent, {
                "agent_id": agent_id
            })

            agent = result_agent.fetchone()

            if not agent:
                return jsonify({"error": f"Agent {agent_id} not found"}), 404

            agent_data = dict(agent._mapping)

            if distance == 1:
                distance_condition = "mi.city_code = :agent_city_code"
            elif distance == 2:
                distance_condition = "mi.area_code = :agent_area_code"
            else:
                distance_condition = "mi.country_code = :agent_country_code"

            mission_type_condition = ""
            if has_mission_type_filter:
                mission_type_condition = "AND m.mission_type_id = ANY(:mission_type_ids)"

            outfit_condition = ""
            if has_outfit_filter:
                outfit_condition = "AND m.outfits::int[] && :outfit_ids"

            hourly_rate_condition = ""
            if has_hourly_rate_filter:
                hourly_rate_condition = "AND m.hourly_rate >= :hourly_rate"

            requete = text(f"""
                SELECT DISTINCT 
                    m.*,
                    mi.city_code AS mission_city_code,
                    mi.area_code AS mission_area_code,
                    mi.country_code AS mission_country_code,
                    CASE
                        WHEN mi.city_code = :agent_city_code THEN 1
                        WHEN mi.area_code = :agent_area_code THEN 2
                        WHEN mi.country_code = :agent_country_code THEN 3
                        ELSE 4
                    END AS distance_order
                FROM os_sub_missions m
                JOIN os_agent_agreement aa ON aa.agent_id = :agent_id
                JOIN os_missions mi ON mi.id = m.mission_id
                WHERE {distance_condition}
                AND (aa.agreements_ids::int[])[1] = ANY(m.agent_type::int[])
                {mission_type_condition}
                {outfit_condition}
                {hourly_rate_condition}
                ORDER BY distance_order
                LIMIT :limit OFFSET :offset
            """)

            params = {
                "agent_id": agent_id,
                "agent_city_code": agent_data.get("city_code"),
                "agent_area_code": agent_data.get("area_code"),
                "agent_country_code": agent_data.get("country_code"),
                "mission_type_ids": mission_type_ids,
                "outfit_ids": outfit_ids,
                "hourly_rate": hourly_rate,
                "limit": limit,
                "offset": offset
            }

            result = connection.execute(requete, params)
            rows = [dict(row._mapping) for row in result]

        return jsonify({
            "agent_id": agent_id,
            "filters": {
                "mission_type_ids": mission_type_ids if has_mission_type_filter else [],
                "outfit_ids": outfit_ids if has_outfit_filter else [],
                "distance": distance,
                "hourly_rate": hourly_rate,
                "limit": limit,
                "offset": offset
            },
            "count": len(rows),
            "data": rows
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