import psycopg2
import networkx as nx
from scipy.spatial import KDTree
import geojson
from geopy.distance import geodesic

# Database connection parameters
db_config = {
    "dbname": "routedb",
    "user": "postgres",
    "password": "admin",
    "host": "localhost",
    "port": "5432"
}

# Function to fetch GeoJSON data from the database
def fetch_geojson_from_db():
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()

        query = """
        SELECT properties, ST_AsGeoJSON(geometry) AS geometry
        FROM routes;
        """
        cursor.execute(query)
        rows = cursor.fetchall()

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

        return {"type": "FeatureCollection", "features": features}

    except Exception as e:
        print(f"Error fetching data: {e}")
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()

# Function to build a graph from GeoJSON data
def build_graph_from_geojson(geojson_data):
    G = nx.DiGraph()  # Use directed graph for one-way roads

    for feature in geojson_data['features']:
        geometry = feature['geometry']
        properties = feature.get('properties', {})

        if geometry['type'] == 'LineString':
            coords = geometry['coordinates']
            is_oneway = properties.get('oneway', 'no') == 'yes'  # Check if road is one-way
            cost = properties.get('cost', 1)  # Default cost if not provided

            for i in range(len(coords) - 1):
                source = tuple(coords[i])
                target = tuple(coords[i + 1])

                G.add_node(source, pos=source)
                G.add_node(target, pos=target)

                # Add edge (one-way or bidirectional)
                G.add_edge(source, target, weight=cost)
                if not is_oneway:  # Add reverse edge for bidirectional roads
                    G.add_edge(target, source, weight=cost)

    return G

# Haversine heuristic for A* search
def heuristic(node1, node2):
    return geodesic(node1, node2).meters  # Straight-line distance in meters

# Function to find the nearest node using a K-D Tree
def find_nearest_node(kdtree, nodes, target_coords):
    distance, index = kdtree.query(target_coords)
    return nodes[index], distance

# Function to generate Leaflet map visualization
def generate_leaflet_html(path_coords, output_file="path_visualization.html"):
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Shortest Path Visualization</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <style>#map {{ height: 600px; }}</style>
    </head>
    <body>
        <div id="map"></div>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
            var map = L.map('map').setView([{path_coords[0][0]}, {path_coords[0][1]}], 15);
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '&copy; OpenStreetMap contributors'
            }}).addTo(map);
            var pathCoords = {path_coords};
            L.polyline(pathCoords, {{color: 'red'}}).addTo(map);
            L.marker([{path_coords[0][0]}, {path_coords[0][1]}]).addTo(map).bindPopup('Start Node');
            L.marker([{path_coords[-1][0]}, {path_coords[-1][1]}]).addTo(map).bindPopup('End Node');
        </script>
    </body>
    </html>
    """
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_template)
    print(f"Leaflet visualization saved to {output_file}")

# Main script
if __name__ == "__main__":
    # Fetch GeoJSON data from database
    geojson_data = fetch_geojson_from_db()
    if not geojson_data:
        print("Failed to fetch GeoJSON data.")
        exit()

    # Build the graph from GeoJSON data
    G = build_graph_from_geojson(geojson_data)
    print(f"Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")

    # Build K-D Tree from graph nodes
    nodes = list(G.nodes())
    kdtree = KDTree(nodes)

    # Source and target coordinates (Replace with actual coordinates)
    snode = (73.084477, 33.661001)  # Example coordinates
    tnode = (73.08296, 33.65165)  # Example coordinates

    # Find nearest graph nodes
    source_node, _ = find_nearest_node(kdtree, nodes, snode)
    target_node, _ = find_nearest_node(kdtree, nodes, tnode)
    print(f"Source node: {source_node}, Target node: {target_node}")

    # Find the shortest path using A* algorithm
    try:
        shortest_path = nx.astar_path(G, source=source_node, target=target_node, weight='weight', heuristic=heuristic)
        print(f"Shortest path: {shortest_path}")

        # Calculate total cost
        total_cost = sum(G[shortest_path[i]][shortest_path[i + 1]]['weight'] for i in range(len(shortest_path) - 1))
        print(f"Total cost: {total_cost}")

        # Convert path to Leaflet-friendly format
        path_coords = [[lon, lat] for lat, lon in shortest_path]

        # Generate HTML visualization
        generate_leaflet_html(path_coords)

    except nx.NetworkXNoPath:
        print(f"No path exists between {source_node} and {target_node}")
