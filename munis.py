import streamlit as st
import pandas as pd
import altair as alt

conn = st.connection("postgresql", type = "sql")

# main heading
st.header("📊 M U N I S")
# st.subheader("A dashboard for the municipal bond market")

# our tabs
market_tab, bonds_tab, risk_tab = st.tabs([
  "Market Overview",
  "Bond Explorer",
  "Ratings & Risk"
])

# all the market overview code goes in here
def render_market_overview():
  st.header("📈 Market Overview")

  states = conn.query(
    "SELECT DISTINCT state FROM issuers ORDER BY state;", ttl = "10m"
  )["state"].tolist()
  types = conn.query(
    "SELECT DISTINCT type FROM bonds ORDER BY type;", ttl = "10m"
  )["type"].tolist()
  purposes = conn.query(
    "SELECT DISTINCT category FROM bonds_purposes ORDER BY category;", ttl = "10m"
  )["category"].tolist()

  col1, col2, col3 = st.columns(3)
  selected_states = col1.multiselect("Filter by State", states)
  selected_types = col1.multiselect("Filter by Bond Type", types)
  selected_purposes = col1.multiselect("Filter by Purpose Category", purposes)

  # building the WHERE clause
  where = []
  params = {}

  if selected_states: 
    where.append("i.state = ANY(:states)")
    params["states"] = selected_states

  if selected_types:
    where.append("b.type = ANY(:types)")
    params["types"] = selected_types

  if selected_purposes:
    where.append("bp.category = ANY(:purposes)")
    params["purposes"] = selected_purposes

  where_clause = "WHERE " + " AND ".join(where) if where else ""

  # loading yield data
  sql = f"""
    SELECT
      b.coupon_rate, b.duration, b.maturity_date, b.issue_date, b.cusip,
      i.state, b.type, bp.category AS purpose,
      t.price, t.yield
    FROM bonds b
    LEFT JOIN bonds_issuers bi ON bi.bond_id = b.id
    LEFT JOIN issuers i ON bi.issuer_id = i.id
    LEFT JOIN bonds_purposes bp ON bp.id = b.purpose_id
    LEFT JOIN LATERAL (
      SELECT tr.price, tr.yield
      FROM trades tr
      JOIN bonds_trades bt ON bt.trade_id = tr.id
      WHERE bt.bond_id = b.id
      ORDER BY tr.date DESC
      LIMIT 1
    ) t ON TRUE
    {where_clause}
    ORDER BY maturity_date;
  """

  df = conn.query(sql, params = params or None, ttl = "2m")
  if df.empty:
    st.warning("No bonds match your filter selections")
    return

  # derived fields
  df["maturity_date"] = pd.to_datetime(df["maturity_date"])
  df["issue_date"] = pd.to_datetime(df["issue_date"]) # convert to datetime first
  df["maturity_year"] = df["maturity_date"].dt.year
  df["years_to_maturity"] = (df["maturity_date"] - df["issue_date"]).dt.days / 365.0

  st.subheader("Aggregate Market Metrics")
  colA, colB, colC = st.columns(3)
  colA.metric("Avg Coupon", f"{df['coupon_rate'].mean():.2f}%")
  colB.metric("Avg Duration", f"{df['duration'].mean():.2f} yrs")
  colC.metric("Count", f"{len(df)} bonds")

  st.divider()

  # yield curve
  st.subheader("Yield Curve (Approximate)")
  
  curve_df = (
    df.groupby("maturity_year")["coupon_rate"]
    .mean()
    .reset_index()
    .sort_values("maturity_year")
  )
  
  st.line_chart(
    curve_df.rename(columns={"maturity_year": "index"}).set_index("index")
  )
  st.caption("This shows average coupon/yield grouped by maturity year.")

  st.divider()

  # yield distribution
  st.subheader("Distribution of Yields")
  chart = (
    alt.Chart(df)
    .mark_bar()
    .encode(
      alt.X("coupon_rate:Q", bin=alt.Bin(maxbins=30), title="Yield (%)"),
      alt.Y("count()", title="Number of Bonds"),
      tooltip=[alt.Tooltip("count()", title="Count")]
    )
    .properties(height=300)
  )
  st.altair_chart(chart, use_container_width=True)
  st.divider()

  # bond price vs yield
  st.subheader("Bond Price vs Yield")

  df_scatter = df.dropna(subset=["price", "yield"])

  # ensure price and yield exist (must join trades table)
  if "price" in df.columns and "yield" in df.columns:
    chart = (
      alt.Chart(df_scatter)
      .mark_line(point=True)
      .encode(
        x=alt.X("price:Q", title="Price ($)"),
        y=alt.Y("mean(yield):Q", title="Average Yield (%)"),
        color=alt.Color("state:N", title="State"),
        # color=alt.Color("maturity_bucket:N"),
        tooltip=[
          alt.Tooltip("cusip:N", title="CUSIP"),
          alt.Tooltip("yield:Q", format=".2f"),
          alt.Tooltip("price:Q", format=".2f"),
          "state:N",
          "type:N",
          "purpose:N",
        ]
      )
      .interactive()
      .properties(height=350)
    )
    st.altair_chart(chart, use_container_width=True)
    st.caption("Higher yields typically correspond to lower prices — showing the inverse price/yield relationship.")
  else:
    st.info("Trade price & yield data unavailable at this level — view details in Bond Explorer.")
  st.divider()

  # state comparison
  if not selected_states:
    st.subheader("Top States by Average Yield")
    state_yield = (
      df.groupby("state")["coupon_rate"]
      .mean()
      .sort_values(ascending=False)
      .head(10)
    )
    st.bar_chart(state_yield)
    st.caption("Shows which states tend to have higher yields.")

# all the "ratings & risk" page code goes in here
def render_ratings_risk():
  st.header("🚨 Ratings & Risk")

  # loading filter values
  state_list = conn.query(
    "SELECT DISTINCT state FROM issuers ORDER BY state;", ttl="10m"
  )["state"].tolist()
  
  agencies = conn.query(
    "SELECT DISTINCT agency FROM credit_ratings ORDER BY agency;", ttl="10m"
  )["agency"].tolist()
  
  outlooks = conn.query(
    "SELECT DISTINCT outlook FROM credit_ratings ORDER BY outlook;", ttl="10m"
  )["outlook"].tolist()

  # filtering UI
  c1, c2, c3 = st.columns(3)
  selected_states = c1.multiselect("State", state_list)
  selected_agencies = c2.multiselect("Rating Agency", agencies)
  selected_outlooks = c3.multiselect("Outlook", outlooks)

  # building WHERE clause
  where = []
  params = {}
  
  if selected_states:
    where.append("i.state = ANY(:states)")
    params["states"] = selected_states
  
  if selected_agencies:
    where.append("cr.agency = ANY(:agencies)")
    params["agencies"] = selected_agencies
  
  if selected_outlooks:
    where.append("cr.outlook = ANY(:outlooks)")
    params["outlooks"] = selected_outlooks

  where_clause = "WHERE " + " AND ".join(where) if where else ""

  # loading the joined rating data
  sql = f"""
    SELECT
      b.cusip, b.coupon_rate, b.duration, b.type,
      i.name AS issuer_name, i.state,
      cr.agency, cr.date AS rating_date, cr.rating, cr.outlook
    FROM credit_ratings cr
    JOIN bonds_credit_ratings bcr ON bcr.credit_id = cr.id
    JOIN bonds b ON b.id = bcr.bond_id
    LEFT JOIN bonds_issuers bi ON bi.bond_id = b.id
    LEFT JOIN issuers i ON i.id = bi.issuer_id
    {where_clause}
    ORDER BY cr.date DESC;
  """
  
  df = conn.query(sql, params=params or None, ttl="2m")

  if df.empty:
    st.warning("No rating data available for the selected filters.")
    return

  # parsing date col directly
  df["rating_date"] = pd.to_datetime(df["rating_date"])
  
  st.subheader("Summary Metrics")
  cA, cB, cC = st.columns(3)
  cA.metric("Total Rated Bonds", len(df))
  cB.metric("Avg Coupon", f"{df['coupon_rate'].mean():.2f}%")
  cC.metric("Unique Rating Grades", df["rating"].nunique())
  st.divider()

  # rating distribution
  st.subheader("Distribution of Credit Ratings")
  
  chart = (
    alt.Chart(df)
    .mark_bar()
    .encode(
      x=alt.X("rating:N", sort="descending"),
      y=alt.Y("count()", title="Number of Bonds"),
      tooltip=["rating", "count()"],
      color=alt.Color("rating:N", legend=None),
    )
    .properties(height=300)
  )
  st.altair_chart(chart, use_container_width=True)
  st.divider()

  # rating vs yield
  st.subheader("Yield (Coupon) vs Credit Rating")
  
  scatter = (
    alt.Chart(df)
    .mark_circle(size=80)
    .encode(
      x=alt.X("rating:N", sort="descending"),
      y=alt.Y("coupon_rate:Q", title="Coupon (%)"),
      tooltip=["cusip", "rating", "coupon_rate"],
      color=alt.Color("state:N", title="State"),
    )
    .interactive()
    .properties(height=300)
  )
  
  st.altair_chart(scatter, use_container_width=True)
  st.divider()

  # avg yield by credit rating
  st.subheader("Average Yield by Credit Rating")
  
  bar = (
      alt.Chart(df)
      .mark_bar()
      .encode(
          x=alt.X("rating:N", sort="descending", title="Credit Rating"),
          y=alt.Y("mean(coupon_rate):Q", title="Avg Coupon (%)"),
          tooltip=[
              alt.Tooltip("rating:N", title="Rating"),
              alt.Tooltip("mean(coupon_rate):Q", title="Avg Coupon", format=".2f")
          ],
          color=alt.Color("rating:N", legend=None)
      )
      .properties(height=300)
  )
  
  st.altair_chart(bar, use_container_width=True)
  st.divider()

  # recent rating changes
  st.subheader("Latest Rating Updates")
  
  recent_updates = (
    df.sort_values("rating_date", ascending=False)
    .groupby("cusip")
    .head(1)  # latest rating per bond
    .head(10) # show 10 newest
    .sort_values("rating_date", ascending=False)
  )
  
  st.table(
    recent_updates[["rating_date", "cusip", "issuer_name", "rating", "outlook"]]
  )
  st.divider()

  # highest-risk (lowest rated) bonds
  st.subheader("Highest-Risk Bonds")
  
  # Sort ratings low to high
  RATING_ORDER = [ # i think this is right?
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
    "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-",
    "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC",
    "C", "D"
  ]
  
  df["rating_sort"] = df["rating"].apply(
    lambda r: RATING_ORDER.index(r) if r in RATING_ORDER else 999
  )
  risky = df.sort_values("rating_sort", ascending=False).head(10)
  st.table(
    risky[["rating", "outlook", "cusip", "issuer_name", "coupon_rate"]]
  )

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
  bond_sql = """
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

  # display bond metadata
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

  st.divider()

  # trades
  trades_sql = """
    SELECT t.date, t.price, t.yield, t.quantity
    FROM trades t
    JOIN bonds_trades bt ON bt.trade_id = t.id
    JOIN bonds b ON b.id = bt.bond_id
    WHERE b.cusip = :cusip
    ORDER BY t.date;
  """
  trades = conn.query(trades_sql, params = {"cusip": selected_cusip}, ttl = "5m")
  
  if trades.empty:
    st.warning("No trades found for this bond")
    return

  # funky visualizations
  st.subheader("Price over Time")
  st.line_chart(trades.set_index("date")["price"])

  st.subheader("Yield over Time")
  st.line_chart(trades.set_index("date")["yield"])

  st.divider()

  # metrics
  last_row = trades.iloc[-1]
  col1, col2, col3 = st.columns(3)
  col1.metric("Latest Price", f"${last_row['price']:.2f}")
  col2.metric("Latest Yield", f"{last_row['yield']:.2f}%")
  col3.metric("Last Trade Date", str(last_row['date']))

with bonds_tab:
  render_bond_explorer()

with risk_tab:
  render_ratings_risk()

with market_tab:
  render_market_overview()
