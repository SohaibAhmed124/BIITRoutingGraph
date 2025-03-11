import networkx as nx

def build_graph_from_geojson(geojson_data, profile="car"):
    G = nx.DiGraph()  # Directed graph to handle one-way streets

    for feature in geojson_data['features']:
        properties = feature.get('properties', {})
        geometry = feature['geometry']

        if geometry['type'] == 'LineString':
            coords = geometry['coordinates']
            oneway = properties.get("oneway", "no") == "yes"
            highway_type = properties.get("highway", "")
            motor_vehicle = properties.get("motor_vehicle", "yes").lower()
            bicycle = properties.get("bicycle", "yes").lower()
            foot = properties.get("foot", "yes").lower()
            cost = properties.get("cost", 1)  # Default cost if not provided

            # Check if the road is allowed for the given profile
            if profile == "car" and motor_vehicle == "no":
                continue
            if profile == "bike" and bicycle == "no":
                continue
            if profile == "foot" and foot == "no":
                continue

            for i in range(len(coords) - 1):
                source = tuple(coords[i])
                target = tuple(coords[i + 1])
                
                # Add nodes
                G.add_node(source, pos=source)
                G.add_node(target, pos=target)
                
                # Add edge (handle one-way roads)
                G.add_edge(source, target, weight=cost)
                if not oneway:
                    G.add_edge(target, source, weight=cost)
    
    return G
