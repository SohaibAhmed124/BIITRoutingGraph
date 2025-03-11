from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import psycopg2
from psycopg2 import sql
import geojson
import networkx as nx
from scipy.spatial import KDTree
from pydantic import BaseModel
from pathlib import Path
from typing import List, Dict, Any

# Database connection parameters
db_config = {
    "dbname": "routedb",  # Your database name
    "user": "postgres",  # Your PostgreSQL username
    "password": "admin",  # Your PostgreSQL password
    "host": "localhost",  # Your database host
    "port": "5432"  # Your database port
}

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (for development only)
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Mount the static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Pydantic models for request/response validation
class GeoJSONFeature(BaseModel):
    type: str
    properties: Dict[str, Any]
    geometry: Dict[str, Any]

class GeoJSONData(BaseModel):
    type: str
    features: List[GeoJSONFeature]

class ShortestPathRequest(BaseModel):
    source: List[float]  # [longitude, latitude]
    target: List[float]  # [longitude, latitude]

# Load GeoJSON file
def load_geojson():
    geojson_path = Path("data/map.geojson")
    with open(geojson_path, "r", encoding="utf-8") as f:
        return geojson.load(f)
    
# Function to convert GeoJSON geometry to WKT
def geojson_to_wkt(geometry):
    geom_type = geometry['type']
    coordinates = geometry['coordinates']

    if geom_type == 'Point':
        return f"POINT ({coordinates[0]} {coordinates[1]})"
    elif geom_type == 'LineString':
        wkt_coords = ", ".join([f"{lon} {lat}" for lon, lat in coordinates])
        return f"LINESTRING ({wkt_coords})"
    elif geom_type == 'Polygon':
        rings = coordinates
        wkt_rings = []
        for ring in rings:
            wkt_coords = ", ".join([f"{lon} {lat}" for lon, lat in ring])
            wkt_rings.append(f"({wkt_coords})")
        return f"POLYGON ({', '.join(wkt_rings)})"
    else:
        raise ValueError(f"Unsupported geometry type: {geom_type}")

# Function to insert GeoJSON data into the database
def insert_geojson_to_db(geojson_data):
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()

        # Create the table if it doesn't exist
        create_table_query = """
        CREATE TABLE IF NOT EXISTS geojson_features (
            id SERIAL PRIMARY KEY,
            properties JSONB,
            geometry GEOMETRY(Geometry, 4326)
        );
        """
        cursor.execute(create_table_query)
        conn.commit()

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
        return {"message": "GeoJSON data inserted into the database."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    finally:
        if conn:
            cursor.close()
            conn.close()

# Function to fetch GeoJSON data from the database
def fetch_geojson_from_db():
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()

        # Query to fetch properties and geometry from the table
        query = """
        SELECT properties, ST_AsGeoJSON(geometry) AS geometry
        FROM routes;
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        # Convert the fetched data into a GeoJSON-like structure
        features = []
        for row in rows:
            properties, geometry_geojson = row
            geometry = geojson.loads(geometry_geojson)
            feature = {
                "type": "Feature",
                "properties": properties,
                "geometry": geometry
            }
            features.append(feature)

        geojson_data = {
            "type": "FeatureCollection",
            "features": features
        }

        return geojson_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    finally:
        if conn:
            cursor.close()
            conn.close()

# Function to build a graph from GeoJSON data
def build_graph_from_geojson(geojson_data):
    G = nx.Graph()

    for feature in geojson_data['features']:
        geometry = feature['geometry']
        properties = feature.get('properties', {})

        if geometry['type'] == 'LineString':
            coords = geometry['coordinates']
            for i in range(len(coords) - 1):
                source = tuple(coords[i])
                target = tuple(coords[i + 1])
                cost = properties.get('cost', 1)  # Default cost if not provided
                G.add_node(source, pos=source)
                G.add_node(target, pos=target)
                G.add_edge(source, target, weight=cost)

        elif geometry['type'] == 'Polygon':
            # Handle Polygon geometry
            # Extract the exterior ring of the polygon (ignoring holes for simplicity)
            exterior_ring = geometry['coordinates'][0]
            for i in range(len(exterior_ring) - 1):
                source = tuple(exterior_ring[i])
                target = tuple(exterior_ring[i + 1])
                cost = properties.get('cost', 1)  # Default cost if not provided
                
                # Add nodes with coordinates as IDs
                G.add_node(source, pos=source)
                G.add_node(target, pos=target)
                
                # Add edge
                G.add_edge(source, target, weight=cost)

        elif geometry['type'] == 'Point':
            # Handle Point geometry (optional, if needed)
            coords = geometry['coordinates']
            point = tuple(coords)
            G.add_node(point, pos=point)

    return G

# Function to find the nearest node using a K-D Tree
def find_nearest_node(kdtree, nodes, target_coords):
    distance, index = kdtree.query(target_coords)
    return nodes[index], distance

# API Endpoints
@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/insert-geojson/")
async def insert_geojson(geojson_data: GeoJSONData):
    return insert_geojson_to_db(geojson_data.dict())

@app.get("/fetch-geojson/")
async def fetch_geojson():
    return fetch_geojson_from_db()

@app.post("/shortest-path/")
async def shortest_path(request: ShortestPathRequest):
    geojson_data = fetch_geojson_from_db()
    G = build_graph_from_geojson(geojson_data)

    # Build K-D Tree from graph nodes
    nodes = list(G.nodes())
    kdtree = KDTree(nodes)

    # Find the nearest nodes
    source_node, _ = find_nearest_node(kdtree, nodes, request.source)
    target_node, _ = find_nearest_node(kdtree, nodes, request.target)

    # Use Dijkstra's algorithm to find the shortest path
    try:
        shortest_path = nx.dijkstra_path(G, source=source_node, target=target_node, weight='weight')
        total_cost = sum(G[shortest_path[i]][shortest_path[i + 1]]['weight'] for i in range(len(shortest_path)
                                                                                             - 1))
        path_coords = [[lon, lat] for lat, lon in shortest_path]
        return {
            "shortest_path": path_coords,
            "total_cost": total_cost
        }
    except nx.NetworkXNoPath:
        raise HTTPException(status_code=404, detail="No path exists between the source and target nodes.")

# Run the FastAPI server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=2000)