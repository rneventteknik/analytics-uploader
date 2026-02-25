WITH booking AS (
    SELECT
        id,
        CASE 
          WHEN fixedPrice IS NOT NULL AND totalEquipmentPrice <> 0 THEN 
            GREATEST(0, fixedPrice - totalTimeReportsPrice)/totalEquipmentPrice
          ELSE NULL
        END AS fixedToEquipmentRatio
    FROM `rn-admin-391316.raw_backstage2.booking`
)

SELECT
    *,
    -- For fixed price equipment, calculate ratio of the fixed price this unit contributes with.
    -- For ordinary priced equipment, use the total_price 
    CASE
        WHEN bookingFixedPrice IS NOT NULL AND fixedToEquipmentRatio IS NOT NULL THEN
            round(fixedToEquipmentRatio * totalPrice, 2) -- totalPrice price of all units of the same equipment
        ELSE
            totalPrice
    END AS totalPriceNormalized
FROM `rn-admin-391316.raw_backstage2.equipmentUsage` AS eu
LEFT JOIN booking ON eu.bookingId = booking.id
