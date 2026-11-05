{# One row per calendar day. Key: date_key as YYYYMMDD. #}

with days as (

    {{ date_spine(var('date_spine_start'), var('date_spine_end')) }}

)

select
    {{ date_key("date_day") }}                                     as date_key,
    date_day,
    year(date_day)                                                 as year,
    quarter(date_day)                                              as quarter,
    month(date_day)                                                as month,
    cast(date_trunc('month', date_day) as date)                    as month_start,
    cast(date_trunc('week', date_day) as date)                     as week_start,
    {{ iso_day_of_week('date_day') }}                              as day_of_week,
    {{ iso_day_of_week('date_day') }} in (6, 7)                    as is_weekend
from days
