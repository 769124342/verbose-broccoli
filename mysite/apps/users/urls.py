from django.urls import path
from users import views

app_name = 'user'
urlpatterns = [
    path('login/',views.Login.as_view(),name='login'),
    path('logout/',views.Logout.as_view(),name='logout'),
    path('register/',views.Register.as_view(),name='register'),
]