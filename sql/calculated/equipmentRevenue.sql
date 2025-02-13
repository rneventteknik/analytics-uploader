SELECT e.* FROM `rn-admin-391316.raw_backstage2.equipmentUsage` e
  JOIN `rn-admin-391316.raw_backstage2.booking` b on e.bookingId = b.id
  WHERE 1=1
  and e.Account in (3550, 4900) 
  and b.fixedPrice is null
  and b.status = 'Klar'