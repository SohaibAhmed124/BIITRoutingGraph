from fastapi import FastAPI, HTTPException
import psycopg2
from shapely.geometry import LineString, Point, MultiPoint
from shapely.wkt import loads, dumps

app = FastAPI()

DB_CONFIG = {
    "dbname": "routedb",
    "user": "postgres",
    "password": "admin",
    "host": "localhost",
    "port": "5432",
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def get_nearest_node(lat, lon):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM nodes 
        ORDER BY ST_Distance(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) 
        LIMIT 1;
    """, (lon, lat))
    node = cur.fetchone()
    cur.close()
    conn.close()
    return node[0] if node else None

def insert_node(lat, lon):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO nodes (lat,lon,geom) 
        VALUES (%s,%s,ST_SetSRID(ST_MakePoint(%s, %s), 4326)) 
        RETURNING id;
    """, (lat, lon, lon, lat))
    node_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return node_id



def check_intersections(geom_wkt):
    """Check if the new edge intersects existing edges and return intersection points."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, ST_AsText(ST_Intersection(geom, ST_GeomFromText(%s, 4326))) AS intersection
        FROM edges
        WHERE ST_Intersects(geom, ST_GeomFromText(%s, 4326));
    """, (geom_wkt, geom_wkt))

    intersections = []
    
    for row in cur.fetchall():
        edge_id, intersection_wkt = row
        intersection_geom = loads(intersection_wkt)  # Convert WKT to Shapely geometry

        if intersection_geom.geom_type == "Point":
            intersections.append((edge_id, intersection_geom))
        elif intersection_geom.geom_type == "MultiPoint":
            for point in intersection_geom.geoms:
                intersections.append((edge_id, point))

    cur.close()
    conn.close()
    return intersections


@app.post("/insert_route/")
async def insert_route(data: dict):
    coords = data["coordinates"]
    oneway = data.get("oneway", False)
    
    geom = LineString(coords)
    geom_wkt = dumps(geom)

    intersections = check_intersections(geom_wkt)

    source = get_nearest_node(*coords[0])
    if not source:
        source = insert_node(*coords[0])

    target = get_nearest_node(*coords[-1])
    if not target:
        target = insert_node(*coords[-1])

    conn = get_db_connection()
    cur = conn.cursor()

    if intersections:
        for edge_id, point in intersections:
            new_node_id = insert_node(point.y, point.x)  # Swap x/y for lat/lon
            cur.execute("""
                UPDATE edges SET target = %s 
                WHERE id = %s AND ST_Intersects(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326));
            """, (new_node_id, edge_id, point.x, point.y))

    cur.execute("""
        INSERT INTO edges (source, target, cost, reverse_cost, oneway, highway, geom, length)
        VALUES (%s, %s, ST_Length(ST_Transform(ST_GeomFromText(%s, 4326), 3857)), 
                COALESCE(%s, 0), %s, 'custom', ST_GeomFromText(%s, 4326), 
                ST_Length(ST_Transform(ST_GeomFromText(%s, 4326), 3857)));
    """, (source, target, geom_wkt, None if oneway else 0, oneway, geom_wkt, geom_wkt))

    conn.commit()
    cur.close()
    conn.close()

    return {"message": "Route inserted successfully!"}

@app.get("/get_route/")
async def get_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float):
    start_node = get_nearest_node(start_lat, start_lon)
    end_node = get_nearest_node(end_lat, end_lon)

    if not start_node or not end_node:
        raise HTTPException(status_code=404, detail="Start or end node not found")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(f"""
        SELECT json_agg(json_build_object('lat', ST_Y(n.geom), 'lon', ST_X(n.geom))) AS route
        FROM pgr_dijkstra(
            'SELECT id, source, target, cost FROM edges', 
            {start_node}, {end_node}
        ) AS r
        JOIN nodes n ON r.node = n.id;
    """)
    route = cur.fetchone()[0]

    cur.close()
    conn.close()

    if not route:
        raise HTTPException(status_code=404, detail="No route found")

    return {"route": route}
