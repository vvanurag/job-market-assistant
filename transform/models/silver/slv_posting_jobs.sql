{#
    Links every posting to one job (FR-TRN-03): reposts within a source and the same
    role posted on different sources resolve to one job_key.

    Grain: one row per posting_key in slv_postings.

      1. repost groups   slv_postings already groups postings with identical company and
                         description text (content_fingerprint); each group has one
                         canonical posting.
      2. cross-source    two canonical postings from different sources are the same job
                         when all of these are equal:
                           - company (normalised name)
                           - city
                           - title, ignoring case and punctuation
                           - the first and the last 1,000 letters of the description,
                             ignoring everything that isn't a letter (sources format
                             the same text differently: HTML, bullets, line breaks)
                         Matches are one-to-one; a posting matching several candidates
                         keeps the one with the lowest key on the other side.
      3. representative  each job is shown by one posting, preferring a recurring source
                         (its open/closed status is checked every run), then the
                         earliest posted.

    The title is part of the rule because some employers reuse one description for
    several levels ("Senior" and "Staff" roles with the same text are two jobs).
#}

with postings as (

    select
        p.posting_key,
        p.source_id,
        p.city,
        p.posted_date,
        p.canonical_posting_key,
        p.is_canonical,
        {{ normalize_company('p.company_name') }}                                  as company_key,
        trim({{ replace_all('lower(p.title)', '[^a-z0-9]+', ' ') }})               as title_key,
        {{ replace_all('lower(p.description_text)', '[^a-z]+', '') }}              as letters
    from {{ ref('slv_postings') }} as p

),

canonical as (

    select
        posting_key,
        source_id,
        city,
        posted_date,
        company_key,
        title_key,
        left(letters, 1000)  as text_head,
        right(letters, 1000) as text_tail
    from postings
    where is_canonical

),

candidate_pairs as (

    select
        a.posting_key as posting_key_a,
        b.posting_key as posting_key_b
    from canonical as a
    inner join canonical as b
        on  a.source_id < b.source_id
        and a.company_key = b.company_key
        and a.city = b.city
        and a.title_key = b.title_key
        and a.text_head = b.text_head
        and a.text_tail = b.text_tail

),

pairs as (

    -- one-to-one: keep each posting's first match on both sides
    select posting_key_a, posting_key_b
    from (
        select
            *,
            row_number() over (partition by posting_key_a order by posting_key_b) as rank_a,
            row_number() over (partition by posting_key_b order by posting_key_a) as rank_b
        from candidate_pairs
    ) as ranked
    where rank_a = 1 and rank_b = 1

),

groups as (

    -- the job a canonical posting belongs to, named after its smallest member for now
    select
        c.posting_key as canonical_posting_key,
        coalesce(
            case when pa.posting_key_b < c.posting_key then pa.posting_key_b end,
            case when pb.posting_key_a < c.posting_key then pb.posting_key_a end,
            c.posting_key
        ) as group_id,
        pa.posting_key_a is not null or pb.posting_key_b is not null as has_cross_source_match
    from canonical as c
    left join pairs as pa on pa.posting_key_a = c.posting_key
    left join pairs as pb on pb.posting_key_b = c.posting_key

),

members as (

    select
        p.posting_key,
        p.source_id,
        p.posted_date,
        p.is_canonical,
        g.group_id,
        g.has_cross_source_match,
        s.source_id is not null as from_recurring_source
    from postings as p
    inner join groups as g on g.canonical_posting_key = p.canonical_posting_key
    left join {{ ref('sources') }} as s on s.source_id = p.source_id

),

ranked as (

    select
        *,
        first_value(posting_key) over (
            partition by group_id
            order by
                case when is_canonical then 0 else 1 end,
                case when from_recurring_source then 0 else 1 end,
                posted_date nulls last,
                posting_key
        )                                                       as job_key,
        count(*) over (partition by group_id)                   as postings_in_job
    from members

),

group_sources as (

    select group_id, count(distinct source_id) as sources_in_job
    from members
    group by group_id

)

select
    r.posting_key,
    r.job_key,
    r.posting_key = r.job_key as is_job_representative,
    case
        when r.posting_key = r.job_key then 'representative'
        when r.is_canonical then 'cross_source'
        else 'repost'
    end                       as linked_as,
    r.postings_in_job,
    gs.sources_in_job
from ranked as r
inner join group_sources as gs on gs.group_id = r.group_id
