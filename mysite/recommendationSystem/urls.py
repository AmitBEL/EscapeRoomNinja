from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views


app_name = 'recommendationSystem'



urlpatterns = [
    path('personalized', views.personalizedRecommendationView.as_view(), name='personalized'),
    path('popular', views.generalRecommendationView.as_view(), name='popular'),
]