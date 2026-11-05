{# One row per skill in the dictionary. Key: skill_key. #}

select
    skill_id as skill_key,
    skill_name,
    category
from {{ ref('skills') }}
