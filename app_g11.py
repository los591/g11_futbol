import streamlit as st
import pandas as pd


def fetch_sorted_results(data, position: str, metric:str):
    position_df = data[data['position'] == position]
    sorted_df = position_df.sort_values(by=metric, ascending=False)
    final_df = sorted_df[['name', 'team', metric]]
    return final_df


def get_scores():
    ''' Display results'''
    ### Translate Position
    if position == 'Goalkeeper':
        position_app = 'G'
    if position == 'Defender':
        position_app = 'D'
    if position == 'Midfielder':
        position_app = 'M'
    if position == 'Forward':
        position_app = 'F'
    ### Translate Metric
    if metric == 'Goals Scored':
        metric_app = 'goals_scored'
    if metric == 'Assists':
        metric_app = 'goals_assisted'
    if metric == 'Yellow Cards':
        metric_app = 'yellow'
    if metric == 'Red Cards':
        metric_app = 'red'
    if metric == 'Minutes Played':
        metric_app = 'minutes'
    
    user_data = fetch_sorted_results(app_data, position_app, metric_app)
    return user_data


left_co, cent_co,last_co = st.columns(3)
with last_co:
    st.image('https://upload.wikimedia.org/wikipedia/en/thumb/f/f2/Premier_League_Logo.svg/420px-Premier_League_Logo.svg.png')


#image = 'https://upload.wikimedia.org/wikipedia/en/thumb/f/f2/Premier_League_Logo.svg/420px-Premier_League_Logo.svg.png'
### Initial layout
#st.image(image, width=200)


st.header('English Premier League Player Performance')

position = st.selectbox('Select Position', ['Goalkeeper', 'Defender', 'Midfielder', 'Forward'])
metric = st.selectbox('Select Metric', ['Goals Scored', 'Assists', 'Yellow Cards', 'Red Cards', 'Minutes Played'])

button = st.button('Fetch Results')




# Data Functionality

data = pd.read_excel('ynwa_one_more.xlsx')
app_data = data[['name', 'team', 'minutes', 'goals_assisted', 'yellow', 'red', 'goals_scored', 'position']]
app_data.fillna(0, inplace=True)
#app_data_final = app_data.to_dict("records")
# Convert relevant columns to integers
numeric_cols = ['minutes', 'goals_assisted', 'yellow', 'red', 'goals_scored']
for col in numeric_cols:
    app_data[col] = pd.to_numeric(app_data[col], errors='coerce').fillna(0)


if button:
    data = get_scores()
    st.dataframe(data)
    #st.line_chart(data.minutesPlayed)
