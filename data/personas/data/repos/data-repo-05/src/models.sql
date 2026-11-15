WITH ranked AS (
  SELECT region, month, revenue,
         RANK() OVER (PARTITION BY month ORDER BY revenue DESC) AS rnk
  FROM sales
)
SELECT * FROM ranked WHERE rnk <= 3;


CREATE OR REPLACE WAREHOUSE reporting_wh WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60;
