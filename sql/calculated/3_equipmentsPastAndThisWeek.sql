SELECT e.*,
    b.fixedPrice,
    b.totalEquipmentPrice,
    b.totalTimeEstimatesPrice,
    b.totalTimeReportsPrice,
    b.ownerUserName
FROM `rn-admin-391316.raw_backstage2.booking` AS b
INNER JOIN `rn-admin-391316.calculated.equipmentUsageNormalized` AS e ON b.id = e.bookingId
WHERE CAST(e.usageStartDatetime AS DATE) BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
    AND DATE_ADD(CURRENT_DATE(), INTERVAL 7 DAY)