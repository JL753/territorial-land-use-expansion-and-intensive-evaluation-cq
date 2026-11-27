from django.contrib import admin

from .models import District, MapRelease, Observation, RefreshRun, ResearchRelease


class PublishedDataAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(District)
class DistrictAdmin(PublishedDataAdmin):
    list_display = ("code", "name", "region")
    list_filter = ("region",)
    search_fields = ("name", "code")


@admin.register(Observation)
class ObservationAdmin(PublishedDataAdmin):
    list_display = ("district", "year")
    list_filter = ("year", "district__region")
    search_fields = ("district__name", "district__code")
    list_select_related = ("district",)


@admin.register(RefreshRun)
class RefreshRunAdmin(PublishedDataAdmin):
    list_display = ("feed", "status", "happened_at", "detail")
    list_filter = ("feed", "status")
    ordering = ("-happened_at",)


@admin.register(ResearchRelease, MapRelease)
class ReleaseAdmin(PublishedDataAdmin):
    list_display = ("id", "source", "digest", "published_at")
    ordering = ("-published_at",)
