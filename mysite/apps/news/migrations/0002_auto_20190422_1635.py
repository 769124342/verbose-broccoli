# Generated by Django 2.1.7 on 2019-04-22 08:35

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('news', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='news',
            name='author',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='news',
            name='tag',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='news.Tag'),
        ),
        migrations.AddField(
            model_name='hotnews',
            name='news',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='news.News'),
        ),
        migrations.AddField(
            model_name='comments',
            name='author',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='comments',
            name='news',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='news.News'),
        ),
        migrations.AddField(
            model_name='banner',
            name='news',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='news.News'),
        ),
    ]