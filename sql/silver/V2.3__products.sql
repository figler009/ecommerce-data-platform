USE SCHEMA ANALYTICS_DB.SILVER;

CREATE OR REPLACE TABLE PRODUCTS (
  PRODUCT_ID STRING NOT NULL,
  PRODUCT_NAME STRING,
  CATEGORY STRING,
  BRAND STRING,
  LIST_PRICE NUMBER(10, 2),
  LOAD_TIMESTAMP TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (PRODUCT_ID)
);

-- Seed data: mimics a product master feed, since no upstream PIM source exists in this project
INSERT INTO PRODUCTS (PRODUCT_ID, PRODUCT_NAME, CATEGORY, BRAND, LIST_PRICE) VALUES
('PROD001', 'Wireless Headphones', 'Electronics', 'SoundWave', 79.99),
('PROD002', 'Running Shoes', 'Footwear', 'TrailBlaze', 59.99),
('PROD003', 'Stainless Water Bottle', 'Outdoors', 'HydroPeak', 19.99),
('PROD004', 'Bluetooth Speaker', 'Electronics', 'SoundWave', 49.99),
('PROD005', 'Yoga Mat', 'Fitness', 'FlexFit', 24.99);
