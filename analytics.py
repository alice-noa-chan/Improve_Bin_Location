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
IS_ALLOW_SAME_LAT_LONG = 0  # 0 to disallow same lat-long, 1 to allow

# Function to validate and filter data based on latitude and longitude validity
def validate_and_filter_data(df):
    """ Validate and filter input data for invalid or out-of-range latitude and longitude values. """
    df = df.dropna(subset=['latitude', 'longitude'])  # Remove rows where lat or long are NaN
    df = df[(df['latitude'].between(-90, 90)) & (df['longitude'].between(-180, 180))]  # Validate range
    return df

# Importing and cleaning data
recyclebin_df = pd.read_csv(recyclebin_file)
recyclebin_df = validate_and_filter_data(recyclebin_df)

bus_df = pd.read_csv(bus_file)
bus_df = validate_and_filter_data(bus_df)

subway_df = pd.read_csv(subway_file)
subway_df = validate_and_filter_data(subway_df)

locations_df = pd.concat([bus_df, subway_df]).drop_duplicates().reset_index(drop=True)

# Exclude data that is too close to an existing dataset
def filter_close_points(df, min_distance):
    """ Filter out points that are too close to each other based on a minimum distance criterion. """
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

# Initialize the Nominatim Geocoder for location verification
geolocator = Nominatim(user_agent="geoapiExercises")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
geolocator.headers = {'Accept-Language': 'ko'}

def is_in_target_city(latitude, longitude, target_city):
    """ Check if a given latitude and longitude are within a specified target city. """
    location = geolocator.reverse((latitude, longitude), exactly_one=True)
    return target_city in location.address if location else False

# Filtering only the locations in Daejeon Metropolitan City
filtered_locations = []
for lat, lon in tqdm(new_locations, desc="Filtering locations in Daejeon Metropolitan City"):
    time.sleep(1)  # Ensure delay between API requests to avoid throttling
    if is_in_target_city(lat, lon, 'Daejeon Metropolitan City'):
        filtered_locations.append((lat, lon))

# Minimum distance filtering
final_locations = []
for lat, lon in tqdm(filtered_locations, desc="Applying minimum distance filter"):
    if IS_ALLOW_SAME_LAT_LONG == 0:
        # Disallow exact duplicates if configured
        if any((lat == final_lat and lon == final_lon) for final_lat, final_lon in final_locations):
            continue
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
