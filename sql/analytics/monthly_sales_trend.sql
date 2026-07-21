-- Monthly trend across the whole fact. Because the grain is one order line, the
-- measures are fully additive: SUM over any month is meaningful, and COUNT(*)
-- is the number of order lines. A quick sanity check that the fact loaded at the
-- grain we declared.
SELECT
    d.year_month,
    COUNT(*)                       AS order_lines,
    SUM(f.quantity)                AS units,
    ROUND(SUM(f.net_amount), 0)    AS net_revenue
FROM fact_sales f
JOIN dim_date d ON f.date_key = d.date_key
GROUP BY d.year_month
ORDER BY d.year_month;
