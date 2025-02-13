SELECT 
    equipmentName, 
    -investment as amount, 
    cast(datetime as timestamp) as date, 
    'investment' as type, 
    comment 
FROM `rn-admin-391316.raw_google_drive.investments` i

UNION ALL

SELECT 
    e.equipmentName, 
    e.totalPrice as amount, 
    e.usageStartDatetime as date, 
    'booking' as type, 
    e.bookingName as comment 
FROM `rn-admin-391316.raw_backstage2.equipmentUsage` e
JOIN `rn-admin-391316.raw_backstage2.booking` b on e.bookingId = b.id
WHERE 1=1
  and e.Account in (3550, 4900) 
  and e.equipmentName in (SELECT distinct equipmentName from `rn-admin-391316.raw_google_drive.investments`)
  and b.fixedPrice is null
  and b.status = 'Klar'