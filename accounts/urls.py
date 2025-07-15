from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView

from .views import RegisterView, CustomTokenObtainPairView, AuthenticatedUserView
from django.urls import path

urlpatterns = [    
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("profile/", AuthenticatedUserView.as_view(), name='authenticated-user'),
]