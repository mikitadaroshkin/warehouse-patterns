-- SCD Type-2 history: the full version trail for the first three customers that
-- have more than one version. Each row is one validity interval [valid_from,
-- valid_to); exactly one row per customer is is_current = true, and the intervals
-- tile the timeline with no gaps. This is what lets the warehouse answer "what
-- did this customer look like *at the time of the sale*".
WITH versioned AS (
    SELECT customer_id
    FROM dim_customer
    GROUP BY customer_id
    HAVING COUNT(*) > 1
    ORDER BY customer_id
    LIMIT 3
)
SELECT
    customer_key,
    customer_id,
    segment,
    city,
    region,
    valid_from,
    valid_to,
    is_current,
    version
FROM dim_customer
WHERE customer_id IN (SELECT customer_id FROM versioned)
ORDER BY customer_id, version;
