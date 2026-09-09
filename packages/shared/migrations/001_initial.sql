-- SELERY research schema v1. No broker or execution tables.
CREATE EXTENSION IF NOT EXISTS timescaledb;


CREATE TABLE alerts (
	id VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE audit (
	id VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE bars (
	symbol VARCHAR NOT NULL, 
	feed VARCHAR NOT NULL, 
	timeframe VARCHAR NOT NULL, 
	time TIMESTAMP WITH TIME ZONE NOT NULL, 
	available_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	open FLOAT, 
	high FLOAT, 
	low FLOAT, 
	close FLOAT, 
	volume FLOAT, 
	source VARCHAR, 
	version VARCHAR NOT NULL, 
	PRIMARY KEY (symbol, feed, timeframe, time)
)

;


CREATE TABLE budgets (
	month VARCHAR NOT NULL, 
	spent FLOAT NOT NULL, 
	reserved FLOAT NOT NULL, 
	PRIMARY KEY (month)
)

;


CREATE TABLE devices (
	id VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE features (
	id VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE jobs (
	id VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE journal (
	id VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE models (
	id VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE news (
	id VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE outcomes (
	id VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE reports (
	id VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE settings (
	id VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE signals (
	id VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
)

;

SELECT create_hypertable('bars', 'time', if_not_exists => TRUE);
CREATE INDEX bars_available_idx ON bars (symbol, feed, timeframe, available_at);
