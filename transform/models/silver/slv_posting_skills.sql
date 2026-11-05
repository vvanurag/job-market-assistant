{#
    Skills mentioned in each posting (FR-TRN-05), found with the maintained skill
    dictionary in seeds/skills.csv.

    Grain: one row per (posting_key, skill_id).

    Each skill's pattern is matched as a whole word or phrase in the lowercase title and
    description: the characters on either side must not be letters or digits, so "sql"
    matches "SQL," but not "MySQL", and "java" doesn't match "JavaScript".
#}

with postings as (

    select
        posting_key,
        lower(title || ' ' || description_text) as text
    from {{ ref('slv_postings') }}

),

skills as (

    select
        skill_id,
        skill_name,
        category,
        '(^|[^a-z0-9])(' || pattern || ')([^a-z0-9]|$)' as whole_word_pattern
    from {{ ref('skills') }}

)

select
    p.posting_key,
    s.skill_id,
    s.skill_name,
    s.category,
    'dictionary' as extraction_method
from postings as p
cross join skills as s
where {{ matches_column('p.text', 's.whole_word_pattern') }}
