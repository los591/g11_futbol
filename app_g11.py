import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import plotly.graph_objects as go

# --- DB Connection ---
conn = psycopg2.connect(
    host=st.secrets["DB_HOST"],
    port=st.secrets["DB_PORT"],
    dbname=st.secrets["DB_NAME"],
    user=st.secrets["DB_USER"],
    password=st.secrets["DB_PASSWORD"]
)


st.title("🌍 Where Soccer Players from a Country Play & Their Performance")

# --- User Input ---
country = st.text_input("Enter a country", "Ecuador")
year = st.number_input("Select Year", min_value=2000, max_value=2026, value=2024)

if country:
    query = """
    SELECT 
        p.player_id AS player_id,
        p.player_name AS player_name,
        p.nationality AS nationality,
        p.photo AS player_photo,
        
        fpp.fixture_id AS fixture_id,
        fpp.fixture_date AS fixture_date,
        fpp.team AS team_name,
        fpp.team_id AS team_id,
        fpp.minutes_played AS minutes_played,
        fpp.goals_total AS goals_total,
        fpp.goals_assisted AS goals_assisted,
        fpp.cards_yellow AS cards_yellow,
        fpp.cards_red AS cards_red,
        fpp.player_rating AS player_rating,
        
        f.league_id AS league_id,
        f.home_team_name AS home_team_name,
        f.away_team_name AS away_team_name,
        l.name AS league_name,
        l.country_name AS country_name
    FROM players p
    JOIN fixtures_players_performance fpp ON p.player_id = fpp.player_id
    JOIN fixtures f ON fpp.fixture_id = f.fixture_id
    JOIN leagues l ON f.league_id = l.id
    WHERE p.nationality = %s
    """

    df = pd.read_sql(query, conn, params=(country,))

    if df.empty:
        st.warning(f"No players from {country} found.")
    else:
        df['fixture_date'] = pd.to_datetime(df['fixture_date'])
        df_year = df[df['fixture_date'].dt.year == year]

        if df_year.empty:
            st.warning(f"No matches found for {country} players in {year}.")
        else:
            # --- Summary ---
            player_counts = df_year.groupby('country_name')['player_id'].nunique().reset_index(name='num_players')
            summary_stats = df_year.groupby('country_name').agg(
                goals_total=('goals_total','sum'),
                goals_assisted=('goals_assisted','sum'),
                minutes_played=('minutes_played','sum')
            ).reset_index()
            summary = player_counts.merge(summary_stats, on='country_name', how='left').fillna(0)
            st.subheader(f"Summary of {country} players in {year} by country they play in")
            st.dataframe(summary, use_container_width=True)

            # --- Country selection ---
            selected_country = st.selectbox("Select a country to see players:", summary['country_name'].sort_values().tolist())
            if selected_country:
                filtered_df = df_year[df_year['country_name'] == selected_country]
                if not filtered_df.empty:
                    st.subheader(f"Players from {country} playing in {selected_country} in {year}")
                    players = filtered_df[['player_id','player_name']].drop_duplicates().sort_values('player_name')
                    player_lookup = dict(zip(players['player_name'], players['player_id']))
                    selected_player_name = st.selectbox("Search & select a player:", players['player_name'].tolist())
                    selected_player_id = player_lookup[selected_player_name]

                    player_df = filtered_df[filtered_df['player_id']==selected_player_id].sort_values('fixture_date').copy()
                    numeric_cols = ['minutes_played','goals_total','goals_assisted','cards_yellow','cards_red','player_rating']
                    player_df[numeric_cols] = player_df[numeric_cols].fillna(0)

                    # Opponent / Home-Away
                    player_df['opponent'] = player_df.apply(lambda r: r['away_team_name'] if r['team_name']==r['home_team_name'] else r['home_team_name'], axis=1)
                    player_df['home_away'] = player_df.apply(lambda r: 'Home' if r['team_name']==r['home_team_name'] else 'Away', axis=1)

                    # Aggregates
                    total_minutes = int(player_df['minutes_played'].sum())
                    total_goals = int(player_df['goals_total'].sum())
                    total_assists = int(player_df['goals_assisted'].sum())
                    avg_rating = round(player_df['player_rating'].mean(), 2)
                    matches_played = player_df.shape[0]

                    # --- Header ---
                    col1, col2, col3 = st.columns([1,3,4])
                    with col1: st.image(player_df.iloc[0]['player_photo'], width=120)
                    with col2:
                        st.markdown(f"### {selected_player_name}\n**Season:** {year}  \n**Matches:** {matches_played}  \n**Teams:** {', '.join(player_df['team_name'].unique())}")
                    with col3:
                        st.metric("⭐ Avg Rating", avg_rating)
                        st.metric("⚽ Goals", total_goals)
                        st.metric("⏱ Minutes", total_minutes)

                    # --- Match table ---
                    match_table = player_df[['fixture_date','team_name','opponent','home_away','league_name','minutes_played','goals_total','goals_assisted','cards_yellow','cards_red','player_rating']].sort_values('fixture_date', ascending=False)
                    match_table['fixture_date'] = match_table['fixture_date'].dt.strftime('%Y-%m-%d')
                    st.subheader("📋 Match-by-match performance")
                    st.dataframe(match_table, use_container_width=True)

                    # --- Season timeline ---
                    viz_df = player_df.copy()
                    viz_df['goal_involvements'] = viz_df['goals_total'] + viz_df['goals_assisted']
                    viz_df['marker_size'] = viz_df['goal_involvements'].clip(lower=0)*8+6

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=viz_df['fixture_date'],
                        y=viz_df['minutes_played'],
                        mode='markers',
                        marker=dict(size=viz_df['marker_size'], color=viz_df['player_rating'], colorscale='RdYlGn', showscale=True, colorbar=dict(title="Rating")),
                        text=[f"Team: {t}<br>League: {l}<br>Goals: {g}<br>Assists: {a}<br>Yellow: {y}<br>Red: {r}<br>Rating: {r2}" for t,l,g,a,y,r,r2 in zip(viz_df['team_name'], viz_df['league_name'], viz_df['goals_total'], viz_df['goals_assisted'], viz_df['cards_yellow'], viz_df['cards_red'], viz_df['player_rating'])],
                        hoverinfo='text', name="Match"
                    ))

                    # Emoji overlay
                    goals_df = viz_df[viz_df['goals_total']>0]
                    goals_text = ['⚽'*int(g) for g in goals_df['goals_total']]
                    fig.add_trace(go.Scatter(x=goals_df['fixture_date'], y=goals_df['minutes_played'], mode='text', text=goals_text, textposition='top center', textfont=dict(size=20), hoverinfo='skip', showlegend=False))
                    
                    max_y = max(viz_df['minutes_played'].max()+15, 95)
                    fig.update_layout(title="Minutes played per match (size = goal involvement, color = rating)", xaxis_title="Match Date", yaxis_title="Minutes Played", yaxis=dict(range=[0,max_y]), height=520)
                    st.plotly_chart(fig, use_container_width=True)
