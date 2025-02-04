from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

from mall import views

app_name = 'mall'

urlpatterns = [
    path('', views.home, name='main'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
