-- Populate the date dimension in-engine. A date dimension is pure calendar math,
-- so SQL builds it directly rather than loading it from a source: expand a day
-- range and derive the reporting attributes. Regenerating it is deterministic
-- and covers the whole fact date span with one row per day.
INSERT INTO dim_date
SELECT
    year(d) * 10000 + month(d) * 100 + day(d)  AS date_key,   -- YYYYMMDD smart key
    d                                          AS full_date,
    day(d)                                     AS day_of_month,
    dayname(d)                                 AS day_name,
    isodow(d)                                  AS day_of_week,  -- 1=Mon ... 7=Sun
    isodow(d) >= 6                             AS is_weekend,
    month(d)                                   AS month_number,
    monthname(d)                               AS month_name,
    quarter(d)                                 AS quarter,
    year(d)                                    AS year,
    strftime(d, '%Y-%m')                       AS year_month
FROM (
    SELECT UNNEST(generate_series(?::DATE, ?::DATE, INTERVAL 1 DAY)) AS d
) calendar
ORDER BY date_key;
