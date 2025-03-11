import psycopg2
import networkx as nx
from scipy.spatial import KDTree
import geojson
from geopy.distance import geodesic
from networkx.algorithms.simple_paths import shortest_simple_paths
import random


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

# Function to find the nearest node using a K-D Tree
def find_nearest_node(kdtree, nodes, target_coords):
    distance, index = kdtree.query(target_coords)
    return nodes[index], distance

# Haversine heuristic for A* search
def heuristic(node1, node2):
    return geodesic(node1, node2).meters  # Straight-line distance in meters


# Random Route Selection 
def find_randomized_paths(G, source, target, k=3):
    paths = []
    
    for _ in range(k):
        temp_G = G.copy()
        
        # Add some random variation to weights
        for u, v, data in temp_G.edges(data=True):
            data['weight'] *= random.uniform(0.9, 1.2)  # Add randomness to costs
        
        try:
            path = nx.astar_path(temp_G, source, target, weight='weight', heuristic=heuristic)
            paths.append(path)
        except nx.NetworkXNoPath:
            break
    
    return paths

# K-Diverse Paths (Avoid Same Path)
def find_k_diverse_paths(G, source, target, k=3):
    paths = []
    temp_G = G.copy()

    for _ in range(k):
        try:
            path = nx.astar_path(temp_G, source, target, weight='weight', heuristic=heuristic)
            paths.append(path)

            # Increase weight on used edges to force alternative paths
            for i in range(len(path) - 1):
                temp_G[path[i]][path[i+1]]['weight'] *= 1.5  # Increase cost of used edges
        except nx.NetworkXNoPath:
            break
    
    return paths

# k-shortest path (Yen's Algorithm)
def find_k_shortest_paths(G, source, target, k=3):
    try:
        best_path = nx.astar_path(G, source, target, weight="weight")  # A* for 1st path
        path_generator = shortest_simple_paths(G, source, target, weight="weight")
        return [best_path] + [next(path_generator) for _ in range(k - 1)]  # Get k-1 more
    except Exception as e:
        print(f"Error finding multiple paths: {e}")
        return []


# Function to generate Leaflet map visualization
def generate_leaflet_html(multiple_paths, output_file="path_visualization.html"):
    colors = ["red", "blue", "green", "purple", "orange"]  # Different colors for different paths

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Multiple Routes Visualization</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <style>#map {{ height: 600px; }}</style>
    </head>
    <body>
        <div id="map"></div>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
            var map = L.map('map').setView([{multiple_paths[0][0][1]}, {multiple_paths[0][0][0]}], 15);
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(map);
    """
    
    for i, path in enumerate(multiple_paths):
        color = colors[i % len(colors)]  # Cycle through colors
        path_coords = [[lon, lat] for lat, lon in path]
        html_template += f"""
            L.polyline({path_coords}, {{color: '{color}', weight:5, opacity:0.4}}).addTo(map);
        """
    
    html_template += f"""
            // Start and End Markers
            var startIcon = L.icon({{
                iconUrl: 'https://cdn-icons-png.flaticon.com/32/684/684908.png', 
                iconSize: [25, 25]
            }});
            var endIcon = L.icon({{
                iconUrl: 'https://cdn-icons-png.flaticon.com/32/684/684912.png',
                iconSize: [25, 25]
            }});

            L.marker([{multiple_paths[0][0][1]}, {multiple_paths[0][0][0]}], {{icon: startIcon}}).addTo(map)
                .bindPopup('Start Node');

            L.marker([{multiple_paths[0][-1][1]}, {multiple_paths[0][-1][0]}], {{icon: endIcon}}).addTo(map)
                .bindPopup('End Node');
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
    snode = (73.04934, 33.59675)  # Example coordinates
    tnode = (73.07492, 33.66728)  # Example coordinates

    # Find nearest graph nodes
    source_node, _ = find_nearest_node(kdtree, nodes, snode)
    target_node, _ = find_nearest_node(kdtree, nodes, tnode)
    print(f"Source node: {source_node}, Target node: {target_node}")

    k_paths = find_k_shortest_paths(G, source_node, target_node, k=3)

    for i, path in enumerate(k_paths):
        print(f"Path {i+1}: {path}")

    # diverse_paths = find_k_diverse_paths(G, source_node, target_node, k=3)

    # for i, path in enumerate(diverse_paths):
    #     print(f"Alternative Path {i+1}: {path}")

    # random_paths = find_randomized_paths(G, source_node, target_node, k=2)

    # for i, path in enumerate(random_paths):
    #     print(f"Alternative Path {i+1}: {path}")

    generate_leaflet_html(k_paths)

