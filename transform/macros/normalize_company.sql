{#
    normalize_company(column): a matching key for company names (FR-TRN-04), so that
    "Accenture in India", "ACCENTURE" and "Accenture Pvt. Ltd." resolve to one company.

    lowercase -> punctuation to spaces -> drop "in india" / "india" at the end ->
    drop legal suffixes (run twice, for pairs like "pvt ltd") -> collapse spaces.
#}
{% macro normalize_company(column) -%}
    {%- set suffixes = '( |^)(inc|incorporated|ltd|limited|pvt|private|llc|llp|corp|corporation|co|plc|gmbh)( |$)' -%}
    trim({{ replace_all(
        replace_all(
            replace_all(
                replace_all(
                    replace_all('lower(' ~ column ~ ')', '[^a-z0-9]+', ' '),
                    ' (in )?india *$', ''),
                suffixes, ' '),
            suffixes, ' '),
        ' +', ' ') }})
{%- endmacro %}
