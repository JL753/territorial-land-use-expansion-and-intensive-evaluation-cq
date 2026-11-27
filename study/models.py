from django.db import models


class District(models.Model):
    code = models.CharField(max_length=6, primary_key=True)
    name = models.CharField(max_length=24)
    region = models.CharField(max_length=24)
    geometry = models.JSONField()

    def __str__(self):
        return f"{self.code} {self.name}"


class Observation(models.Model):
    district = models.ForeignKey(District, on_delete=models.CASCADE)
    year = models.PositiveSmallIntegerField(db_index=True)
    payload = models.JSONField()

    class Meta:
        ordering = ["year", "district_id"]
        constraints = [models.UniqueConstraint(fields=["district", "year"], name="unique_district_year")]

    def __str__(self):
        return f"{self.district_id} · {self.year}"


class ResearchRelease(models.Model):
    digest = models.CharField(max_length=64, unique=True)
    source = models.CharField(max_length=300)
    published_at = models.DateTimeField(auto_now_add=True)
    districts = models.JSONField()
    observations = models.JSONField()
    report = models.JSONField(null=True)


class MapRelease(models.Model):
    digest = models.CharField(max_length=64, unique=True)
    source = models.CharField(max_length=300)
    published_at = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField()


class Publication(models.Model):
    research = models.ForeignKey(ResearchRelease, null=True, on_delete=models.PROTECT)
    map_release = models.ForeignKey(MapRelease, null=True, on_delete=models.PROTECT)


class RefreshRun(models.Model):
    feed = models.CharField(max_length=20)
    status = models.CharField(max_length=20)
    detail = models.CharField(max_length=400)
    happened_at = models.DateTimeField(auto_now_add=True, db_index=True)
