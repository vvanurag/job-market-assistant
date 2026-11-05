{#
    Seniority and work mode for each posting (FR-TRN-06).

    Grain: one row per posting_key in slv_postings.

    Both are inferred with maintained, ordered rules (seeds/seniority_rules.csv and
    seeds/work_mode_rules.csv). Each posting takes the first rule that matches, by
    rule_order, and records which kind of evidence decided it (the *_basis columns),
    so every value can be explained and checked.

    Seniority
      1. title rules      "Senior", "Lead", "Engineer II", "Intern"...
      2. source rules     the source's own level, only where it names a single level
      3. experience       minimum years asked for in the description, banded:
                          0-1 junior, 2-4 mid, 5-7 senior, 8-20 lead
      4. otherwise        'unknown'

    Work mode
      1. title or location  "Remote - Bengaluru", "(Hybrid)"
      2. labelled phrases   "Work mode: Hybrid"
      3. other phrases      "3 days a week in the office", "fully remote"
      4. otherwise          'unknown'

    Rule patterns are matched as whole words, like the skill dictionary.
#}

{%- set number_of_years = "([0-9]{1,2})[[:space:]]*([+]|plus)?[[:space:]]*((-|–|to)[[:space:]]*[0-9]{1,2}[[:space:]]*[+]?[[:space:]]*)?(years?|yrs?)" -%}
{#- "5+ years of hands-on experience", "3-6 yrs relevant experience" -#}
{%- set years_then_experience = number_of_years ~ "[^.;]{0,40}experience" -%}
{#- "Experience: 8-15 years", "Experience of 4+ years" -#}
{%- set experience_then_years = "experience[^.;0-9]{0,30}" ~ number_of_years -%}

with postings as (

    select
        posting_key,
        lower(title)                                     as title_text,
        lower(coalesce(seniority_raw, ''))               as source_text,
        lower(title || ' | ' || coalesce(location_raw, '')) as title_location_text,
        lower(description_text)                          as description_text
    from {{ ref('slv_postings') }}

),

seniority_rules as (

    select
        rule_order,
        seniority,
        field,
        '(^|[^a-z0-9])(' || pattern || ')([^a-z0-9]|$)' as whole_word_pattern
    from {{ ref('seniority_rules') }}

),

work_mode_rules as (

    select
        rule_order,
        work_mode,
        field,
        '(^|[^a-z0-9])(' || pattern || ')([^a-z0-9]|$)' as whole_word_pattern
    from {{ ref('work_mode_rules') }}

),

seniority_hits as (

    select
        p.posting_key,
        r.seniority,
        r.field as seniority_basis,
        row_number() over (partition by p.posting_key order by r.rule_order) as hit_rank
    from postings as p
    cross join seniority_rules as r
    where {{ matches_column(
        "case r.field when 'title' then p.title_text when 'source' then p.source_text end",
        'r.whole_word_pattern'
    ) }}

),

work_mode_hits as (

    select
        p.posting_key,
        r.work_mode,
        r.field as work_mode_basis,
        row_number() over (partition by p.posting_key order by r.rule_order) as hit_rank
    from postings as p
    cross join work_mode_rules as r
    where {{ matches_column(
        "case r.field when 'title_location' then p.title_location_text when 'description' then p.description_text end",
        'r.whole_word_pattern'
    ) }}

),

experience_phrases as (

    select
        posting_key,
        coalesce(
            {{ extract_match('description_text', years_then_experience) }},
            {{ extract_match('description_text', experience_then_years) }}
        ) as experience_phrase
    from postings

),

experience as (

    select
        posting_key,
        experience_phrase,
        -- The first number in the phrase is the minimum: "4-8 years" gives 4.
        -- More than 20 years is almost always about the company, not the role.
        case
            when cast({{ extract_match('experience_phrase', '[0-9]{1,2}') }} as integer) <= 20
                then cast({{ extract_match('experience_phrase', '[0-9]{1,2}') }} as integer)
        end as min_years_experience
    from experience_phrases

)

select
    p.posting_key,
    coalesce(
        s.seniority,
        case
            when e.min_years_experience <= 1 then 'junior'
            when e.min_years_experience <= 4 then 'mid'
            when e.min_years_experience <= 7 then 'senior'
            when e.min_years_experience <= 20 then 'lead'
        end,
        'unknown'
    )                                                         as seniority,
    case
        when s.seniority is not null then s.seniority_basis
        when e.min_years_experience is not null then 'experience'
        else 'none'
    end                                                       as seniority_basis,
    e.min_years_experience,
    e.experience_phrase,
    coalesce(w.work_mode, 'unknown')                          as work_mode,
    coalesce(w.work_mode_basis, 'none')                       as work_mode_basis
from postings as p
left join seniority_hits as s
    on s.posting_key = p.posting_key and s.hit_rank = 1
left join work_mode_hits as w
    on w.posting_key = p.posting_key and w.hit_rank = 1
left join experience as e
    on e.posting_key = p.posting_key
