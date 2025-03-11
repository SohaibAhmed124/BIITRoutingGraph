from scipy.spatial import cKDTree
# Example: Building the K-D tree from your graph's nodes
def build_kdtree_from_graph(G):
    # Extract coordinates from the nodes
    nodes = list(G.nodes())
    coordinates = [node for node in nodes]
    
    # Create the K-D Tree
    kdtree = cKDTree(coordinates)
    
    return kdtree, nodes

# Example: Finding the nearest node to a given node
def find_nearest_node(kdtree, nodes, target_node):
    # Get the coordinates of the target node
    target_coords = target_node
    
    # Query the K-D tree for the nearest neighbor
    distance, index = kdtree.query(target_coords)
    
    # Return the nearest node
    nearest_node = nodes[index]
    return nearest_node, distance

