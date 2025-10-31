import os
import sys
import streamlit as st
import psycopg2
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection parameters
DB_USER = os.getenv('DB_USER_DESTINATION')
DB_PASSWORD = os.getenv('DB_PASSWORD_DESTINATION')
DB_HOST = os.getenv('DB_HOST_DESTINATION')
DB_NAME = os.getenv('DB_NAME_DESTINATION')

def test_db_connection():
    st.title("Database Connection Test")
    
    try:
        # SQLAlchemy connection test
        connection_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
        engine = create_engine(connection_string)
        
        with engine.connect() as connection:
            result = connection.execute("SELECT version()")
            postgres_version = result.fetchone()[0]
            st.success(f"SQLAlchemy Connection Successful! PostgreSQL Version: {postgres_version}")
        
        # psycopg2 connection test
        conn = psycopg2.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            database=DB_NAME
        )
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        psycopg2_version = cursor.fetchone()[0]
        st.success(f"psycopg2 Connection Successful! PostgreSQL Version: {psycopg2_version}")
        
        cursor.close()
        conn.close()
        
        # Test reading data
        st.write("Attempting to read data from yield_level.mv_25_26_prediction_demand")
        query = "SELECT * FROM yield_level.mv_25_26_prediction_demand LIMIT 5"
        df = pd.read_sql(query, engine)
        st.dataframe(df)
        
    except Exception as e:
        st.error(f"Connection error: {e}")
        # Detailed error analysis
        st.write("Error Details:")
        st.write(f"User: {DB_USER}")
        st.write(f"Host: {DB_HOST}")
        st.write(f"Database: {DB_NAME}")
        
        # Check specific connection issues
        if "authentication" in str(e).lower():
            st.error("Authentication failed. Check username and password.")
        elif "connection refused" in str(e).lower():
            st.error("Connection refused. Check if the database is running and network settings.")
        elif "timeout" in str(e).lower():
            st.error("Connection timed out. Check network connectivity.")

if __name__ == "__main__":
    test_db_connection()