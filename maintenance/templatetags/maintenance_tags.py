from django import template
register = template.Library()


@register.simple_tag
def column_label(headers, index):
    """Keep dynamic source-table card labels aligned with their column."""
    return headers[index]


@register.simple_tag(takes_context=True)
def page_query(context, number):
    params = context['request'].GET.copy()
    params['page'] = number
    return params.urlencode()
