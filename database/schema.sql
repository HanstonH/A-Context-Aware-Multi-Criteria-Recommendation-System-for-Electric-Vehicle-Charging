-- Local SQLite schema for the EV charging project.
-- Replaces the old Supabase `users` table. No cloud host required.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT,
    phone TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label TEXT,
    capacity_kwh REAL NOT NULL DEFAULT 60,
    wh_per_km REAL NOT NULL DEFAULT 180,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One row per charger. station_id is MAC Address (project) or TDX StationID.
CREATE TABLE IF NOT EXISTS stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL CHECK (source IN ('project', 'tdx')),
    name TEXT,
    address TEXT,
    operator TEXT,
    plug_type TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    city TEXT,
    spaces INTEGER,
    charging_points INTEGER,
    sumo_cs_id TEXT,
    sumo_lane TEXT
);

CREATE INDEX IF NOT EXISTS idx_stations_city ON stations(city);
CREATE INDEX IF NOT EXISTS idx_stations_geo ON stations(latitude, longitude);

CREATE TABLE IF NOT EXISTS station_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id TEXT NOT NULL REFERENCES stations(station_id) ON DELETE CASCADE,
    price_ntd_per_kwh REAL,
    price_tier REAL,
    parking_cost REAL,
    source TEXT,
    UNIQUE (station_id, source)
);

-- Connector-level TDX charging rates (GitHub static snapshot).
CREATE TABLE IF NOT EXISTS charging_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id TEXT,
    charging_point_id TEXT,
    connector_id TEXT,
    city TEXT,
    rate_type INTEGER,
    pricing_type INTEGER,
    rate_price REAL,
    peak INTEGER,
    start_time TEXT,
    end_time TEXT,
    fetched_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_charging_rates_station ON charging_rates(station_id);

CREATE TABLE IF NOT EXISTS recommendation_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    latitude REAL,
    longitude REAL,
    battery_pct REAL,
    city TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recommendation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER REFERENCES recommendation_requests(id) ON DELETE CASCADE,
    station_id TEXT,
    station_name TEXT,
    latitude REAL,
    longitude REAL,
    distance_m REAL,
    waiting_time REAL,
    poi_sum REAL,
    cost REAL,
    total_score REAL,
    rank INTEGER,
    explanation TEXT
);
