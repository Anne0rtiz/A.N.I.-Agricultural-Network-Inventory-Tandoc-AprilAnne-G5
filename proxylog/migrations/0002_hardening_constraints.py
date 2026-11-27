from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proxylog", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="cropdeposit",
            constraint=models.CheckConstraint(
                condition=models.Q(("weight_kg__gt", 0)), name="deposit_weight_positive"
            ),
        ),
        migrations.AddConstraint(
            model_name="equipmentrental",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "active")),
                fields=("machine",),
                name="one_active_rental_per_machine",
            ),
        ),
        migrations.AddConstraint(
            model_name="equipmentrental",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("expected_hours__gte", Decimal("0.5")), ("expected_hours__lte", Decimal("12"))
                ),
                name="rental_hours_between_0_5_and_12",
            ),
        ),
    ]
