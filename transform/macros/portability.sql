{#
    Engine-specific SQL lives only in these macros (ADR-0005). Each has a default
    implementation (DuckDB) and a Snowflake implementation, chosen automatically by
    dbt's adapter.dispatch. Models call the macro and stay portable.
#}

{# json_str(column, path): read a string at a dotted path from a JSON column #}
{% macro json_str(column, path) -%}
    {{ return(adapter.dispatch('json_str', 'jobmarket')(column, path)) }}
{%- endmacro %}

{% macro default__json_str(column, path) -%}
    json_extract_string({{ column }}, '$.{{ path }}')
{%- endmacro %}

{% macro snowflake__json_str(column, path) -%}
    {{ column }}:{{ path }}::varchar
{%- endmacro %}


{# replace_all(expression, pattern, replacement): replace every regex match #}
{% macro replace_all(expression, pattern, replacement) -%}
    {{ return(adapter.dispatch('replace_all', 'jobmarket')(expression, pattern, replacement)) }}
{%- endmacro %}

{% macro default__replace_all(expression, pattern, replacement) -%}
    regexp_replace({{ expression }}, '{{ pattern }}', '{{ replacement }}', 'g')
{%- endmacro %}

{% macro snowflake__replace_all(expression, pattern, replacement) -%}
    regexp_replace({{ expression }}, '{{ pattern }}', '{{ replacement }}')
{%- endmacro %}


{# matches(expression, pattern): true when the regex matches anywhere in the text #}
{% macro matches(expression, pattern) -%}
    {{ return(adapter.dispatch('matches', 'jobmarket')(expression, pattern)) }}
{%- endmacro %}

{% macro default__matches(expression, pattern) -%}
    regexp_matches({{ expression }}, '{{ pattern }}')
{%- endmacro %}

{% macro snowflake__matches(expression, pattern) -%}
    regexp_instr({{ expression }}, '{{ pattern }}') > 0
{%- endmacro %}


{#
    target_role_pattern(): titles in scope (data engineering, analytics engineering,
    ML and AI engineering). Lowercase; spaces stand in for word boundaries so the
    pattern needs no backslashes and behaves the same in DuckDB and Snowflake.
#}
{% macro target_role_pattern() -%}
(^|[^a-z])(data|ml|mlops|ai|llm|genai|etl|elt|bi|nlp|rag)([^a-z]|$)|machine learning|artificial intelligence|generative|analytics|big data|snowflake|databricks|spark|hadoop|kafka|airflow|warehouse|lakehouse|deep learning|computer vision
{%- endmacro %}
