CREATE TABLE nodes (
    id SERIAL PRIMARY KEY,
    lat NUMERIC NOT NULL,
    lon NUMERIC NOT NULL
);

CREATE TABLE edges (
    id SERIAL PRIMARY KEY,
    source INT REFERENCES nodes(id),
    target INT REFERENCES nodes(id),
    length NUMERIC NOT NULL, -- Distance (meters)
    cost NUMERIC NOT NULL, -- Travel cost (time or distance)
    reverse_cost NUMERIC, -- If bidirectional, otherwise NULL
    oneway BOOLEAN DEFAULT FALSE,
    highway TEXT,
    maxspeed INT
);

ALTER TABLE edges ADD COLUMN geom geometry(LineString, 4326);

UPDATE edges
SET geom = ST_MakeLine(
    (SELECT geom FROM nodes WHERE nodes.id = edges.source),
    (SELECT geom FROM nodes WHERE nodes.id = edges.target)
)
WHERE geom IS NULL;

ALTER TABLE nodes ADD COLUMN geom geometry(Point, 4326);

UPDATE nodes 
SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326);

SELECT edges.source, edges.target, nodes.id 
FROM edges 
LEFT JOIN nodes ON edges.source = nodes.id 
WHERE nodes.id IS NULL;

SELECT id, ST_AsText(geom) FROM edges LIMIT 5;

SELECT COUNT(*) FROM edges WHERE geom IS NULL;

SELECT pgr_createTopology('edges', 0.0001, 'geom', 'id');
