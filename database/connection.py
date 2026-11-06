
import os
import oracledb
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


def get_connection():

    # Read database configuration
    username = os.getenv("ORACLE_USER")
    password = os.getenv("ORACLE_PASSWORD")
    host = os.getenv("ORACLE_HOST")
    port = os.getenv("ORACLE_PORT")
    service = os.getenv("ORACLE_SERVICE")

    # Check required settings
    if not all([username, password, host, port, service]):
        raise ValueError("Oracle database configuration is incomplete.")

    # Create database connection
    dsn = f"{host}:{port}/{service}"

    connection = oracledb.connect(
        user=username,
        password=password,
        dsn=dsn
    )

    return connection
