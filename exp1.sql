SELECT * FROM public.edges where highway = 'custom'

SELECT setval('nodes_id_seq', (SELECT MAX(id) FROM nodes));

SELECT * FROM pg_sequences WHERE schemaname = 'public' AND sequencename = 'nodes_id_seq';


SELECT COUNT(*) FROM edges WHERE source IS NULL OR target IS NULL;

SELECT * FROM edges WHERE source NOT IN (SELECT id FROM nodes) OR target NOT IN (SELECT id FROM nodes);

SELECT * FROM nodes WHERE id IN (SELECT source FROM edges UNION SELECT target FROM edges);

SELECT * FROM edges WHERE cost IS NULL;

SELECT pgr_createTopology('edges', 0.0001, 'geom', 'id');



