WITH ranked AS (
  SELECT region, month, revenue,
         RANK() OVER (PARTITION BY month ORDER BY revenue DESC) AS rnk
  FROM sales
)
SELECT * FROM ranked WHERE rnk <= 3;
