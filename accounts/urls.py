from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView

from .views import RegisterView, CustomTokenObtainPairView, AuthenticatedUserView, GoogleCalendarInitView, GoogleCalendarRedirectView
from django.urls import path

urlpatterns = [    
    # dj-rest-auth API endpoints
    
    path('registration/', include('dj_rest_auth.registration.urls')),
    
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("profile/", AuthenticatedUserView.as_view(), name='authenticated-user'),
    
    path('google/init/', GoogleCalendarInitView.as_view(), name='google_init'),
    path('google/redirect/', GoogleCalendarRedirectView.as_view(), name='google_redirect'),
]