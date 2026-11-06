{#
    One row per unique data/AI job, target roles only. Key: posting_key.

    Each job appears once, shown by its representative posting (slv_posting_jobs):
    reposts and the same role found on several sources are counted once (FR-TRN-03).
    status comes from the representative; first and last seen span every copy.

    posted_date falls back to the date the posting was first loaded when the source
    gives no publish date; posted_date_is_estimated records when that happened.
#}

with postings as (

    select
        *,
        coalesce(posted_date, cast(loaded_at as date)) as effective_posted_date,
        posted_date is null                             as posted_date_is_estimated
    from {{ ref('slv_postings') }}
    where is_target_role
      and posting_key in (select job_key from {{ ref('slv_posting_jobs') }})

),

jobs as (

    select * from {{ ref('slv_posting_jobs') }}

),

posting_history as (

    select
        posting_key,
        min(valid_from)                                        as first_seen_at,
        max(last_returned_at)                                  as last_seen_at,
        max(case when is_current then status end)              as status,
        count(*)                                               as version_count
    from {{ ref('slv_posting_history') }}
    group by posting_key

),

history as (

    -- status and versions of the representative; first and last seen across all copies
    select
        j.job_key                                                          as posting_key,
        max(case when j.is_job_representative then h.status end)           as status,
        max(case when j.is_job_representative then h.version_count end)    as version_count,
        min(h.first_seen_at)                                               as first_seen_at,
        max(h.last_seen_at)                                                as last_seen_at,
        max(j.postings_in_job)                                             as postings_in_job,
        max(j.sources_in_job)                                              as sources_in_job
    from jobs as j
    inner join posting_history as h on h.posting_key = j.posting_key
    group by j.job_key

),

skill_counts as (

    select posting_key, count(*) as skill_count
    from {{ ref('slv_posting_skills') }}
    group by posting_key

)

select
    p.posting_key,
    md5({{ normalize_company('p.company_name') }})   as company_key,
    {{ location_key('p.city') }}                      as location_key,
    {{ date_key('p.effective_posted_date') }}         as posted_date_key,
    p.source_id                                       as source_key,
    p.source_posting_id,
    p.title,
    h.status,
    h.first_seen_at,
    h.last_seen_at,
    h.version_count,
    a.seniority,
    a.seniority_basis,
    a.min_years_experience,
    a.work_mode,
    a.work_mode_basis,
    p.employment_type,
    p.url,
    p.effective_posted_date                           as posted_date,
    p.posted_date_is_estimated,
    h.postings_in_job - 1                             as repost_count,
    h.sources_in_job,
    coalesce(s.skill_count, 0)                        as skill_count,
    p.loaded_at
from postings as p
left join skill_counts as s on s.posting_key = p.posting_key
inner join {{ ref('slv_posting_attributes') }} as a on a.posting_key = p.posting_key
inner join history as h on h.posting_key = p.posting_key
