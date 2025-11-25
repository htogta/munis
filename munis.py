import streamlit as st

conn = st.connection("postgresql", type="sql")

df = conn.query('SELECT * FROM bonds;', ttl="10m")

for row in df.itertuples():
    st.write(f"{row.cusip}")
