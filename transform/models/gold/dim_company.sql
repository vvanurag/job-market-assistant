{#
    One row per company, after name normalisation (FR-TRN-04). Key: company_key.
    company_name is the most common original spelling, for display.
#}

with names as (

    select
        {{ normalize_company('company_name') }} as normalized_name,
        company_name,
        count(*) as postings
    from {{ ref('slv_postings') }}
    group by 1, 2

)

select
    md5(normalized_name)  as company_key,
    normalized_name,
    company_name,
    count(*) over (partition by normalized_name) as spelling_variants
from names
qualify row_number() over (partition by normalized_name order by postings desc, company_name) = 1
