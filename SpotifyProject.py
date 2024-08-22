import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import os
from dotenv import load_dotenv, dotenv_values
import requests
import sys
import json
from datetime import datetime
import re
#Connecting to Spotify API
load_dotenv()
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')


REDIRECT_URI = 'http://localhost:5000'

sp = spotipy.Spotify(
    auth_manager= SpotifyOAuth(
        client_id = CLIENT_ID,
        client_secret = CLIENT_SECRET,
        redirect_uri = REDIRECT_URI,
        scope = 'user-top-read'
    )
)

# Get the users top 50 tracks long term
top_tracks = sp.current_user_top_tracks(limit = 50, time_range = 'long_term')

track_ids = [track['id'] for track in top_tracks['items']]

audio_features = sp.audio_features(track_ids)


df = pd.DataFrame(audio_features)

df['trackName'] = [track['name'] for track in top_tracks['items']]

df = df[['trackName', 'danceability', 'energy', 'valence']]

df.set_index('trackName')
df['rank'] = range(1, len(df) + 1)

# response = requests.request("GET", "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/college%20park/2024-06-01/2024-07-02?unitGroup=metric&include=hours&key=T3PKYFUDJ9LS7YPU8HAHC6SJQ&contentType=json")
# if response.status_code!=200:
#   print('Unexpected Status code: ', response.status_code)
#   sys.exit()  


# # Parse the results as JSON
# jsonData = response.json()

# Put weather data into pandas dataframe
weatherData = pd.read_csv("college park 2024-02-24 to 2024-04-04 .csv")
weatherData['datetime'] = pd.to_datetime(weatherData['datetime'])

weatherData['datetime'] = weatherData['datetime'].astype(str)
# weatherData['date'] = weatherData['datetime'].dt.date
# weatherData['time'] = weatherData['datetime'].dt.time


def p_time(time):
  return time.strftime('%I:%M %p')


# weatherData['time'] = weatherData['time'].apply(p_time)

# put streaming history into pandas dataframe
streamingHistory =pd.read_json("StreamingHistory_music_2.json")


def fix_time(time):
  temp = list(time)
  temp[13],temp[14] = '0','0'
  time = "".join(temp)
 
# Clean up data and merge the two datasets
streamingHistory['endTime']= streamingHistory['endTime'].str.replace(r'(\d{2})$', '00:00',regex= True)


streamingHistory = streamingHistory.rename(columns= {'endTime': 'datetime'})

testData = pd.merge(streamingHistory, weatherData[['datetime','conditions','temp']], on='datetime', how = 'left')
testData = testData.dropna()

testData['time'] = testData['datetime'].str[10:]


# Method that filters the merged datasets by the provided temperature,range,conditions, and time.

def get_matching_songs(song_history, current_temp, range, condition, time):

    currentWeather = 70
    range = 5
    condition = "Partially cloudy"
    time = "17:00:00" #use datetime to get current time

    # Filters songs that were listend in higher temperatures
    matchingSongsTemp = song_history[song_history['temp'] < currentWeather + range]

    # If any rows do not match the upper bound for temerpature, None is returned.

    if len(matchingSongsTemp) == 0:
       return None
    
    # Filters out songs that were listend to in lower temperatures
    matchingSongsTemp = matchingSongsTemp[matchingSongsTemp['temp'] > currentWeather - range]

    # Filters out songs that were listened to in differnt weather conditions
    matchingSongsConditions = matchingSongsTemp[matchingSongsTemp['conditions'] == condition]

    # If the lenght of the dataset after filtering for conditions is 0 return the dataset before the filter.

    if len(matchingSongsConditions) == 0:
       return matchingSongsTemp
    
    matchingSongsTime = matchingSongsConditions[matchingSongsConditions['time'] == time]

    # If the lenght of the dataset after filtering for time is 0 return the dataset before the filter.
    if len(matchingSongsTime) == 0:
      return matchingSongsConditions

#gets dataset of songs that were listend to in simillar conditions.
matchingSongs = get_matching_songs(testData,70,5,"Partially cloudy","17:00:00" )

# Filters out any songs that were listend to for less than 60 seconds
matchingSongs = matchingSongs[matchingSongs['msPlayed'] > 60000]

# sorts the dataset by the rank of the songs in the users top tracks.
matchingSongs = pd.merge(matchingSongs,df[['trackName', 'rank']], on = 'trackName', how= 'left')
matchingSongs = matchingSongs.sort_values(by = 'rank')


# gets the artist ID
def get_artist_id(query):

  result = sp.search(q=query, type="artist", limit=1)

  # Step 5: Extract the Spotify ID of the artist from the result
  if result['artists']['items']:
    artist_id = result['artists']['items'][0]['id']
  return str(artist_id)

# gets the track ID
def get_song_id(query):

  # Step 4: Use the search function to find the song
  result = sp.search(q=query, type="track", limit=1)

  # Step 5: Extract the Spotify ID from the result
  if result['tracks']['items']:
    track_id = result['tracks']['items'][0]['id']
  return str(track_id)

#gets the genre ID
def get_genre_id(query):

  # Step 4: Use the search function to find the song
  result = sp.artist(query)

  # Step 5: Extract the Spotify ID from the result
  if len(result['genres']) > 0:
    track_id = result['genres'][0]
  else:
    track_id = ""
  return str(track_id)

#adds in song and artist ID's for each song in the dataset
matchingSongs['songID'] = matchingSongs['trackName'] + " " + matchingSongs['artistName']

matchingSongs['songID'] = matchingSongs['songID'].apply(get_song_id)

matchingSongs['artistID'] = matchingSongs['artistName'].apply(get_artist_id)

#matchingSongs['genreID'] = matchingSongs['artistID'].apply(get_genre_id)

# Gets the first 5 song an artist ID's
inputs = matchingSongs[['songID', 'artistID']].head(5)

# provides a  20 song reccomendation based on the top 5 songs for in the matchingSongs dataset.
songRecs = sp.recommendations(seed_tracks=inputs['songID'].tolist(), limit=20)
uri_list = []
for track in songRecs['tracks']:
    print(f"{track['name']} by {track['artists'][0]['name']} (Spotify URI: {track['uri']})")
    uri_list.append(track['uri'])

