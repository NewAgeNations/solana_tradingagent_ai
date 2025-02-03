import psycopg2
from datetime import datetime
import json
import pandas as pd
import streamlit as st

# Load database configuration from config.json
with open("config.json", "r") as config_file:
    config = json.load(config_file)

DATABASE_CONFIG = config["database_config"]

# Function to insert a new record into the dexscreener table
def insert_record(token_address, token_name, entry_price):
    timestamp = datetime.now()  # Automatically generate the current timestamp

    try:
        with psycopg2.connect(**DATABASE_CONFIG) as conn:
            with conn.cursor() as cursor:
                # Create the dexscreener table if it doesn't exist
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS dexscreener (
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    token_address TEXT PRIMARY KEY,
                    token_name TEXT,
                    entry_price DECIMAL(18, 8)  -- New column for entry price
                );
                """)

                # Insert the new record into the table
                cursor.execute("""
                INSERT INTO dexscreener (timestamp, token_address, token_name, entry_price)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (token_address) DO UPDATE SET
                    timestamp = EXCLUDED.timestamp,
                    token_name = EXCLUDED.token_name,
                    entry_price = EXCLUDED.entry_price;
                """, (timestamp, token_address, token_name, entry_price))

                conn.commit()
                st.success(f"Record for {token_address} successfully saved.")

    except Exception as e:
        st.error(f"Error inserting record into database: {str(e)}")

# Function to display all records in the dexscreener table
def display_records():
    try:
        with psycopg2.connect(**DATABASE_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM dexscreener ORDER BY timestamp DESC;")
                rows = cursor.fetchall()

                # Convert rows to a DataFrame for better display in Streamlit
                df = pd.DataFrame(rows, columns=["Timestamp", "Token Address", "Token Name", "Entry Price"])
                return df

    except Exception as e:
        st.error(f"Error fetching records from database: {str(e)}")
        return pd.DataFrame()  # Return an empty DataFrame in case of error

# Function to update an existing record in the dexscreener table
def update_record(token_address, new_token_name, new_entry_price):
    try:
        with psycopg2.connect(**DATABASE_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE dexscreener 
                    SET token_name = %s, entry_price = %s 
                    WHERE token_address = %s;
                """, (new_token_name, new_entry_price, token_address))
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    st.success(f"Record for {token_address} successfully updated.")
                else:
                    st.warning(f"No record found for {token_address}.")

    except Exception as e:
        st.error(f"Error updating record: {str(e)}")

# Function to delete a record from the dexscreener table
def delete_record(token_address):
    try:
        with psycopg2.connect(**DATABASE_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM dexscreener 
                    WHERE token_address = %s;
                """, (token_address,))
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    st.success(f"Record for {token_address} successfully deleted.")
                else:
                    st.warning(f"No record found for {token_address}.")

    except Exception as e:
        st.error(f"Error deleting record: {str(e)}")

# Streamlit Dashboard
def main():
    st.title("DexScreener Database Management")

    # Tabbed interface for inserting and displaying records
    tab1, tab2, tab3 = st.tabs(["Insert Record", "Update Record", "Delete Record"])

    # Tab 1: Insert Record
    with tab1:
        st.header("Insert New Token Record")
        token_address = st.text_input("Enter Token Address:")
        token_name = st.text_input("Enter Token Name:")
        entry_price = st.number_input("Enter Entry Price:", min_value=0.0, format="%.8f")  # Allow decimal input

        if st.button("Save Record"):
            if not token_address or not token_name:
                st.error("Token Address and Token Name cannot be empty!")
            else:
                insert_record(token_address.strip(), token_name.strip(), entry_price)

    # Tab 2: Update Record
    with tab2:
        st.header("Update Existing Token Record")
        update_token_address = st.text_input("Enter Token Address to Update:")
        update_token_name = st.text_input("Enter New Token Name:")
        update_entry_price = st.number_input("Enter New Entry Price:", min_value=0.0, format="%.8f")

        if st.button("Update Record"):
            if not update_token_address or not update_token_name or update_entry_price <= 0.0:
                st.error("All fields must be filled out correctly!")
            else:
                update_record(update_token_address.strip(), update_token_name.strip(), update_entry_price)

    # Tab 3: Delete Record
    with tab3:
        st.header("Delete Token Record")
        delete_token_address = st.text_input("Enter Token Address to Delete:")

        if st.button("Delete Record"):
            if not delete_token_address:
                st.error("Token Address must be provided!")
            else:
                delete_record(delete_token_address.strip())

    # View Records Tab (optional)
    with st.expander("View All Records"):
        records_df = display_records()
        
        if not records_df.empty:
            st.dataframe(records_df)
        else:
            st.write("No records found in the database.")

if __name__ == "__main__":
    main()
