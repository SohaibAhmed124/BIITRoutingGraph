import psycopg2
import networkx as nx
from scipy.spatial import KDTree
import geojson
from shapely.geometry import LineString, Point
from shapely.validation import make_valid
from shapely.strtree import STRtree
import time
import os
import psutil



# Database connection parameters
DB_CONFIG = {
    "dbname": "routedb",
    "user": "postgres",
    "password": "admin",
    "host": "localhost",
    "port": "5432"
}



# def split_line_at_point(line, point):
#     """Split a LineString at a given point, ensuring valid geometries."""
#     line = make_valid(LineString(line))  # Ensure the LineString is valid
#     point = make_valid(Point(point))     # Ensure the Point is valid

#     if not line.is_valid or not point.is_valid:
#         raise ValueError("Invalid geometry encountered.")

#     if not line.contains(point) and not line.touches(point):
#         raise ValueError("Point does not lie on the LineString.")

#     distance = line.project(point)
#     split_line = [
#         list(line.interpolate(d).coords[0]) for d in [0, distance, line.length]
#     ]
#     return [split_line[0], split_line[1]], [split_line[1], split_line[2]]

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

def find_intersection(line1, line2):
    """Find intersection point between two LineStrings."""
    line1 = LineString(line1)
    line2 = LineString(line2)
    intersection = line1.intersection(line2)
    if intersection.is_empty:
        return None
    if intersection.geom_type == 'Point':
        return intersection.coords[0]  # Return the intersection point
    return None  # Ignore multi-point or line intersections

def log_memory_usage():
    """Log the current memory usage of the process."""
    process = psutil.Process(os.getpid())
    print(f"Memory usage: {process.memory_info().rss / 1024 ** 2:.2f} MB")

def split_line_at_point(line, point):
    """Split a LineString at a given point, ensuring valid geometries."""
    line = make_valid(LineString(line))  # Ensure the LineString is valid
    point = make_valid(Point(point))     # Ensure the Point is valid

    if not line.is_valid or not point.is_valid:
        raise ValueError("Invalid geometry encountered.")

    if not line.contains(point) and not line.touches(point):
        raise ValueError("Point does not lie on the LineString.")

    distance = line.project(point)
    split_line = [
        list(line.interpolate(d).coords[0]) for d in [0, distance, line.length]
    ]
    return [split_line[0], split_line[1]], [split_line[1], split_line[2]]

def build_graph_with_intersections(geojson_data, tolerance=0.0001):
    """Build a graph from GeoJSON data, handling intersections and merging similar nodes."""
    G = nx.DiGraph()
    lines = []

    # First pass: Collect all LineStrings and their geometries
    line_geometries = []
    for feature in geojson_data['features']:
        if feature['geometry']['type'] == 'LineString':
            coords = feature['geometry']['coordinates']
            properties = feature.get('properties', {})
            try:
                line = make_valid(LineString(coords))
                if not line.is_valid:
                    print(f"Skipping invalid LineString: {coords}")
                    continue
                lines.append({
                    'geometry': line,
                    'coordinates': coords,
                    'properties': properties
                })
                line_geometries.append(line)
            except Exception as e:
                print(f"Error creating LineString: {e}")
                continue

    # Build a spatial index
    tree = STRtree(line_geometries)

    # Second pass: Detect intersections and split LineStrings
    new_lines = []
    batch_size = 1000  # Adjust batch size as needed
    batches = [lines[i:i + batch_size] for i in range(0, len(lines), batch_size)]
    max_candidates = 2000  # Skip LineStrings with too many candidates
    max_intersections = 50  # Skip LineStrings with too many intersection points

    for batch in batches:
        start_time = time.time()
        batch_index = batches.index(batch) + 1
        print(f"Processing batch {batch_index}/{len(batches)}")
        log_memory_usage()

        for line1 in batch:
            coords1 = line1['coordinates']
            split_points = set()
            candidates = tree.query(line1['geometry'])
            num_candidates = len(candidates)
            print(f"LineString {batch.index(line1) + 1}/{len(batch)}: {num_candidates} candidates")

            if num_candidates > max_candidates:
                print(f"Skipping LineString {batch.index(line1) + 1}/{len(batch)}: too many candidates ({num_candidates})")
                continue

            for candidate in candidates:
                if candidate == line1['geometry']:
                    continue  # Skip self
                if not isinstance(candidate, LineString):
                    continue  # Skip invalid candidates
                try:
                    intersection = line1['geometry'].buffer(tolerance).intersection(candidate.buffer(tolerance))
                    if intersection.is_empty:
                        continue
                    if intersection.geom_type == 'Point':
                        split_points.add(intersection.coords[0])
                except Exception as e:
                    print(f"Error computing intersection: {e}")
                    continue

            num_intersections = len(split_points)
            print(f"LineString {batch.index(line1) + 1}/{len(batch)}: {num_intersections} intersection points")

            if num_intersections > max_intersections:
                print(f"Skipping LineString {batch.index(line1) + 1}/{len(batch)}: too many intersections ({num_intersections})")
                continue

            if split_points:
                current_line = coords1
                for point in sorted(split_points, key=lambda p: LineString(current_line).project(Point(p))):
                    try:
                        part1, part2 = split_line_at_point(current_line, point)
                        new_lines.append({'coordinates': part1, 'properties': line1['properties']})
                        current_line = part2
                    except ValueError as e:
                        print(f"Skipping invalid split: {e}")
                new_lines.append({'coordinates': current_line, 'properties': line1['properties']})
            else:
                new_lines.append(line1)

        end_time = time.time()
        print(f"Batch {batch_index} processed in {end_time - start_time:.2f} seconds")
        log_memory_usage()

    # Third pass: Add nodes and edges to the graph
    for line in new_lines:
        coords = line['coordinates']
        properties = line['properties']
        is_oneway = properties.get('oneway', 'no') == 'yes'
        cost = properties.get('cost', 1)

        for i in range(len(coords) - 1):
            source = tuple(coords[i])
            target = tuple(coords[i + 1])

            G.add_node(source, pos=source)
            G.add_node(target, pos=target)

            G.add_edge(source, target, weight=cost)
            if not is_oneway:
                G.add_edge(target, source, weight=cost)

    # Merge similar nodes
    G = merge_similar_nodes(G, tolerance)

    return G

def merge_similar_nodes(G, tolerance=0.0001):
    """Merge nodes that are within a given tolerance."""
    nodes = list(G.nodes)
    merged_nodes = {}

    for i, node1 in enumerate(nodes):
        if node1 in merged_nodes:
            continue
        for j in range(i + 1, len(nodes)):
            node2 = nodes[j]
            if abs(node1[0] - node2[0]) < tolerance and abs(node1[1] - node2[1]) < tolerance:
                merged_nodes[node2] = node1

    # Update the graph
    for old_node, new_node in merged_nodes.items():
        for neighbor in G[old_node]:
            G.add_edge(new_node, neighbor, **G[old_node][neighbor])
        G.remove_node(old_node)

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
    G = build_graph_with_intersections(geojson_data)
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
