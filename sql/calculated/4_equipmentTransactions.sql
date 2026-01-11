(
    SELECT `equipmentId`,
        `equipmentName`,
        `totalPrice` AS amount,
        cast(bookingInvoiceDate AS date) AS `transactionDate`,
        bookingName as comment
    FROM `rn-admin-391316.raw_backstage2.equipmentUsage`
    WHERE bookingInvoiceDate IS NOT NULL
        AND equipmentId IS NOT NULL
        AND bookingFixedPrice IS NULL
)
UNION ALL
(
    SELECT `equipmentId`,
        `equipmentName`,
        -(amount),
        `investmentDate` AS `transactionDate`,
        comment
    FROM `rn-admin-391316.raw_spreadsheet.equipment_investments`
)
UNION ALL
(
    SELECT `equipmentId`,
        `equipmentName`,
        (amount),
        `investmentDate` AS `transactionDate`,
        comment
    FROM `rn-admin-391316.raw_spreadsheet.equipment_stage1_income`
    WHERE equipmentId IS NOT NULL
)
ORDER BY transactionDate