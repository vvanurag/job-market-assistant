{#
    Posting history as slowly changing dimension Type 2 records (FR-TRN-08), with
    closed postings detected from missed runs (FR-TRN-09).

    Grain: one row per (posting_key, version_number).

    Built from every Bronze delivery, not from snapshots, so it can be rebuilt from
    scratch at any time and gives the same result on every engine.

      1. runs          each source's collection runs (batches), numbered in order
      2. grid          every posting x every run of its source since it was first seen
      3. observed      was the posting returned in that run? If not, how many runs in a
                       row has it been missing? Missing for closed_after_missed_runs
                       runs or more means 'closed'. A posting that comes back reopens.
      4. versions      a new version starts whenever status, title, location or
                       description changes; valid_to is the start of the next version.
#}

{%- set missed_runs_to_close = var('closed_after_missed_runs') -%}

with deliveries as (

    select
        md5(source_id || '|' || source_posting_id) as posting_key,
        source_id,
        batch_id,
        title,
        location_raw,
        md5(coalesce(description_raw, ''))          as description_hash
    from {{ ref('stg_postings') }}
    -- streamed batches hold only new postings, so they aren't full runs: counting them
    -- would make every other posting look "missed" (ADR-0009)
    where batch_id not like 'stream-%'

),

runs as (

    select
        source_id,
        batch_id,
        row_number() over (partition by source_id order by batch_id) as run_number,
        run_started_at
    from (
        select source_id, batch_id, min(loaded_at) as run_started_at
        from {{ ref('stg_postings') }}
        where batch_id not like 'stream-%'
        group by source_id, batch_id
    ) as batches

),

first_seen as (

    select d.posting_key, d.source_id, min(r.run_number) as first_run_number
    from deliveries as d
    inner join runs as r on r.source_id = d.source_id and r.batch_id = d.batch_id
    where d.posting_key in (select posting_key from {{ ref('slv_postings') }})
    group by d.posting_key, d.source_id

),

grid as (

    select
        f.posting_key,
        r.run_number,
        r.run_started_at,
        d.posting_key is not null as was_returned,
        d.title,
        d.location_raw,
        d.description_hash
    from first_seen as f
    inner join runs as r
        on r.source_id = f.source_id and r.run_number >= f.first_run_number
    left join deliveries as d
        on d.posting_key = f.posting_key and d.batch_id = r.batch_id

),

last_returned as (

    select
        *,
        max(case when was_returned then run_number end) over (
            partition by posting_key order by run_number
            rows between unbounded preceding and current row
        ) as last_returned_run
    from grid

),

observed as (

    select
        l.posting_key,
        l.run_number,
        l.run_started_at,
        l.run_number - l.last_returned_run              as runs_missed,
        case
            when l.run_number - l.last_returned_run >= {{ missed_runs_to_close }} then 'closed'
            else 'open'
        end                                             as status,
        -- attributes as last returned by the source
        seen.title,
        seen.location_raw,
        seen.description_hash
    from last_returned as l
    inner join grid as seen
        on seen.posting_key = l.posting_key and seen.run_number = l.last_returned_run

),

changes as (

    select
        *,
        md5(status || '|' || coalesce(title, '') || '|' || coalesce(location_raw, '') || '|' || description_hash)
            as attributes_hash
    from observed

),

flagged as (

    select
        *,
        case
            when lag(attributes_hash) over (partition by posting_key order by run_number) = attributes_hash then 0
            else 1
        end as starts_version
    from changes

),

numbered as (

    select
        *,
        sum(starts_version) over (
            partition by posting_key order by run_number
            rows between unbounded preceding and current row
        ) as version_number
    from flagged

),

versions as (

    select
        posting_key,
        version_number,
        min(run_started_at)     as valid_from,
        max(case when runs_missed = 0 then run_started_at end) as last_returned_at,
        min(run_number)         as from_run_number,
        max(run_number)         as to_run_number,
        max(status)             as status,
        max(title)              as title,
        max(location_raw)       as location_raw,
        max(description_hash)   as description_hash
    from numbered
    group by posting_key, version_number

)

select
    md5(posting_key || '|' || cast(version_number as varchar)) as posting_version_key,
    posting_key,
    version_number,
    status,
    title,
    location_raw,
    description_hash,
    valid_from,
    last_returned_at,
    lead(valid_from) over (partition by posting_key order by version_number) as valid_to,
    lead(valid_from) over (partition by posting_key order by version_number) is null as is_current,
    from_run_number,
    to_run_number
from versions
