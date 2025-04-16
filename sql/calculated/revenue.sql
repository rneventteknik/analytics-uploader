SELECT 
  bookingId,
  bookingName,
  bookingPricePlan,
  bookingAccountKind,
  bookingType,
  name,
  equipmentInDatetime as invoiceDate,
  account,
  totalPrice as amount,
  'equipment' as revenueType
FROM `rn-admin-391316.raw_backstage2.equipmentUsage`
WHERE bookingFixedPrice is null and bookingStatus = 'Klar'

UNION ALL

SELECT 
  bookingId,
  bookingName,
  bookingPricePlan,
  bookingAccountKind,
  bookingType,
  userName as name,
  endDatetime as invoiceDate,
  account,
  totalPrice as amount,
  'timeReport' as revenueType
FROM `rn-admin-391316.raw_backstage2.timeReport`
WHERE bookingFixedPrice is null and bookingStatus = 'Klar'
