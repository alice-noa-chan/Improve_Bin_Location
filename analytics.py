# Required Library Imports
import pandas as pd
from sklearn.cluster import KMeans
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy.extra.rate_limiter import RateLimiter
import numpy as np
from scipy.spatial import cKDTree
import asyncio
import aiohttp

# File path and other settings variables
recyclebin_file = 'recyclebin.csv'
bus_file = 'bus.csv'
subway_file = 'subway.csv'
output_file = 'improve_recyclebin.csv'
n_clusters = 100  # Number of new bins
min_distance_m = 50  # Minimum distance (meters) for final selection
min_input_distance_m = 100  # Minimum allowable interval between data in an existing dataset
IS_ALLOW_SAME_LAT_LONG = 0  # 0 to disallow same lat-long, 1 to allow
PASS_NOMINATIM_VALID_CHECK = 0  # 0 to use Nominatim validation, 1 to skip it

# Function to validate and filter data based on latitude and longitude validity
def validate_and_filter_data(df):
    """ Validate and filter input data for invalid or out-of-range latitude and longitude values. """
    return df.dropna(subset=['latitude', 'longitude']).query('-90 <= latitude <= 90 and -180 <= longitude <= 180')

# Importing and cleaning data
recyclebin_df = pd.read_csv(recyclebin_file)
recyclebin_df = validate_and_filter_data(recyclebin_df)

bus_df = pd.read_csv(bus_file)
bus_df = validate_and_filter_data(bus_df)

subway_df = pd.read_csv(subway_file)
subway_df = validate_and_filter_data(subway_df)

locations_df = pd.concat([bus_df, subway_df]).drop_duplicates().reset_index(drop=True)

# Function to filter out close points using a KD-Tree for faster execution
def filter_close_points(df, min_distance):
    """ Filter out points that are too close to each other using a KD-Tree. """
    coords = df[['latitude', 'longitude']].to_numpy()
    tree = cKDTree(coords)
    unique_indices = tree.query_ball_tree(tree, r=min_distance/100000, p=2, eps=0)  # Earth's radius in km approx 6371 km, hence divide by 100000
    unique_rows = set(min(indices) for indices in unique_indices if indices)
    return df.iloc[list(unique_rows)]

filtered_locations_df = filter_close_points(locations_df, min_input_distance_m)

# Clustering
kmeans = KMeans(n_clusters=n_clusters, random_state=0).fit(filtered_locations_df[['latitude', 'longitude']])
new_locations = kmeans.cluster_centers_


# Initialize the Nominatim Geocoder for location verification
geolocator = Nominatim(user_agent="geoapiExercises")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
geolocator.headers = {'Accept-Language': 'ko'}

async def is_in_target_city(session, latitude, longitude, target_city):
    """ Asynchronously check if a given latitude and longitude are within a specified target city. """
    try:
        await asyncio.sleep(1)  # Ensure 1 second delay between requests to comply with API usage policy
        async with session.get(f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}") as response:
            result = await response.json()
            return target_city in result['address']['county']
    except Exception as e:
        return False

async def filter_locations(locations, target_city):
    """ Filter locations asynchronously to find those within a specified target city. """
    async with aiohttp.ClientSession() as session:
        tasks = [is_in_target_city(session, lat, lon, target_city) for lat, lon in locations]
        results = await asyncio.gather(*tasks)
        return [loc for loc, res in zip(locations, results) if res]

if PASS_NOMINATIM_VALID_CHECK == 0:
    # Run the async filtering task if validation is not skipped
    filtered_locations = asyncio.run(filter_locations(new_locations, 'Daejeon Metropolitan City'))
else:
    # Skip validation and use all new locations
    filtered_locations = new_locations

# Minimum distance filtering
final_locations = []
for lat, lon in filtered_locations:
    if IS_ALLOW_SAME_LAT_LONG == 0:
        if any(lat == final_lat and lon == final_lon for final_lat, final_lon in final_locations):
            continue
    if not any(geodesic((lat, lon), (final_lat, final_lon)).meters < min_distance_m for final_lat, final_lon in final_locations):
        final_locations.append([lat, lon])

# Create and store resulting data frames
final_df = pd.DataFrame(final_locations, columns=['latitude', 'longitude'])
final_df.to_csv(output_file, index=False)
