{# One row per target location: the two cities and remote roles open to India (Q6). Key: location_key. #}

select
    {{ location_key('city') }} as location_key,
    city,
    case city when 'Hyderabad' then 'Telangana' when 'Bengaluru' then 'Karnataka' end as state,
    'India' as country,
    city = 'Remote (India)' as is_remote
from (select distinct city from {{ ref('city_aliases') }}) as cities
