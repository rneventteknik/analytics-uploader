WITH revenue AS (
    SELECT bookingId,
        bookingName,
        bookingPricePlan,
        bookingAccountKind,
        bookingType,
        bookingInvoiceDate,
        bookingOperationalYear,
        bookingFiscalYear,
        `name`,
        account,
        totalPrice as amount,
        'equipment' as revenueType
    FROM `rn-admin-391316.raw_backstage2.equipmentUsage` AS equipmentUsage
    WHERE bookingFixedPrice is null
        and bookingStatus = 'Klar'
    UNION ALL
    SELECT bookingId,
        bookingName,
        bookingPricePlan,
        bookingAccountKind,
        bookingType,
        bookingInvoiceDate,
        bookingOperationalYear,
        bookingFiscalYear,
        userName as `name`,
        account,
        totalPrice as amount,
        'timeReport' as revenueType
    FROM `rn-admin-391316.raw_backstage2.timeReport`
    WHERE bookingFixedPrice is null
        and bookingStatus = 'Klar'
)
SELECT revenue.*,
    booking.created as bookingCreated
FROM revenue
    LEFT JOIN `rn-admin-391316.raw_backstage2.booking` AS booking ON revenue.bookingId = booking.id