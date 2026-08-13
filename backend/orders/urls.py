from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import OrderViewSet, SummaryView

router = DefaultRouter()
router.register("orders", OrderViewSet, basename="order")

app_name = "orders"

urlpatterns = [
    path("summary/", SummaryView.as_view(), name="summary"),
    path("", include(router.urls)),
]
