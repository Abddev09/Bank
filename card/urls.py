from rest_framework.routers import DefaultRouter
from .views import CardViewSet

router = DefaultRouter()
router.register(r'cards', CardViewSet, basename='cards')

urlpatterns = router.urls
