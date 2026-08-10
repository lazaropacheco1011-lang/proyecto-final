from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts.views import (
    LoginView,
    LogoutView,
    MeView,
    PasswordView,
    RefreshView,
    RegisterView,
)

router = DefaultRouter()
router.register('register', RegisterView, basename='register')
router.register('login', LoginView, basename='login')
router.register('logout', LogoutView, basename='logout')
router.register('me', MeView, basename='me')
router.register('password', PasswordView, basename='password')

urlpatterns = [
    path('refresh/', RefreshView.as_view(), name='token_refresh'),
    path('', include(router.urls)),
]
