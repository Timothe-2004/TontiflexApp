from django.db import migrations, models
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="kkiapaytransaction",
            name="webhook_received_at",
            field=models.DateTimeField(null=True, blank=True, help_text="Horodatage réception webhook"),
        ),
        migrations.AddField(
            model_name="kkiapaytransaction",
            name="error_details",
            field=models.JSONField(default=dict, blank=True, help_text="Détails d'erreur structurés"),
        ),
        migrations.AddField(
            model_name="kkiapaytransaction",
            name="retry_count",
            field=models.PositiveIntegerField(default=0, help_text="Nombre de tentatives webhook/API"),
        ),
        migrations.AddField(
            model_name="kkiapaytransaction",
            name="callback_url",
            field=models.URLField(max_length=300, blank=True, null=True, help_text="URL de callback utilisée pour cette transaction"),
        ),
        migrations.AddField(
            model_name="kkiapaytransaction",
            name="metadata",
            field=models.JSONField(default=dict, blank=True, help_text="Métadonnées métier/contextuelles"),
        ),
        migrations.AddField(
            model_name="kkiapaytransaction",
            name="kkiapay_fees",
            field=models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Frais KKiaPay prélevés"),
        ),
        migrations.AddField(
            model_name="kkiapaytransaction",
            name="net_amount",
            field=models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, help_text="Montant net après frais"),
        ),
    ]
