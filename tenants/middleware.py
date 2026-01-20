from tenants.models import Business, BusinessMembership


class BusinessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.business = None
        request.tenant = None
        if request.user.is_authenticated:
            business_id = request.session.get("business_id")
            if business_id:
                business = Business.objects.filter(id=business_id).first()
                if business and (
                    request.user.is_superuser
                    or BusinessMembership.objects.filter(
                        business=business, user=request.user, is_active=True
                    ).exists()
                ):
                    request.business = business
                    request.tenant = business
                else:
                    request.session.pop("business_id", None)
        return self.get_response(request)
