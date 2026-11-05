{#
    Staging for the one-off backfill batch (flat JSON records with search metadata).
    Parses the payload into the common staging columns (FR-TRN-01). No rows are
    removed and nothing is interpreted beyond trimming and type casting.
#}

with source as (

    select * from {{ source('bronze', 'raw_postings') }}
    where source_id <> 'greenhouse'

),

parsed as (

    select
        source_id,
        batch_id,
        source_posting_id,
        record_hash,
        loaded_at,
        {{ json_str('payload', 'title') }}                               as title,
        {{ json_str('payload', 'company') }}                             as company_name,
        {{ json_str('payload', 'location') }}                            as location_raw,
        {{ json_str('payload', 'raw_description') }}                     as description_raw,
        {{ json_str('payload', 'seniority_level') }}                     as seniority_raw,
        {{ json_str('payload', 'employment_type') }}                     as employment_type,
        {{ json_str('payload', 'industries') }}                          as industries,
        {{ json_str('payload', 'job_url') }}                             as url,
        {{ json_str('payload', 'bronze_meta.search_hit.posted_date') }}  as posted_date_raw,
        {{ json_str('payload', 'bronze_meta.search_hit.posted_time') }}  as posted_time_raw,
        {{ json_str('payload', 'bronze_meta.search_hit.query_keyword') }} as search_keyword
    from source

)

select
    source_id,
    batch_id,
    source_posting_id,
    record_hash,
    loaded_at,
    trim(title)                                                as title,
    trim(company_name)                                         as company_name,
    trim(location_raw)                                         as location_raw,
    description_raw,
    nullif(trim(seniority_raw), 'Not Applicable')              as seniority_raw,
    nullif(trim(employment_type), '')                          as employment_type,
    nullif(trim(industries), '')                               as industries,
    url,
    coalesce(
        try_cast(posted_date_raw as date),
        try_cast(left(posted_time_raw, 10) as date)
    )                                                          as posted_date,
    search_keyword
from parsed
