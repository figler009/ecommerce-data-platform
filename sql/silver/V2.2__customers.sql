USE SCHEMA ANALYTICS_DB.SILVER;

CREATE OR REPLACE TABLE CUSTOMERS (
  CUSTOMER_ID STRING NOT NULL,
  CUSTOMER_NAME STRING,
  EMAIL STRING,  -- noqa: RF04
  REGION_ID STRING,
  SIGNUP_DATE DATE,
  CUSTOMER_SEGMENT STRING,
  LOAD_TIMESTAMP TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (CUSTOMER_ID)
);

-- Seed data: mimics a customer master feed, since no upstream CRM source exists in this project
INSERT INTO CUSTOMERS (CUSTOMER_ID, CUSTOMER_NAME, EMAIL, REGION_ID, SIGNUP_DATE, CUSTOMER_SEGMENT) VALUES
('CUST001', 'Alice Johnson', 'alice.johnson@example.com', 'REGION_NA', '2024-01-15', 'Retail'),
('CUST002', 'Brian Chen', 'brian.chen@example.com', 'REGION_NA', '2024-02-20', 'Retail'),
('CUST003', 'Carla Diaz', 'carla.diaz@example.com', 'REGION_EU', '2024-03-05', 'Wholesale'),
('CUST004', 'David Smith', 'david.smith@example.com', 'REGION_EU', '2024-04-11', 'Retail'),
('CUST005', 'Emma Wilson', 'emma.wilson@example.com', 'REGION_APAC', '2024-05-30', 'Wholesale');
