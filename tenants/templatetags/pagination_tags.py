from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    request = context.get("request")
    if request is None:
        return ""
    query = request.GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()


@register.simple_tag
def pagination_window(page_obj, radius=2):
    total_pages = page_obj.paginator.num_pages
    current_page = page_obj.number
    start = max(current_page - radius, 1)
    end = min(current_page + radius, total_pages)

    pages = [1]
    if start > 2:
        pages.append(None)
    for number in range(start, end + 1):
        if number not in pages:
            pages.append(number)
    if end < total_pages - 1:
        pages.append(None)
    if total_pages > 1 and total_pages not in pages:
        pages.append(total_pages)
    return pages
