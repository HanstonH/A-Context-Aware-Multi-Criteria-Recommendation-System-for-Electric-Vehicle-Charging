-- Local SQLite database (not Supabase).
-- Run via: python database/import_data.py

CREATE TABLE IF NOT EXISTS stations (
  station_id     TEXT PRIMARY KEY,
  source         TEXT NOT NULL,          -- tdx | sumo
  city           TEXT,
  station_name   TEXT,
  description    TEXT,
  operator_id    TEXT,
  lat            REAL NOT NULL,
  lon            REAL NOT NULL,
  spaces         INTEGER,
  charging_points INTEGER,
  service_time   TEXT,
  address        TEXT,
  telephone      TEXT,
  plug_type      TEXT,
  updated_at     TEXT
);

CREATE TABLE IF NOT EXISTS station_connectors (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  station_id  TEXT NOT NULL REFERENCES stations(station_id),
  type        INTEGER,   -- TDX connector type (5=CCS, 6=Type2, ...)
  power       INTEGER,   -- 1=AC, 2=DC
  quantity    INTEGER
);

CREATE TABLE IF NOT EXISTS charging_rates (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  station_id         TEXT NOT NULL,
  charging_point_id  TEXT,
  connector_id       TEXT,
  rate_type          INTEGER,   -- 1=free, 2=per kWh, 3=other
  pricing_type       INTEGER,
  rate_price         REAL,
  peak               INTEGER,
  start_time         TEXT,
  end_time           TEXT
);

CREATE TABLE IF NOT EXISTS telemetry (
  id                            INTEGER PRIMARY KEY AUTOINCREMENT,
  time_s                        REAL,
  vehicle_id                    TEXT,
  lat                           REAL,
  lon                           REAL,
  speed_mps                     REAL,
  remaining_wh                  REAL,
  max_wh                        REAL,
  soc_percent                   REAL,
  charging                      INTEGER,
  charging_station_id           TEXT,
  total_energy_consumed_wh      REAL,
  energy_charged_wh             REAL,
  distance_m                    REAL,
  is_tracked                    INTEGER
);

CREATE TABLE IF NOT EXISTS recommendation_logs (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  mac_address    TEXT,
  station_name   TEXT,
  lat            REAL,
  lon            REAL,
  distance_m     REAL,
  waiting_time_s REAL,
  cost           REAL,
  total_score    REAL,
  rank           INTEGER
);

CREATE INDEX IF NOT EXISTS stations_city_idx ON stations(city);
CREATE INDEX IF NOT EXISTS stations_source_idx ON stations(source);
CREATE INDEX IF NOT EXISTS connectors_station_idx ON station_connectors(station_id);
CREATE INDEX IF NOT EXISTS rates_station_idx ON charging_rates(station_id);
CREATE INDEX IF NOT EXISTS telemetry_vehicle_time_idx ON telemetry(vehicle_id, time_s);
CREATE INDEX IF NOT EXISTS recs_rank_idx ON recommendation_logs(rank);
