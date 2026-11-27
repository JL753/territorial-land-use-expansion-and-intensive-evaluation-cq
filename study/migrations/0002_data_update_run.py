from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("study", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="DataUpdateRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_key", models.CharField(db_index=True, max_length=32)),
                ("action", models.CharField(default="check", max_length=16)),
                ("status", models.CharField(default="pending", max_length=16)),
                ("version", models.CharField(blank=True, max_length=128)),
                ("message", models.CharField(blank=True, max_length=500)),
                ("details", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
