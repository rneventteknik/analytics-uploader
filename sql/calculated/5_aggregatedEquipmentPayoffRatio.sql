-- Aggregate revenue and cost per equipment
WITH rev_cost AS (
    SELECT equipmentId,
        ANY_VALUE(equipmentName) as equipmentName,
        -- Sum ONLY positive amounts → treat these as revenue
        SUM(
            CASE
                WHEN amount > 0 THEN amount
                ELSE 0
            END
        ) AS revenue,
        -- Sum ONLY negative amounts → treat these as cost
        -- (Values remain negative here)
        SUM(
            CASE
                WHEN amount < 0 THEN amount
                ELSE 0
            END
        ) AS cost
    FROM `rn-admin-391316.calculated.equipmentTransactions`
    GROUP BY equipmentId
)
SELECT *,
    -- Compute the payback ratio:
    -- ratio = revenue / cost (converted to positive)
    -- Special handling for edge cases:
    -- 1. If both revenue and cost are zero → ratio = 0 (avoid divide-by-zero)
    -- 2. If cost is zero → divide revenue by revenue (ratio = 1)
    -- 3. Otherwise divide revenue by (-cost) since cost is negative in source data
    CASE
        WHEN revenue = 0
        AND cost = 0 THEN 0
        ELSE revenue / CASE
            WHEN cost = 0 THEN revenue -- avoid division by zero
            ELSE - cost -- convert negative cost to positive
        END
    END AS ratio
FROM rev_cost;