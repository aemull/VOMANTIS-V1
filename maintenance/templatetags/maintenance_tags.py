from django import template
register = template.Library()


@register.simple_tag(takes_context=True)
def page_query(context, number):
    params = context['request'].GET.copy()
    params['page'] = number
    return params.urlencode()
