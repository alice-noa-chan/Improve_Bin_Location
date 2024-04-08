# Required Library Import
import pandas as pd
from sklearn.cluster import KMeans
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.distance import geodesic
from tqdm import tqdm
import time
import numpy as np

# File path and other settings variables
recyclebin_file = 'recyclebin.csv'
bus_file = 'bus.csv'
subway_file = 'subway.csv'
output_file = 'improve_recyclebin.csv'
n_clusters = 100  # The number of new bins
min_distance_m = 50  # Minimum distance (meters) for final selection
min_input_distance_m = 100  # Minimum allowable interval between data in an existing dataset

# Importing and merging data
recyclebin_df = pd.read_csv(recyclebin_file)
bus_df = pd.read_csv(bus_file)
subway_df = pd.read_csv(subway_file)
locations_df = pd.concat([bus_df, subway_df]).drop_duplicates().reset_index(drop=True)

# Exclude data that is too close to an existing dataset
def filter_close_points(df, min_distance):
    result = []
    for _, row in tqdm(df.iterrows(), total=df.shape[0], desc="Filtering close points"):
        point = (row['latitude'], row['longitude'])
        if all(geodesic(point, (r['latitude'], r['longitude'])).meters >= min_distance for r in result):
            result.append(row)
    return pd.DataFrame(result)

filtered_locations_df = filter_close_points(locations_df, min_input_distance_m)

# Clustering
kmeans = KMeans(n_clusters=n_clusters, random_state=0).fit(filtered_locations_df[['latitude', 'longitude']])
new_locations = kmeans.cluster_centers_

# Initialization and setting of the Nominatim Geocoder for location confirmation in Daejeon Metropolitan City
geolocator = Nominatim(user_agent="geoapiExercises")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
geolocator.headers = {'Accept-Language': 'ko'}

def is_in_target_city(latitude, longitude, target_city):
    location = geolocator.reverse((latitude, longitude), exactly_one=True)
    return target_city in location.address if location else False

# Filtering only the location of trash cans in Daejeon Metropolitan City
filtered_locations = []
for lat, lon in tqdm(new_locations, desc="Filtering locations in Daejeon Metropolitan City"):
    time.sleep(1)  # Add delay between Nominatim requests
    if is_in_target_city(lat, lon, 'Daejeon Metropolitan City'):
        filtered_locations.append((lat, lon))

# Minimum distance filtering
final_locations = []
for lat, lon in tqdm(filtered_locations, desc="Applying minimum distance filter"):
    too_close = False
    for final_lat, final_lon in final_locations:
        distance = geodesic((lat, lon), (final_lat, final_lon)).meters
        if distance < min_distance_m:
            too_close = True
            break
    if not too_close:
        final_locations.append([lat, lon])

# Create and store resulting data frames
final_df = pd.DataFrame(final_locations, columns=['latitude', 'longitude'])
final_df.to_csv(output_file, index=False)
