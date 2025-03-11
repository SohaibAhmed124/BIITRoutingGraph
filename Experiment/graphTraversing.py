import psycopg2
import heapq
import networkx as nx
from decimal import Decimal

# Connect to PostgreSQL
def fetch_graph_data():
    conn = psycopg2.connect(
        dbname="routedb",
        user="postgres",
        password="admin",
        host="localhost",
        port="5432"
    )
    cursor = conn.cursor()

    # Fetch nodes and edges
    cursor.execute("SELECT id, name FROM nodes")
    nodes = cursor.fetchall()

    cursor.execute("SELECT source, target, cost FROM edges")
    edges = cursor.fetchall()

    conn.close()
    return nodes, edges

# Manual dijkstra Algorithm
def dijkstra_manual(nodes, edges, start, target):
    # Build adjacency list
    graph = {}
    for source, target_node, cost in edges:
        if source not in graph:
            graph[source] = []
        graph[source].append((target_node, float(cost)))

    print(graph)

    # Priority queue for Dijkstra
    pq = [(0, start)]  # (distance, node)
    distances = {node_id: float("inf") for node_id, _ in nodes}
    distances[start] = 0
    previous = {node_id: None for node_id, _ in nodes}
    
    while pq:
        current_distance, current_node = heapq.heappop(pq)
        
        if current_node == target:
            break
        
        if current_distance > distances[current_node]:
            continue
        
        for neighbor, weight in graph.get(current_node, []):
            distance = current_distance + weight
            if distance < distances[neighbor]:
                distances[neighbor] = distance
                previous[neighbor] = current_node
                heapq.heappush(pq, (distance, neighbor))
    
    # Reconstruct path
    path = []
    node = target
    while node is not None:
        path.append(node)
        node = previous[node]
    path.reverse()
    
    return {"cost": distances[target], "path": path}



def networkx_shortest_path(nodes, edges, start, target):
    G = nx.Graph()
    for source, target_node, cost in edges:
        G.add_edge(source, target_node, weight=float(cost))
    
    try:
        path = nx.shortest_path(G, source=start, target=target, weight='weight')
        cost = nx.shortest_path_length(G, source=start, target=target, weight='weight')
        return {"cost": cost, "path": path}
    except nx.NetworkXNoPath:
        return {"cost": float("inf"), "path": []}


if __name__ == "__main__":
    nodes, edges = fetch_graph_data()
    # Manual Dijkstra
    start_node, target_node = 2, 8

    result = dijkstra_manual(nodes, edges, start_node, target_node)
    cost = result['cost']
    path = result['path'] 
    print(f"Dijkstra - Cost: {cost}, Path: {path}")

    # Using NetworkX
    result = networkx_shortest_path(nodes, edges, start_node, target_node)
    cost = result['cost']
    path = result['path'] 
    print(f"NetworkX - Cost: {cost}, Path: {path}")
