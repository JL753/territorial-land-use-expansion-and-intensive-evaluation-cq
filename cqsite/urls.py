from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.views import serve as staticfile
from django.urls import path

from study import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.page),
    path("mobile.html", views.page),
    path("desktop.html", views.page),
    path("dashboard.json", views.data, {"name": "dashboard.json"}),
    path("districts.geojson", views.data, {"name": "districts.geojson"}),
    path("api/v1/observations/", views.observations),
    path("api/v1/analysis/", views.analysis_report),
    path("api/config", views.config),
    path("api/interpret", views.interpret),
    path("<path:name>", views.asset),
]
if settings.DEBUG:
    urlpatterns.insert(0, path("static/<path:path>", staticfile))
