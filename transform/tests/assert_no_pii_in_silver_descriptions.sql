-- NFR-15: no email address or Indian mobile number may remain in Silver text.
-- A test passes when it returns no rows.

select posting_key, 'email' as found
from {{ ref('slv_postings') }}
where {{ matches('description_text', pii_email_pattern()) }}

union all

select posting_key, 'phone' as found
from {{ ref('slv_postings') }}
where {{ matches('description_text', pii_phone_pattern()) }}
