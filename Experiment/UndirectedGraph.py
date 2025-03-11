import networkx as nx

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
    return G