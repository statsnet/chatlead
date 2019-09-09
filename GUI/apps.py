import threading
import traceback
from datetime import datetime

from django.apps import AppConfig


class GuiConfig(AppConfig):
    name = 'GUI'

    def ready(self):
        start_bots()
        print('launch')
        threading.Thread(target=broadcast_sender, daemon=True).start()


def start_bots():
    from .models import Manager
    for manager in Manager.objects.all():
        for bot in ["whatsapp", "telegram", "vk", "facebook"]:
            if getattr(manager, bot):
                print(manager.id, bot)
                threading.Thread(target=manager.get_bot(bot).start).start()


def broadcast_sender():
    from .models import BroadcastMessages
    while True:
        try:
            for broadcast in BroadcastMessages.objects.filter(sent=False, time__lte=datetime.now().timestamp()):
                try:
                    broadcast.proccessing = True
                    broadcast.save()
                    result = broadcast.manager.broadcast(broadcast.scenario, broadcast.tag)
                    broadcast.users_count = result
                    broadcast.sent = True
                    broadcast.proccessing = False
                    broadcast.save()
                except Exception:
                    print(traceback.format_exc())
        except Exception:
            print(traceback.format_exc())
