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


{# matches_column(expression, pattern_expression): like matches(), but the regex comes from a column #}
{% macro matches_column(expression, pattern_expression) -%}
    {{ return(adapter.dispatch('matches_column', 'jobmarket')(expression, pattern_expression)) }}
{%- endmacro %}

{% macro default__matches_column(expression, pattern_expression) -%}
    regexp_matches({{ expression }}, {{ pattern_expression }})
{%- endmacro %}

{% macro snowflake__matches_column(expression, pattern_expression) -%}
    regexp_instr({{ expression }}, {{ pattern_expression }}) > 0
{%- endmacro %}


{# date_spine(start, end): one row per calendar day, column "date_day" #}
{% macro date_spine(start_date, end_date) -%}
    {{ return(adapter.dispatch('date_spine', 'jobmarket')(start_date, end_date)) }}
{%- endmacro %}

{% macro default__date_spine(start_date, end_date) -%}
    select cast(range as date) as date_day
    from range(date '{{ start_date }}', date '{{ end_date }}' + interval 1 day, interval 1 day)
{%- endmacro %}

{% macro snowflake__date_spine(start_date, end_date) -%}
    select dateadd(day, row_number() over (order by seq4()) - 1, '{{ start_date }}'::date) as date_day
    from table(generator(rowcount => 20000))
    qualify date_day <= '{{ end_date }}'::date
{%- endmacro %}


{# iso_day_of_week(date): 1 = Monday ... 7 = Sunday #}
{% macro iso_day_of_week(expression) -%}
    {{ return(adapter.dispatch('iso_day_of_week', 'jobmarket')(expression)) }}
{%- endmacro %}

{% macro default__iso_day_of_week(expression) -%}
    isodow({{ expression }})
{%- endmacro %}

{% macro snowflake__iso_day_of_week(expression) -%}
    dayofweekiso({{ expression }})
{%- endmacro %}


{# date_key(date): integer YYYYMMDD, the key of dim_date #}
{% macro date_key(expression) -%}
    (year({{ expression }}) * 10000 + month({{ expression }}) * 100 + day({{ expression }}))
{%- endmacro %}


{# extract_match(expression, pattern): the first text matching the regex, or NULL #}
{% macro extract_match(expression, pattern) -%}
    {{ return(adapter.dispatch('extract_match', 'jobmarket')(expression, pattern)) }}
{%- endmacro %}

{% macro default__extract_match(expression, pattern) -%}
    nullif(regexp_extract({{ expression }}, '{{ pattern }}', 0), '')
{%- endmacro %}

{% macro snowflake__extract_match(expression, pattern) -%}
    regexp_substr({{ expression }}, '{{ pattern }}')
{%- endmacro %}
