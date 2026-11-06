{#
    One row per unique job with everything the retrieval index needs (Phase 5):
    the cleaned description (personal data already removed, NFR-15) and the metadata
    each chunk carries (FR-IDX-02). The serving role reads Gold only, so this is
    where the index and the API get posting text.

    document_hash changes only when text the index embeds changes; status and other
    metadata can change without re-embedding (FR-IDX-04).
#}

with skills as (

    select posting_key, {{ string_agg_sorted('skill_name', '|') }} as skills
    from {{ ref('slv_posting_skills') }}
    group by posting_key

)

select
    f.posting_key,
    f.title,
    c.company_name,
    l.city,
    l.is_remote                                       as is_remote_india,
    f.work_mode,
    f.seniority,
    f.min_years_experience,
    f.status,
    f.posted_date,
    f.first_seen_at,
    f.last_seen_at,
    f.url,
    f.source_key,
    coalesce(s.skills, '')                            as skills,
    p.description_text,
    md5(f.title || '|' || c.company_name || '|' || l.city || '|' || p.description_text) as document_hash
from {{ ref('fct_postings') }} as f
inner join {{ ref('dim_company') }} as c on c.company_key = f.company_key
inner join {{ ref('dim_location') }} as l on l.location_key = f.location_key
inner join {{ ref('slv_postings') }} as p on p.posting_key = f.posting_key
left join skills as s on s.posting_key = f.posting_key
