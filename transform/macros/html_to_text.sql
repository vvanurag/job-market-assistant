{#
    html_to_text(column): turn entity-encoded HTML into plain text, portably.

    Greenhouse job content is HTML whose markup is entity-encoded ("&lt;p&gt;"), and
    the text inside carries a second level of entities ("&amp;nbsp;"). So:
      1. decode the outer level, which turns encoded markup back into tags
      2. remove the tags
      3. decode the inner level of common entities
      4. collapse runs of whitespace
    Uses only replace() and regex replacement, which both DuckDB and Snowflake support.
#}

{% macro _decode_entities(expression) -%}
    {%- set pairs = [
        ('&lt;', '<'), ('&gt;', '>'), ('&quot;', '"'), ('&#39;', "''"), ('&apos;', "''"),
        ('&nbsp;', ' '), ('&ndash;', '-'), ('&mdash;', '-'), ('&rsquo;', "''"), ('&lsquo;', "''"),
        ('&rdquo;', '"'), ('&ldquo;', '"'), ('&hellip;', '...'), ('&bull;', '-'),
        ('&amp;', '&')
    ] -%}
    {%- set ns = namespace(sql=expression) -%}
    {%- for entity, text in pairs -%}
        {%- set ns.sql = "replace(" ~ ns.sql ~ ", '" ~ entity ~ "', '" ~ text ~ "')" -%}
    {%- endfor -%}
    {{ ns.sql }}
{%- endmacro %}

{% macro html_to_text(column) -%}
    trim({{ replace_all(
        _decode_entities(
            replace_all(_decode_entities(column), '<[^>]*>', ' ')
        ),
        '[[:space:]]+',
        ' '
    ) }})
{%- endmacro %}
