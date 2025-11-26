import streamlit as st

conn = st.connection("postgresql", type = "sql")

# our tabs
market_tab, bonds_tab, risk_tab = st.tabs([
  "Market Overview",
  "Bond Explorer",
  "Ratings & Risk"
])

# the bond explorer page's code all goes in here
def render_bond_explorer():
  st.header("🔍 Bond Explorer") # TODO emoji is bad idea? or nah

  cusips_df = conn.query(
    "SELECT cusip FROM bonds ORDER BY cusip;",
    ttl="5m"
  )
  selected_cusip = st.selectbox(
    "Select a bond (CUSIP)", cusips_df["cusip"].tolist()
  )

  if not selected_cusip:
    return

  st.divider()

  selected_cusip = selected_cusip.strip() # remove leading/trailing whitespace

  # getting bond metadata
  bond_sql = f"""
    SELECT
      b.id AS bond_id,
      b.cusip, b.type, b.coupon_rate, b.issue_date, b.maturity_date,
      b.duration, b.tax_status,
      bp.category AS purpose_category, bp.description AS purpose_description,
      i.name AS issuer_name, i.state AS issuer_state
    FROM bonds b
    JOIN bonds_purposes bp ON b.purpose_id = bp.id
    LEFT JOIN bonds_issuers bi ON bi.bond_id = b.id
    LEFT JOIN issuers i ON bi.issuer_id = i.id
    WHERE b.cusip = :cusip
    LIMIT 1;
  """

  bond_df = conn.query(
    bond_sql,
    params = {"cusip": selected_cusip},
    ttl="5m"
  )

  if bond_df.empty:
    st.warning("No metadata found for this bond.")
    return

  bond = bond_df.iloc[0]

  # display metadata
  st.subheader("Bond Summary")
  st.write(f"**CUSIP:** `{bond.cusip}`")
  st.write(f"**Issuer:** {bond.issuer_name} ({bond.issuer_state})")
  st.write(f"**Purpose:** {bond.purpose_category} — {bond.purpose_description}")
  st.write(f"**Type:** {bond.type}")
  st.write(f"**Coupon:** {bond.coupon_rate}%")
  st.write(f"**Issue Date:** {bond.issue_date}")
  st.write(f"**Maturity Date:** {bond.maturity_date}")
  st.write(f"**Duration:** {bond.duration}")
  st.write(f"**Tax Status:** {'Tax-Exempt' if bond.tax_status else 'Taxable'}")

  # TODO funky visualizations

with bonds_tab:
  render_bond_explorer()
