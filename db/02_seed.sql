-- Starter data: 4 sites x 5 warehouses = 20 warehouses.
-- (More seed data for stock, jobs and users comes in phase 2.)


INSERT INTO site (name, country) VALUES
    ('Køge Depot',      'DK'),
    ('Hamburg Depot',   'DE'),
    ('Rotterdam Depot', 'NL'),
    ('Lyon Depot',      'FR');

-- Capacities from the brief: warehouse 1-5 = 10, 12, 5, 3, 9 K units.
-- The cross join gives every site all 5 warehouses.
INSERT INTO warehouse (site_id, number, capacity_k)
SELECT s.id, w.number, w.capacity_k
FROM site s
CROSS JOIN (
    SELECT 1 AS number, 10 AS capacity_k UNION ALL
    SELECT 2, 12 UNION ALL
    SELECT 3, 5  UNION ALL
    SELECT 4, 3  UNION ALL
    SELECT 5, 9
) w;
