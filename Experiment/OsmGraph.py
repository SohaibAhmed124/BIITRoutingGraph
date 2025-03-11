import psycopg2
import networkx as nx
from scipy.spatial import KDTree
import geojson

# Database connection parameters
DB_CONFIG = {
    "dbname": "routedb",
    "user": "postgres",
    "password": "admin",
    "host": "localhost",
    "port": "5432"
}

# Fetch GeoJSON data from the database
def fetch_geojson_from_db():
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                query = """
                SELECT properties, ST_AsGeoJSON(geometry) AS geometry
                FROM routes;
                """
                cursor.execute(query)
                rows = cursor.fetchall()

                # Convert database records to GeoJSON
                features = [
                    {"type": "Feature", "properties": properties, "geometry": geojson.loads(geometry_geojson)}
                    for properties, geometry_geojson in rows
                ]
                return {"type": "FeatureCollection", "features": features}

    except Exception as e:
        print(f"Error fetching data from the database: {e}")
        return None

# Build graph from GeoJSON data
def build_graph_from_geojson(geojson_data):
    G = nx.DiGraph()  # Directed graph to handle one-way roads

    for feature in geojson_data['features']:
        geometry = feature['geometry']
        properties = feature.get('properties', {})

        if geometry['type'] == 'LineString':
            coords = geometry['coordinates']
            is_oneway = properties.get('oneway', 'no') == 'yes'  # Check if road is one-way

            for i in range(len(coords) - 1):
                source = tuple(coords[i])
                target = tuple(coords[i + 1])
                cost = properties.get('cost', 1)  # Default cost if not provided

                # Add nodes
                G.add_node(source, pos=source)
                G.add_node(target, pos=target)

                # Add directed edge (one-way)
                G.add_edge(source, target, weight=cost)
                if not is_oneway:
                    G.add_edge(target, source, weight=cost)  # Add reverse edge if not one-way

        elif geometry['type'] == 'Polygon':
            exterior_ring = geometry['coordinates'][0]
            for i in range(len(exterior_ring) - 1):
                source = tuple(exterior_ring[i])
                target = tuple(exterior_ring[i + 1])
                cost = properties.get('cost', 1)

                G.add_node(source, pos=source)
                G.add_node(target, pos=target)
                G.add_edge(source, target, weight=cost)

        elif geometry['type'] == 'Point':
            G.add_node(tuple(geometry['coordinates']), pos=tuple(geometry['coordinates']))

        else:
            print(f"Unsupported geometry type: {geometry['type']}")

    return G

# Find the nearest node using a K-D Tree
def find_nearest_node(kdtree, nodes, target_coords):
    _, index = kdtree.query(target_coords)
    return nodes[index]

# Generate Leaflet HTML file for path visualization
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
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
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
    geojson_data = fetch_geojson_from_db()
    if not geojson_data:
        print("Failed to fetch GeoJSON data from the database.")
        exit()

    # Build the graph
    G = build_graph_from_geojson(geojson_data)
    print(f"Graph built with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")

    # Build K-D Tree
    nodes = list(G.nodes())
    kdtree = KDTree(nodes)

    # Example start and end points (replace with actual coordinates)
    start_coords = (73.04934, 33.59675)
    end_coords = (73.08453, 33.66114)

    # Find nearest nodes
    source_node = find_nearest_node(kdtree, nodes, start_coords)
    target_node = find_nearest_node(kdtree, nodes, end_coords)
    print(f"Nearest source node: {source_node}")
    print(f"Nearest target node: {target_node}")

    # Find shortest path using Dijkstra
    try:
        shortest_path = nx.dijkstra_path(G, source=source_node, target=target_node, weight='weight')
        total_cost = sum(G[shortest_path[i]][shortest_path[i + 1]]['weight'] for i in range(len(shortest_path) - 1))
        
        print(f"Shortest path: {shortest_path}")
        print(f"Total path cost: {total_cost}")

        # Convert path to Leaflet format
        path_coords = [[lon, lat] for lat, lon in shortest_path]
        generate_leaflet_html(path_coords)

    except nx.NetworkXNoPath:
        print("No path found between the given nodes.")
