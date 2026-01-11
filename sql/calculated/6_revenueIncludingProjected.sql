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
        and bookingStatus != 'Inställd'
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
        and bookingStatus != 'Inställd'
    UNION ALL
    SELECT id as bookingId,
        name as bookingName,
        pricePlan as bookingPricePlan,
        accountKind as bookingAccountKind,
        bookingType,
        invoiceDate as bookingInvoiceDate,
        operationalYear as bookingOperationalYear,
        fiscalYear as bookingFiscalYear,
        "Tidsestimat" as `name`,
        case
            when accountKind = "Normal" then 3620
            when accountKind = "Intern" then 7900
        end as account,
        totalTimeEstimatesPrice as amount,
        'timeEstimate' as revenueType
    FROM `rn-admin-391316.raw_backstage2.booking`
    WHERE fixedPrice is null
        and status != 'Inställd'
)
SELECT revenue.*,
    booking.created as bookingCreated,
    booking.usageStartDatetime as bookingUsageStartDatetime
FROM revenue
    LEFT JOIN `rn-admin-391316.raw_backstage2.booking` AS booking ON revenue.bookingId = booking.id