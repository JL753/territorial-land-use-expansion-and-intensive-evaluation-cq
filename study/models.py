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


class DataUpdateRun(models.Model):
    source_key = models.CharField(max_length=32, db_index=True)
    action = models.CharField(max_length=16, default="check")
    status = models.CharField(max_length=16, default="pending")
    version = models.CharField(max_length=128, blank=True)
    message = models.CharField(max_length=500, blank=True)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.source_key} · {self.action} · {self.status}"
