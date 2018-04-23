from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('search_<query_type>=<query>', views.search, name='search'),
    path('artist/<MBID>', views.artist_page, name='artist'),
    path('album/<MBID>', views.album_page, name='album'),
    path('genre/<genre>', views.genre_page, name='genre'),
]