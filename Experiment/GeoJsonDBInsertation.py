import geojson
import psycopg2
from psycopg2 import sql

# Database connection parameters
db_config = {
    "dbname": "routedb",  # Your database name
    "user": "postgres",  # Your PostgreSQL username
    "password": "admin",  # Your PostgreSQL password
    "host": "localhost",  # Your database host
    "port": "5432"  # Your database port
}

# Function to convert GeoJSON geometry to WKT
def geojson_to_wkt(geometry):
    if geometry['type'] == 'Point':
        coords = geometry['coordinates']
        return f"POINT({coords[0]} {coords[1]})"
    elif geometry['type'] == 'LineString':
        coords = geometry['coordinates']
        wkt_coords = ", ".join([f"{lon} {lat}" for lon, lat in coords])
        return f"LINESTRING({wkt_coords})"
    elif geometry['type'] == 'Polygon':
        rings = geometry['coordinates']
        wkt_rings = []
        for ring in rings:
            wkt_coords = ", ".join([f"{lon} {lat}" for lon, lat in ring])
            wkt_rings.append(f"({wkt_coords})")
        return f"POLYGON({', '.join(wkt_rings)})"
    else:
        raise ValueError(f"Unsupported geometry type: {geometry['type']}")

# Function to insert GeoJSON data into the database
def insert_geojson_to_db(geojson_data):
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()

        # Create the table if it doesn't exist
        create_table_query = """
        CREATE TABLE IF NOT EXISTS routes (
            id SERIAL PRIMARY KEY,
            properties JSONB,
            geometry GEOMETRY(Geometry, 4326)
        );
        """
        cursor.execute(create_table_query)
        conn.commit()
        print("Table created or already exists.")

        # Insert GeoJSON features into the database
        for feature in geojson_data['features']:
            properties = feature.get('properties', {})
            geometry = feature['geometry']

            try:
                # Convert geometry to WKT
                wkt = geojson_to_wkt(geometry)

                # Insert the feature into the database
                insert_query = sql.SQL("""
                INSERT INTO routes (properties, geometry)
                VALUES (%s, ST_GeomFromText(%s, 4326));
                """)
                cursor.execute(insert_query, (geojson.dumps(properties), wkt))

            except ValueError as e:
                print(f"Skipping feature due to error: {e}")

        conn.commit()
        print("GeoJSON data inserted into the database.")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        # Close the database connection
        if conn:
            cursor.close()
            conn.close()
            print("Database connection closed.")

# Load GeoJSON file
with open("map.geojson", "r", encoding="utf-8") as f:
    geojson_data = geojson.load(f)

# Insert GeoJSON data into the database
insert_geojson_to_db(geojson_data)