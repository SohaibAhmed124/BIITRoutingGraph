import matplotlib.pyplot as plt

# Points
points = [(7, 2), (5, 4), (9, 6), (4, 7), (8, 1), (2, 3)]
x = [p[0] for p in points]
y = [p[1] for p in points]

# Plot points
plt.scatter(x, y, c='blue', label='Points')

# Draw splits
plt.axvline(x=7, color='red', linestyle='--', label='x=7')  # First split (x-axis)
plt.axhline(y=4, color='green', linestyle='--', label='y=4')  # Second split (y-axis, left subtree)
plt.axhline(y=6, color='purple', linestyle='--', label='y=6')  # Second split (y-axis, right subtree)

# Annotate points
for i, (xi, yi) in enumerate(points):
    plt.text(xi, yi, f'({xi}, {yi})', fontsize=9, ha='right')

# Add labels and legend
plt.xlabel('x')
plt.ylabel('y')
plt.title('k-d Tree Partitioning')
plt.legend()
plt.grid()
plt.show()