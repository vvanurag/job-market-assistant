{#
    One row per (unique job, skill). The job's company, city and date keys are copied
    onto each row so common questions ("top skills in Bengaluru this month") need no
    extra joins.
#}

select
    f.posting_key,
    s.skill_id        as skill_key,
    f.company_key,
    f.location_key,
    f.posted_date_key
from {{ ref('fct_postings') }} as f
inner join {{ ref('slv_posting_skills') }} as s
    on s.posting_key = f.posting_key
