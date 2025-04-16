SELECT e.*,
    b.fixedPrice,
    b.totalEquipmentPrice,
    b.totalTimeEstimatesPrice,
    b.totalTimeReportsPrice,
    b.ownerUserName
FROM `rn-admin-391316.calculated.bookingsPastAndThisWeek` AS b
    INNER JOIN `rn-admin-391316.raw_backstage2.equipmentUsage` AS e ON b.id = e.bookingId