-- Every repost group must have exactly one canonical posting.

select content_fingerprint, count_if(is_canonical) as canonical_rows
from {{ ref('slv_postings') }}
group by content_fingerprint
having count_if(is_canonical) <> 1
