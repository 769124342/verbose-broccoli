# Generated by Django 2.1.7 on 2019-04-22 08:35

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0002_auto_20190422_1635'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='tag',
            options={'ordering': ['-update_time', '-id'], 'verbose_name': '新闻标签', 'verbose_name_plural': '新闻标签'},
        ),
        migrations.AlterModelTable(
            name='tag',
            table='tb_tag',
        ),
    ]
