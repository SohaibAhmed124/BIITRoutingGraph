import geojson
import networkx as nx
from scipy.spatial import KDTree

# Load GeoJSON file
with open("map.geojson", "r", encoding="utf-8") as f:
    geojson_data = geojson.load(f)

# Initialize a graph
G = nx.Graph()

# Parse GeoJSON features
for feature in geojson_data['features']:
    geometry = feature['geometry']
    properties = feature.get('properties', {})

    if geometry['type'] == 'LineString':
        coords = geometry['coordinates']
        
        # Add edges and nodes to the graph
        for i in range(len(coords) - 1):
            source = tuple(coords[i])
            target = tuple(coords[i + 1])
            cost = properties.get('cost', 1)  # Default cost if not provided
            
            # Add nodes with coordinates as IDs
            G.add_node(source, pos=source)
            G.add_node(target, pos=target)
            
            # Add edge
            G.add_edge(source, target, weight=cost)

# Build K-D Tree from graph nodes
nodes = list(G.nodes())
kdtree = KDTree(nodes)

# Specify the source and target nodes
snode = (73.05676, 33.65435)  # Example coordinates (Replace with the desired node)
tnode = (73.06567, 33.64306)  # Example coordinates (Replace with the desired node)

# Find the nearest nodes
_, source_index = kdtree.query(snode)
source_node = nodes[source_index]
print(f"Source node exists in graph: {G.has_node(source_node)}")

_, target_index = kdtree.query(tnode)
target_node = nodes[target_index]
print(f"Target node exists in graph: {G.has_node(target_node)}")

# Use Dijkstra's algorithm to find the shortest path
try:
    shortest_path = nx.dijkstra_path(G, source=source_node, target=target_node, weight='weight')
    print(f"Shortest path from {source_node} to {target_node}: {shortest_path}")
    
    # Calculate total cost of the shortest path
    total_cost = sum(G[shortest_path[i]][shortest_path[i + 1]]['weight'] for i in range(len(shortest_path) - 1))
    print(f"Total cost of the shortest path: {total_cost}")

    # Generate Leaflet visualization
    def generate_leaflet_html(path_coords, output_file="path_visualization.html"):
        # HTML template with Leaflet
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Shortest Path Visualization</title>
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
            <style>
                #map {{ height: 600px; }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <script>
                // Initialize the map
                var map = L.map('map').setView([{path_coords[0][0]}, {path_coords[0][1]}], 15);

                // Add a tile layer (OpenStreetMap)
                L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                }}).addTo(map);

                // Add the path as a polyline
                var pathCoords = {path_coords};
                L.polyline(pathCoords, {{color: 'red'}}).addTo(map);

                // Add markers for the start and end points
                L.marker([{path_coords[0][0]}, {path_coords[0][1]}]).addTo(map)
                    .bindPopup('Start Node');
                L.marker([{path_coords[-1][0]}, {path_coords[-1][1]}]).addTo(map)
                    .bindPopup('End Node');
            </script>
        </body>
        </html>
        """
        
        # Write the HTML file
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_template)
        print(f"Leaflet visualization saved to {output_file}")

    # Extract coordinates from the shortest path
    path_coords = [[lon, lat] for lat, lon in shortest_path]
    
    # Generate the Leaflet HTML file
    generate_leaflet_html(path_coords)

except nx.NetworkXNoPath:
    print(f"No path exists between {source_node} and {target_node}")