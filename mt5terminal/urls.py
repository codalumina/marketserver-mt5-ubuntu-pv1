from django.urls import path

from . import views

urlpatterns = [
    path("live/", views.live, name="live"),
    path('stat/', views.server_stat, name='server_stat'),
    path('history/', views.history, name='history'),
    path('recent/', views.recent_price_action, name='recent_price_action'),
    path('symbols/all/', views.all_symbols, name='all_symbols'),
    path('symbols/names/', views.symbols, name='symbol_names'),
]