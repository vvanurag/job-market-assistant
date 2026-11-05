{#
    One row per unique data/AI job: canonical postings only (reposts counted once),
    target roles only. Key: posting_key.

    posted_date falls back to the date the posting was first loaded when the source
    gives no publish date; posted_date_is_estimated records when that happened.
#}

with postings as (

    select
        *,
        coalesce(posted_date, cast(loaded_at as date)) as effective_posted_date,
        posted_date is null                             as posted_date_is_estimated
    from {{ ref('slv_postings') }}
    where is_canonical and is_target_role

),

skill_counts as (

    select posting_key, count(*) as skill_count
    from {{ ref('slv_posting_skills') }}
    group by posting_key

)

select
    p.posting_key,
    md5({{ normalize_company('p.company_name') }})   as company_key,
    lower(p.city)                                     as location_key,
    {{ date_key('p.effective_posted_date') }}         as posted_date_key,
    p.source_id,
    p.source_posting_id,
    p.title,
    p.seniority_raw                                   as seniority,
    p.employment_type,
    p.url,
    p.effective_posted_date                           as posted_date,
    p.posted_date_is_estimated,
    p.copies_in_group - 1                             as repost_count,
    coalesce(s.skill_count, 0)                        as skill_count,
    p.loaded_at
from postings as p
left join skill_counts as s on s.posting_key = p.posting_key
