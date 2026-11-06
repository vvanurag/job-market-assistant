{#
    One row per source of postings (FR-TRN-10). Key: source_key.
    Sources listed in seeds/sources.csv get their name and collection schedule from
    there; any other source is the one-off initial backfill.
#}

with sources as (

    select distinct source_id from {{ ref('slv_postings') }}

)

select
    s.source_id                                       as source_key,
    coalesce(m.source_name, 'Initial backfill')       as source_name,
    coalesce(m.collection, 'one-off')                 as collection,
    m.homepage
from sources as s
left join {{ ref('sources') }} as m on m.source_id = s.source_id
