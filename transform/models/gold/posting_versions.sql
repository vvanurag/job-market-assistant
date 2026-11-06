{#
    History of each unique job for the API (US-10): one row per version of the job's
    representative posting. Key: posting_version_key. Copied from Silver because the
    serving role reads Gold only (NFR-12).
#}

select
    h.posting_version_key,
    h.posting_key,
    h.version_number,
    h.status,
    h.title,
    h.location_raw,
    h.description_hash,
    h.valid_from,
    h.valid_to,
    h.is_current
from {{ ref('slv_posting_history') }} as h
where h.posting_key in (select posting_key from {{ ref('fct_postings') }})
