from django.apps import AppConfig


class SduShareConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sdu_share'
    def ready(self):
        # 注册信号
        from . import signals
        signals.connect_signals()