from reports.dashboard_handlers.default import DefaultHandler
from reports.dashboard_handlers.hardware import HardwareHandler
from reports.dashboard_handlers.restaurant import RestaurantHandler
from reports.dashboard_handlers.retail import RetailHandler


class DashboardFactory:
    _handlers = [
        HardwareHandler(),
        RestaurantHandler(),
        RetailHandler(),
        DefaultHandler(),
    ]

    @classmethod
    def get_dashboard(cls, business_type):
        for handler in cls._handlers:
            if handler.supports(business_type):
                return handler
        return DefaultHandler()

    @classmethod
    def get_navigation_profile(cls, business):
        handler = cls.get_dashboard(business.business_type)
        return handler.get_navigation_profile(business)
