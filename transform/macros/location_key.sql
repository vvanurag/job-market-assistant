{# location_key(city): the key of dim_location, e.g. 'hyderabad', 'remote_india' #}
{% macro location_key(city) -%}
    trim({{ replace_all('lower(' ~ city ~ ')', '[^a-z]+', '_') }}, '_')
{%- endmacro %}
