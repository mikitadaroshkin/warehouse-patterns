-- Net revenue by product category by month, pivoted to a compact crosstab for
-- the first half of 2025. This is the canonical star-schema query: the fact is
-- sliced by one dimension (product.category) and rolled up along another
-- (date.year_month), joining only on surrogate keys.
SELECT
    p.category,
    ROUND(SUM(f.net_amount) FILTER (WHERE d.year_month = '2025-01'), 0) AS "2025-01",
    ROUND(SUM(f.net_amount) FILTER (WHERE d.year_month = '2025-02'), 0) AS "2025-02",
    ROUND(SUM(f.net_amount) FILTER (WHERE d.year_month = '2025-03'), 0) AS "2025-03",
    ROUND(SUM(f.net_amount) FILTER (WHERE d.year_month = '2025-04'), 0) AS "2025-04",
    ROUND(SUM(f.net_amount) FILTER (WHERE d.year_month = '2025-05'), 0) AS "2025-05",
    ROUND(SUM(f.net_amount) FILTER (WHERE d.year_month = '2025-06'), 0) AS "2025-06",
    ROUND(SUM(f.net_amount), 0)                                          AS h1_2025_total
FROM fact_sales f
JOIN dim_product p ON f.product_key = p.product_key
JOIN dim_date    d ON f.date_key    = d.date_key
WHERE d.year_month BETWEEN '2025-01' AND '2025-06'
GROUP BY p.category
ORDER BY h1_2025_total DESC;
