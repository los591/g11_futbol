import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.graph_objects as go

# --------------------------------------------------
# Supabase client
# --------------------------------------------------
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"]
)

st.title("🌍 Where Soccer Players from a Country Play & Their Performance")

# --------------------------------------------------
# User input
# --------------------------------------------------
country = st.text_input("Enter a country", "Ecuador")
year = st.number_input("Select Year", min_value=2000, max_value=2026, value=2024)

# --------------------------------------------------
# Helper: fetch data from Supabase
# --------------------------------------------------
@st.cache_data(ttl=3600)
@st.cache_data(ttl=3600)
def fetch_country_data(country: str):

    # 1️⃣ Players
    players = (
        supabase
        .table("players_subset")
        .select("player_id, player_name, nationality, photo")
        .eq("nationality", country)
        .execute()
    ).data

    if not players:
        return pd.DataFrame()

    players_df = pd.DataFrame(players)

    # 2️⃣ Player performances
    player_ids = players_df["player_id"].tolist()

    fpp = (
        supabase
        .table("fixtures_players_performance_subset")
        .select("""
            fixture_id,
            fixture_date,
            team,
            team_id,
            minutes_played,
            goals_total,
            goals_assisted,
            cards_yellow,
            cards_red,
            player_rating,
            player_id
        """)
        .in_("player_id", player_ids)
        .execute()
    ).data

    if not fpp:
        return pd.DataFrame()

    fpp_df = pd.DataFrame(fpp)

    # 3️⃣ Fixtures
    fixture_ids = fpp_df["fixture_id"].unique().tolist()

    fixtures = (
        supabase
        .table("fixtures_subset")
        .select("""
            fixture_id,
            home_team_name,
            away_team_name,
            league_id
        """)
        .in_("fixture_id", fixture_ids)
        .execute()
    ).data

    fixtures_df = pd.DataFrame(fixtures)

    # 4️⃣ Leagues
    leagues = (
        supabase
        .table("leagues_subset")
        .select("id, name, country_name")
        .execute()
    ).data

    leagues_df = pd.DataFrame(leagues)

    # 5️⃣ Merge everything locally
    df = (
        fpp_df
        .merge(players_df, on="player_id", how="left")
        .merge(fixtures_df, on="fixture_id", how="left")
        .merge(leagues_df, left_on="league_id", right_on="id", how="left")
    )

    df = df.rename(columns={
        "team": "team_name",
        "photo": "player_photo",
        "name": "league_name"
    })

    return df


# --------------------------------------------------
# Main logic
# --------------------------------------------------
if country:
    df = fetch_country_data(country)

    if df.empty:
        st.warning(f"No players from {country} found.")
        st.stop()

    df["fixture_date"] = pd.to_datetime(df["fixture_date"], errors="coerce")
    df_year = df[df["fixture_date"].dt.year == year]

    if df_year.empty:
        st.warning(f"No matches found for {country} players in {year}.")
        st.stop()

    # --------------------------------------------------
    # Summary table
    # --------------------------------------------------
    player_counts = (
        df_year.groupby("country_name")["player_id"]
        .nunique()
        .reset_index(name="num_players")
    )

    summary_stats = (
        df_year.groupby("country_name")
        .agg(
            goals_total=("goals_total", "sum"),
            goals_assisted=("goals_assisted", "sum"),
            minutes_played=("minutes_played", "sum")
        )
        .reset_index()
    )

    summary = player_counts.merge(summary_stats, on="country_name", how="left").fillna(0)

    st.subheader(f"Summary of {country} players in {year}")
    st.dataframe(summary, use_container_width=True)

    # --------------------------------------------------
    # Country selector
    # --------------------------------------------------
    selected_country = st.selectbox(
        "Select a country to see players:",
        sorted(summary["country_name"].unique())
    )

    filtered_df = df_year[df_year["country_name"] == selected_country]

    players = (
        filtered_df[["player_id", "player_name"]]
        .drop_duplicates()
        .sort_values("player_name")
    )

    selected_player_name = st.selectbox(
        "Search & select a player:",
        players["player_name"].tolist()
    )

    selected_player_id = players.loc[
        players["player_name"] == selected_player_name, "player_id"
    ].iloc[0]

    player_df = (
        filtered_df[filtered_df["player_id"] == selected_player_id]
        .sort_values("fixture_date")
        .copy()
    )

    # --------------------------------------------------
    # Clean numeric columns
    # --------------------------------------------------
    numeric_cols = [
        "minutes_played",
        "goals_total",
        "goals_assisted",
        "cards_yellow",
        "cards_red",
        "player_rating"
    ]
    player_df[numeric_cols] = player_df[numeric_cols].fillna(0)

    # Opponent + home/away
    player_df["opponent"] = player_df.apply(
        lambda r: r["away_team_name"]
        if r["team_name"] == r["home_team_name"]
        else r["home_team_name"],
        axis=1
    )

    player_df["home_away"] = player_df.apply(
        lambda r: "Home"
        if r["team_name"] == r["home_team_name"]
        else "Away",
        axis=1
    )

    # --------------------------------------------------
    # Player header
    # --------------------------------------------------
    total_minutes = int(player_df["minutes_played"].sum())
    total_goals = int(player_df["goals_total"].sum())
    total_assists = int(player_df["goals_assisted"].sum())
    avg_rating = round(player_df["player_rating"].mean(), 2)

    col1, col2, col3 = st.columns([1, 3, 4])

    with col1:
        st.image(player_df.iloc[0]["player_photo"], width=120)

    with col2:
        st.markdown(
            f"""
            ### {selected_player_name}
            **Season:** {year}  
            **Matches:** {len(player_df)}  
            **Teams:** {', '.join(player_df['team_name'].unique())}
            """
        )

    with col3:
        st.metric("⭐ Avg Rating", avg_rating)
        st.metric("⚽ Goals", total_goals)
        st.metric("⏱ Minutes", total_minutes)

    # --------------------------------------------------
    # Timeline visualization
    # --------------------------------------------------
    st.subheader("📈 Season timeline")

    player_df["goal_involvements"] = (
        player_df["goals_total"] + player_df["goals_assisted"]
    )
    player_df["marker_size"] = player_df["goal_involvements"] * 8 + 6

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=player_df["fixture_date"],
            y=player_df["minutes_played"],
            mode="markers",
            marker=dict(
                size=player_df["marker_size"],
                color=player_df["player_rating"],
                colorscale="RdYlGn",
                showscale=True
            ),
            hovertext=player_df["opponent"],
            hoverinfo="text"
        )
    )

    st.plotly_chart(fig, use_container_width=True)
