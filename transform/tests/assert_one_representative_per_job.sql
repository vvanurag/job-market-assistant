-- Every job has exactly one representative posting, and it is the job_key itself.
select job_key
from {{ ref('slv_posting_jobs') }}
group by job_key
having sum(case when is_job_representative then 1 else 0 end) <> 1
    or max(case when is_job_representative then posting_key end) <> job_key
