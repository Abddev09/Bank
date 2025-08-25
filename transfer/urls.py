from rest_framework.routers import DefaultRouter
from .views import TransfersAPIViewsSet

router = DefaultRouter()
router.register(r'transfers', TransfersAPIViewsSet, basename='transfers')

urlpatterns = router.urls
