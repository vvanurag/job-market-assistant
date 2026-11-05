{#
    Silver postings: cleaned, located, privacy-safe and duplicate-aware.

    Grain: one row per posting per source (source_id, source_posting_id).

    Steps
      1. latest         keep the most recent delivery of each posting (FR-TRN-02)
      2. city_matches   resolve the location to Hyderabad or Bengaluru (FR-TRN-12)
      3. cleaned        remove emails and phone numbers from the text (NFR-15)
      4. fingerprinted  identify reposts: same company and same description text
      5. final          link every repost to one canonical posting; flag target roles

    Rows are flagged, not deleted: Gold decides whether to use only canonical rows.
#}

with staged as (

    select * from {{ ref('stg_postings') }}

),

latest as (

    select *
    from staged
    qualify row_number() over (
        partition by source_id, source_posting_id
        order by loaded_at desc, batch_id desc
    ) = 1

),

city_matches as (

    select
        l.source_id,
        l.source_posting_id,
        a.city,
        a.match_level,
        row_number() over (
            partition by l.source_id, l.source_posting_id
            order by case a.match_level when 'city' then 1 when 'area' then 2 else 3 end, a.alias
        ) as match_rank
    from latest as l
    inner join {{ ref('city_aliases') }} as a
        on contains(lower(l.location_raw), a.alias)

),

cleaned as (

    select
        l.source_id,
        l.batch_id,
        l.source_posting_id,
        l.record_hash,
        l.loaded_at,
        l.title,
        l.company_name,
        l.location_raw,
        c.city,
        c.match_level                                as city_match_level,
        {{ redact_pii('l.description_raw') }}        as description_text,
        l.seniority_raw,
        l.employment_type,
        l.industries,
        l.url,
        l.posted_date,
        l.search_keyword
    from latest as l
    inner join city_matches as c
        on  c.source_id = l.source_id
        and c.source_posting_id = l.source_posting_id
        and c.match_rank = 1

),

fingerprinted as (

    select
        *,
        md5(source_id || '|' || source_posting_id) as posting_key,
        md5(
            lower(trim(company_name)) || '|'
            || trim({{ replace_all('lower(description_text)', '[[:space:]]+', ' ') }})
        )                                           as content_fingerprint
    from cleaned

),

final as (

    select
        posting_key,
        source_id,
        source_posting_id,
        batch_id,
        title,
        company_name,
        city,
        city_match_level,
        location_raw,
        seniority_raw,
        employment_type,
        industries,
        posted_date,
        description_text,
        url,
        search_keyword,
        {{ matches('lower(title)', target_role_pattern()) }} as is_target_role,
        content_fingerprint,
        first_value(posting_key) over (
            partition by content_fingerprint
            order by posted_date nulls last, source_posting_id
        )                                           as canonical_posting_key,
        count(*) over (partition by content_fingerprint) as copies_in_group,
        record_hash,
        loaded_at
    from fingerprinted

)

select
    *,
    posting_key = canonical_posting_key as is_canonical
from final
