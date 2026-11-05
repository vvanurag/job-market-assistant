{# One row per target city. Key: location_key. #}

select
    lower(city) as location_key,
    city,
    case city when 'Hyderabad' then 'Telangana' when 'Bengaluru' then 'Karnataka' end as state,
    'India' as country
from (select distinct city from {{ ref('city_aliases') }}) as cities
