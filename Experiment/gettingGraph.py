import psycopg2
import networkx as nx

# Database Configuration
DB_CONFIG = {
    "dbname": "routedb",
    "user": "postgres",
    "password": "admin",
    "host": "localhost",
    "port": "5432",
}

# Connect to PostgreSQL
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# Load edges from PostgreSQL
cur.execute("SELECT source, target, length FROM edges;")
edges = cur.fetchall()

# Create Graph in NetworkX
G = nx.DiGraph()  # Directed Graph for one-way streets

for source, target, length in edges:
    G.add_edge(source, target, weight=length)

print(f"Graph loaded with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")

cur.close()
conn.close()
