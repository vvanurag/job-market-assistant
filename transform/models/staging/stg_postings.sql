{#
    All sources in one shape. Each source has its own staging model because raw
    formats differ; this view combines them so Silver doesn't need to care where a
    posting came from. To add a source: add stg_postings__<source> with the same
    columns and list it here.
#}

{% set sources = ['stg_postings__backfill', 'stg_postings__greenhouse'] %}

{% for model in sources %}
select
    source_id,
    batch_id,
    source_posting_id,
    record_hash,
    loaded_at,
    title,
    company_name,
    location_raw,
    description_raw,
    seniority_raw,
    employment_type,
    industries,
    url,
    posted_date,
    search_keyword
from {{ ref(model) }}
{% if not loop.last %}union all{% endif %}
{% endfor %}
