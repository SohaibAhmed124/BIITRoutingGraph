import networkx as nx
import matplotlib.pyplot as plt

# Create an empty undirected graph
G = nx.Graph()

# Add nodes
G.add_node(1)  # Add a single node with ID 1
G.add_nodes_from([2, 3, 4])  # Add multiple nodes from a list

# Add edges
G.add_edge(1, 2)  # Add an edge between nodes 1 and 2
G.add_edges_from([(2, 3), (3, 4), (4, 1)])  # Add multiple edges from a list of tuples

# Print graph information
print("Nodes:", G.nodes)
print("Edges:", G.edges)

# Visualize the graph
nx.draw(G, with_labels=True, node_color='lightblue', edge_color='gray')
plt.show()