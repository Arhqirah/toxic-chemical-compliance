-- Starter data: 4 sites x 5 warehouses = 20 warehouses.
-- (More seed data for stock, jobs and users comes in phase 2.)


INSERT INTO site (name, country) VALUES
    ('Køge Depot',      'DK'),
    ('Hamburg Depot',   'DE'),
    ('Rotterdam Depot', 'NL'),
    ('Lyon Depot',      'FR');

-- Capacities from the brief: warehouse 1-5 = 10, 12, 5, 3, 9 K units.
-- Written out row by row so the ids are predictable (1-5 = site 1, 6-10 = site 2, ...).
-- 04_seed_data.sql relies on this order.
INSERT INTO warehouse (site_id, number, capacity_k) VALUES
    (1, 1, 10),
    (1, 2, 12),
    (1, 3, 5),
    (1, 4, 3),
    (1, 5, 9),
    (2, 1, 10),
    (2, 2, 12),
    (2, 3, 5),
    (2, 4, 3),
    (2, 5, 9),
    (3, 1, 10),
    (3, 2, 12),
    (3, 3, 5),
    (3, 4, 3),
    (3, 5, 9),
    (4, 1, 10),
    (4, 2, 12),
    (4, 3, 5),
    (4, 4, 3),
    (4, 5, 9);
