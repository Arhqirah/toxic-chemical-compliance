-- Tables for Toxic Chemical Industrie A/S.
-- Runs automatically the first time the database container starts.


-- A depot somewhere in the EU
CREATE TABLE site (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    name    VARCHAR(100) NOT NULL,
    country VARCHAR(2)   NOT NULL            -- ISO code, e.g. 'DK'
);

-- Each site has warehouses 1-5 with a fixed capacity in K units
CREATE TABLE warehouse (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    site_id     INT NOT NULL,
    number      TINYINT NOT NULL CHECK (number BETWEEN 1 AND 5),
    capacity_k  DECIMAL(6,2) NOT NULL CHECK (capacity_k > 0),
    FOREIGN KEY (site_id) REFERENCES site(id),
    UNIQUE (site_id, number)                 -- no two "warehouse 3" on one site
);

-- Staff who log in. Named "users" because "user" is easy to confuse
-- with MariaDB's own mysql.user table.
CREATE TABLE users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,     -- never the plain password
    role          ENUM('gate', 'warehouse', 'compliance') NOT NULL
);

-- What is stored where right now
CREATE TABLE stock (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    warehouse_id   INT NOT NULL,
    chemical_class ENUM('A', 'B', 'C') NOT NULL,
    units_k        DECIMAL(6,2) NOT NULL CHECK (units_k >= 0),
    delivered_at   DATETIME NOT NULL,
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(id)
);

-- A job is raised at the gate (IN = delivery, OUT = dispatch)
-- and closed as 'confirmed' when the barrels have been moved
CREATE TABLE job (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    site_id        INT NOT NULL,
    warehouse_id   INT NOT NULL,
    type           ENUM('IN', 'OUT') NOT NULL,
    chemical_class ENUM('A', 'B', 'C') NOT NULL,
    units_k        DECIMAL(6,2) NOT NULL CHECK (units_k > 0),
    ticket_ref     VARCHAR(50) NOT NULL,     -- the driver's ticket number
    status         ENUM('open', 'confirmed') NOT NULL DEFAULT 'open',
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES site(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(id)
);

-- Every change is logged here. The app account may only INSERT and SELECT,
-- so nobody using the app can change or delete history.
CREATE TABLE audit_log (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    job_id     INT NULL,
    user_id    INT NULL,
    action     VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES job(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Indexes for the columns we filter the inventory and jobs on
CREATE INDEX idx_stock_class      ON stock (chemical_class);
CREATE INDEX idx_stock_delivered  ON stock (delivered_at);
CREATE INDEX idx_job_created      ON job (created_at);
