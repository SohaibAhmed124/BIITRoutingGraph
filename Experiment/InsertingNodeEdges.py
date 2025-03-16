import json
import psycopg2
from shapely.geometry import LineString, Point
from geopy.distance import geodesic

# Database Configuration
DB_CONFIG = {
    "dbname": "routedb",
    "user": "postgres",
    "password": "admin",
    "host": "localhost",
    "port": "5432",
}

# Load GeoJSON

with open('map.geojson', "r", encoding="utf-8") as file:
    geojson_data = json.load(file)

# Connect to PostgreSQL
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# # Create Tables
# cur.execute("""
#     CREATE TABLE IF NOT EXISTS nodes (
#         id SERIAL PRIMARY KEY,
#         lat NUMERIC NOT NULL,
#         lon NUMERIC NOT NULL
#     );
# """)

# cur.execute("""
#     CREATE TABLE IF NOT EXISTS edges (
#         id SERIAL PRIMARY KEY,
#         source INT REFERENCES nodes(id),
#         target INT REFERENCES nodes(id),
#         length NUMERIC NOT NULL,
#         cost NUMERIC NOT NULL,
#         reverse_cost NUMERIC,
#         oneway BOOLEAN DEFAULT FALSE,
#         highway TEXT
#     );
# """)
# conn.commit()

# Extract Nodes & Edges
nodes = {}
edges = []
node_counter = 1

def get_or_create_node(lat, lon):
    """Store unique nodes and return their ID."""
    global node_counter
    coord = (lat, lon)
    if coord not in nodes:
        nodes[coord] = node_counter
        node_counter += 1
    return nodes[coord]

for feature in geojson_data["features"]:
    if feature["geometry"]["type"] == "LineString":
        coords = feature["geometry"]["coordinates"]
        properties = feature["properties"]

        highway = properties.get("highway", None)
        oneway = properties.get("oneway", "no") == "yes"

        for i in range(len(coords) - 1):
            lat1, lon1 = coords[i][1], coords[i][0]
            lat2, lon2 = coords[i + 1][1], coords[i + 1][0]

            source = get_or_create_node(lat1, lon1)
            target = get_or_create_node(lat2, lon2)

            length = geodesic((lat1, lon1), (lat2, lon2)).meters
            cost = length  # Distance-based cost

            edges.append((source, target, length, cost, None if oneway else cost, oneway, highway))

# Insert Nodes into PostgreSQL
for (lat, lon), node_id in nodes.items():
    cur.execute("INSERT INTO nodes (id, lat, lon) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING;", (node_id, lat, lon))

# Insert Edges into PostgreSQL
for edge in edges:
    cur.execute("""
        INSERT INTO edges (source, target, length, cost, reverse_cost, oneway, highway)
        VALUES (%s, %s, %s, %s, %s, %s, %s);
    """, edge)

# Commit & Close
conn.commit()
cur.close()
conn.close()
print("Data successfully inserted into PostgreSQL!")
