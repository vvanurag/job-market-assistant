{#
    Staging for Greenhouse Job Board API records. Each Bronze payload wraps the job
    object exactly as returned by the API under "job". Parsed into the common
    staging columns (FR-TRN-01); HTML descriptions are converted to plain text.
#}

with source as (

    select * from {{ source('bronze', 'raw_postings') }}
    where source_id = 'greenhouse'

)

select
    source_id,
    batch_id,
    source_posting_id,
    record_hash,
    loaded_at,
    trim({{ json_str('payload', 'job.title') }})                           as title,
    trim({{ json_str('payload', 'company_name') }})                        as company_name,
    trim({{ json_str('payload', 'job.location.name') }})                   as location_raw,
    {{ html_to_text(json_str('payload', 'job.content')) }}                 as description_raw,
    cast(null as varchar)                                                  as seniority_raw,
    cast(null as varchar)                                                  as employment_type,
    cast(null as varchar)                                                  as industries,
    {{ json_str('payload', 'job.absolute_url') }}                          as url,
    try_cast(left({{ json_str('payload', 'job.first_published') }}, 10) as date) as posted_date,
    cast(null as varchar)                                                  as search_keyword
from source
