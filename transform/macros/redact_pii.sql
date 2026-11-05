{#
    Remove personal contact details from free text before it reaches Silver (NFR-15).
    Patterns avoid backslashes so they behave identically in DuckDB and Snowflake.

    - Email addresses
    - Indian mobile numbers: optional +91, then 10 digits starting 6-9,
      optionally split 5+5 by a space or hyphen
#}
{% macro redact_pii(column) -%}
    {{ replace_all(
        replace_all(column, pii_email_pattern(), '[email removed]'),
        pii_phone_pattern(),
        '[phone removed]'
    ) }}
{%- endmacro %}

{# The same patterns, for tests that check nothing slipped through #}
{% macro pii_email_pattern() %}[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+[.][A-Za-z]{2,}{% endmacro %}
{% macro pii_phone_pattern() %}([+]91[ -]?)?[6-9][0-9]{4}[ -]?[0-9]{5}{% endmacro %}
