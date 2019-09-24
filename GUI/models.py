import json
import os
import re
import threading
import time
import traceback
from datetime import datetime
from urllib.request import urlopen

import openpyxl
import requests
import telebot
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django_extensions.db.fields.json import JSONField
from pymessenger.bot import Bot as FacebookClient

from .mail import send_message

default_message = [{'text': '', 'keyboard': []}]
default_messages = {"vk": default_message, "facebook": default_message, "telegram": default_message,
                    "whatsapp": default_message}


def genchoices(*args):
    return tuple([(str(c), str(c)) for c in args])


def auto_increment():
    last = Trigger.objects.all().order_by('id').last()
    return int(last.id) + 1 if last else 10000


def auto_increment_scenario():
    last = Scenario.objects.all().order_by('id').last()
    return int(last.id) + 1 if last else 10000


def auto_increment_ride():
    last = AutoRide.objects.all().order_by('id').last()
    return int(last.id) + 1 if last else 10000


class AutoRide(models.Model):
    id = models.AutoField(auto_created=True, unique=True, default=auto_increment_ride, primary_key=True)
    manager = models.ForeignKey('Manager', on_delete=models.CASCADE, null=True)
    trigger_text = models.TextField(blank=True, null=True)
    scenario = models.ForeignKey('Scenario', on_delete=models.CASCADE, null=True)


class Scenario(models.Model):
    id = models.AutoField(auto_created=True, unique=True, default=auto_increment_scenario, primary_key=True)
    destination = models.CharField(max_length=20, default='',
                                   choices=genchoices('', 'broadcast', 'autoride', 'subscribe', 'unsubscribe'))
    manager = models.ForeignKey('Manager', on_delete=models.CASCADE, null=True)
    trigger_text = models.TextField(blank=True, null=True)


class Trigger(models.Model):
    id = models.AutoField(auto_created=True, unique=True, default=auto_increment, primary_key=True)
    caption = models.CharField(max_length=256, null=True, blank=True, default="")
    social = models.CharField(max_length=20, default='telegram',
                              choices=genchoices('telegram', 'vk', 'whatsapp', 'facebook'))
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, null=True, blank=True, related_name="triggers")
    keyboard = models.CharField(max_length=256, null=True, blank=True, default="{}")
    messages = JSONField(default=default_messages, null=True, blank=True)

    def __str__(self):
        return "[%s - %s]" % (self.caption, self.id)


class Tag(models.Model):
    action = models.CharField(max_length=20, default='add', choices=genchoices('add', 'remove'))
    tag_name = models.CharField(max_length=30, default='')
    trigger = models.ForeignKey('Trigger', on_delete=models.CASCADE, related_name='tags')


class User(AbstractUser):
    email = models.CharField(max_length=256, blank=False, null=False, unique=True)
    username = models.CharField(max_length=16, blank=True, null=True, unique=False, default="")
    user_token = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")
    utm_source = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")
    ref = models.IntegerField(null=True, blank=True, unique=False)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"[User: {self.email} ({self.password})]"


class BroadcastMessages(models.Model):
    manager = models.ForeignKey('Manager', on_delete=models.SET_NULL, null=True)
    scenario = models.ForeignKey('Scenario', on_delete=models.CASCADE, null=True)
    tag = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")
    time = models.IntegerField(null=True, blank=True, unique=False)
    users_count = models.IntegerField(null=True, blank=True, unique=False, default=0)
    sent = models.BooleanField(default=False)
    proccessing = models.BooleanField(default=False)

    def __str__(self):
        return f"[{self.time}] - {self.text}"

    def get_time(self):
        return datetime.fromtimestamp(self.time).strftime("%Y-%m-%d %H:%M:%S")


class WhatsAppUsers(models.Model):
    manager = models.ForeignKey('Manager', on_delete=models.SET_NULL, null=True)
    user_id = models.CharField(max_length=256, null=True, blank=True, unique=False)
    name = models.CharField(max_length=512, null=True, blank=True, unique=False, default="")
    tag = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")
    mode = models.CharField(max_length=128, blank=True, null=True, unique=False, default="main")
    data = models.CharField(max_length=4096, blank=True, null=True, unique=False, default="main")
    user_data = models.CharField(max_length=4096, blank=True, null=True, unique=False, default="main")


class TelegramUsers(models.Model):
    manager = models.ForeignKey('Manager', on_delete=models.SET_NULL, null=True)
    user_id = models.CharField(max_length=256, null=True, blank=True, unique=False)
    name = models.CharField(max_length=512, null=True, blank=True, unique=False, default="")
    tag = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")
    mode = models.CharField(max_length=128, blank=True, null=True, unique=False, default="main")
    data = models.CharField(max_length=4096, blank=True, null=True, unique=False, default="main")
    user_data = models.CharField(max_length=4096, blank=True, null=True, unique=False, default="main")


class VkUsers(models.Model):
    manager = models.ForeignKey('Manager', on_delete=models.SET_NULL, null=True)
    user_id = models.CharField(max_length=256, null=True, blank=True, unique=False)
    name = models.CharField(max_length=512, null=True, blank=True, unique=False, default="")
    tag = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")
    mode = models.CharField(max_length=128, blank=True, null=True, unique=False, default="main")
    data = models.CharField(max_length=4096, blank=True, null=True, unique=False, default="main")
    user_data = models.CharField(max_length=4096, blank=True, null=True, unique=False, default="main")


class FacebookUsers(models.Model):
    manager = models.ForeignKey('Manager', on_delete=models.SET_NULL, null=True)
    user_id = models.CharField(max_length=256, null=True, blank=True, unique=False)
    name = models.CharField(max_length=512, null=True, blank=True, unique=False, default="")
    tag = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")
    mode = models.CharField(max_length=128, blank=True, null=True, unique=False, default="main")
    data = models.CharField(max_length=4096, blank=True, null=True, unique=False, default="main")
    user_data = models.CharField(max_length=4096, blank=True, null=True, unique=False, default="main")


class WhatsAppDelayMsg(models.Model):
    manager = models.ForeignKey('Manager', on_delete=models.SET_NULL, null=True)
    chat_id = models.CharField(max_length=256, null=True, blank=True, unique=False)
    text = models.TextField(null=False, blank=False, unique=False)
    plan_time = models.IntegerField(null=True, blank=True, unique=False)
    sent = models.BooleanField(default=False)


class TelegramDelayMsg(models.Model):
    manager = models.ForeignKey('Manager', on_delete=models.SET_NULL, null=True)
    chat_id = models.CharField(max_length=256, null=True, blank=True, unique=False)
    text = models.TextField(null=False, blank=False, unique=False)
    plan_time = models.IntegerField(null=True, blank=True, unique=False)
    sent = models.BooleanField(default=False)


class VkDelayMsg(models.Model):
    manager = models.ForeignKey('Manager', on_delete=models.SET_NULL, null=True)
    chat_id = models.CharField(max_length=256, null=True, blank=True, unique=False)
    text = models.TextField(null=False, blank=False, unique=False)
    plan_time = models.IntegerField(null=True, blank=True, unique=False)
    sent = models.BooleanField(default=False)


class FacebookDelayMsg(models.Model):
    manager = models.ForeignKey('Manager', on_delete=models.SET_NULL, null=True)
    chat_id = models.CharField(max_length=256, null=True, blank=True, unique=False)
    text = models.TextField(null=False, blank=False, unique=False)
    plan_time = models.IntegerField(null=True, blank=True, unique=False)
    sent = models.BooleanField(default=False)


class WhatsAppReceivedMsg(models.Model):
    manager = models.ForeignKey('Manager', on_delete=models.SET_NULL, null=True)
    text = models.TextField(null=False, blank=False, unique=False)
    chat_id = models.CharField(max_length=256, null=True, blank=True, unique=False)
    user_id = models.CharField(max_length=256, null=True, blank=True, unique=False)
    sender_name = models.CharField(max_length=512, null=True, blank=True, unique=False)
    time = models.CharField(max_length=256, null=True, blank=True, unique=False)
    message_number = models.IntegerField(null=True, blank=True, unique=False)
    proccessed = models.BooleanField(default=False)
    user_data = models.CharField(max_length=512, null=True, blank=True, unique=False)

    def __str__(self):
        return f"Message {self.manager}"


class TelegramReceivedMsg(models.Model):
    manager = models.ForeignKey('Manager', on_delete=models.SET_NULL, null=True)
    text = models.TextField(null=False, blank=False, unique=False)
    chat_id = models.CharField(max_length=256, null=True, blank=True, unique=False)
    user_id = models.CharField(max_length=256, null=True, blank=True, unique=False)
    sender_username = models.CharField(max_length=512, null=True, blank=True, unique=False)
    sender_name = models.CharField(max_length=512, null=True, blank=True, unique=False)
    chat_title = models.CharField(max_length=512, null=True, blank=True, unique=False)
    time = models.CharField(max_length=256, null=True, blank=True, unique=False)
    message_id = models.IntegerField(null=True, blank=True, unique=False)
    proccessed = models.NullBooleanField(default=False)
    user_data = models.CharField(max_length=512, null=True, blank=True, unique=False)

    def __str__(self):
        return f"Message {self.manager}"


class VkReceivedMsg(models.Model):
    manager = models.ForeignKey('Manager', on_delete=models.SET_NULL, null=True)
    message_id = models.IntegerField(null=True, blank=True, unique=False)
    text = models.TextField(null=False, blank=False, unique=False)
    user_id = models.CharField(max_length=256, null=True, blank=True, unique=False)
    chat_id = models.CharField(max_length=256, null=True, blank=True, unique=False)
    time = models.IntegerField(null=True, blank=True, unique=False)
    user_data = models.CharField(max_length=512, null=True, blank=True, unique=False)

    def __str__(self):
        return f"Message {self.manager}"


class FacebookReceivedMsg(models.Model):
    manager = models.ForeignKey('Manager', on_delete=models.SET_NULL, null=True)
    message_id = models.CharField(max_length=256, null=True, blank=True, unique=False)
    text = models.TextField(null=False, blank=False, unique=False)
    user_id = models.CharField(max_length=256, null=True, blank=True, unique=False)
    chat_id = models.CharField(max_length=256, null=True, blank=True, unique=False)
    time = models.IntegerField(null=True, blank=True, unique=False)
    user_data = models.CharField(max_length=512, null=True, blank=True, unique=False)

    def __str__(self):
        return f"Message {self.manager}"


class Bot():
    BotUsers = lambda *args, **kwargs: models.Model()
    BotDelayMsg = lambda *args, **kwargs: models.Model()
    BotReceivedMsg = lambda *args, **kwargs: models.Model()
    bot_place = ""

    @staticmethod
    def can_work(manager):
        return False

    def __init__(self, manager):
        self.manager = manager

    def start(self):
        return True

    def stop(self):
        return True

    def wait_stopping(self):
        while True:
            print(self.threads)
            time.sleep(1)
            if not self.is_any_work():
                break

    def get_hide_link(self, text):
        return text

    def send_file(self, *args, **kwargs):
        return True

    def send_contact(self, *args, **kwargs):
        return True

    def send_message(self, *args, **kwargs):
        return True

    def broadcast(self, text, tag=""):
        result = 0
        for user in self.BotUsers.objects.filter(manager=self.manager):
            try:
                if not tag or user.tag == tag:
                    self.message_routine(text, self.BotUsers(manager=self.manager, user_id=user.user_id))

                    self.send_message(user.user_id, text)
                    result += 1
            except Exception:
                print(traceback.format_exc())
        return result

    def get_dialogs_count(self):
        return 0

    def run_threads(self, threads=None, send_delay_messages=True):
        if threads is None:
            threads = []

        for thread in self.threads.get(self.manager.id, {}).values():
            if thread.is_alive():
                return False

        if "send_delay_messages" not in [thread["name"] for thread in threads]:
            threads.append({
                "name": "send_delay_messages",
                "target": self.send_delay_messages
            })

        self.threads.update({self.manager.id: {
            thread["name"]: threading.Thread(
                target=thread["target"], args=thread.get("args", ()), daemon=True
            ) for thread in threads
        }})
        for thread in self.threads.get(self.manager.id, {}).values():
            thread.start()

        return self.is_all_work()

    def is_all_work(self):
        try:
            return all(thread.is_alive() for key, thread in self.threads.get(self.manager.id, {}).items())
        except TypeError:
            return False

    def is_any_work(self):
        try:
            return any(thread.is_alive() for key, thread in self.threads.get(self.manager.id, {}).items())
        except TypeError:
            return False

    def fix_work_status(self):
        print("fix", self.bot_place, self.threads, self.is_all_work(), self.is_all_work())
        if not self.is_any_work():
            if getattr(self.manager, self.bot_place):
                setattr(self.manager, self.bot_place, False)
                self.manager.save()
        elif self.is_any_work() and not self.is_all_work():
            self.stop()
        elif self.is_all_work():
            if not getattr(self.manager, self.bot_place):
                setattr(self.manager, self.bot_place, True)
                self.manager.save()

    def send_delay_messages(self):
        print(self.BotDelayMsg.objects.filter(manager=self.manager))
        while getattr(self.manager, self.bot_place):
            try:
                if not getattr(self.manager, self.bot_place):
                    print("break")
                    break
                for message in self.BotDelayMsg.objects.filter(manager=self.manager, sent=False,
                                                               plan_time__lte=datetime.now().timestamp()):
                    try:
                        print(message)
                        if not getattr(self.manager, self.bot_place):
                            break
                        self.send_message(message.chat_id, message.text)
                        message.sent = True
                        message.save()
                    except Exception:
                        print(traceback.format_exc())
                time.sleep(1)
            except Exception:
                print(traceback.format_exc())

    def find_scenario(self, trigger_text):
        scenario = Scenario.objects.filter(manager=self.manager, trigger_text=trigger_text)
        if scenario.exists():
            return scenario[0]

    def find_scenario_by_id(self, scenario_id):
        scenario = Scenario.objects.filter(manager=self.manager, id=scenario_id)
        if scenario.exists():
            return scenario[0]

    def send_photo(self, chat_id, filename=None, url=None, **kwargs):
        return True

    def send_audio(self, chat_id, filename=None, url=None, **kwargs):
        return True

    def send_video(self, chat_id, filename=None, url=None, **kwargs):
        return True

    def find_trigger(self, scenario, trigger_id=None):
        if not trigger_id and scenario:
            trigger = scenario.triggers.all()
            if trigger.exists():
                return trigger[0]
            else:
                return None
        if trigger_id and scenario:
            return Trigger.objects.get(scenario=scenario, id=trigger_id)

    def trigger_routine(self, scenario, trigger, user):
        if not trigger:
            return
        result = True
        for tag in trigger.tags.all():
            if tag.action == 'add' and tag.tag_name not in user.tag:
                user.tag = f"{user.tag} {tag.tag_name}"
            if tag.action == 'remove':
                user.tag = str(user.tag).replace(f"{tag.tag_name}", "").strip()
            user.save()
        result = self.message_routine(trigger.messages, user, scenario, trigger.keyboard)
        return result

    def message_routine(self, messages, user, scenario=None, fast_buttons=None):
        messages = messages.get(self.bot_place)
        if not messages:
            return
        try:
            if fast_buttons:
                fast_buttons = json.loads(fast_buttons).get(self.bot_place, [])
        except:
            fast_buttons = []
        result = True
        for tg_message in messages:
            print(tg_message, type(tg_message))
            kwargs = {}
            keyboard = tg_message.get('keyboard', []) + fast_buttons
            if keyboard:
                for button in keyboard:
                    btn_type = button.get('type')
                    if btn_type not in kwargs:
                        kwargs[btn_type] = []
                    kwargs[btn_type].append(button)
            print(kwargs)
            for field in tg_message:
                text = tg_message.get('text')
                try:
                    text = str(text).replace('{username}', json.loads(user.user_data).get('username', ''))
                    text = str(text).replace('{first_name}', json.loads(user.user_data).get('first_name', ''))
                    text = str(text).replace('{phone}', json.loads(user.user_data).get('phone', ''))
                except Exception as e:
                    print('form?', str(e))
                if field == "timer":
                    timing = tg_message.get('timer', {})
                    pause = timing.get('pause_delay')
                    send_time = timing.get('send_time')
                    plan_time = int(
                        datetime.now().timestamp() + int(pause)) if pause else send_time if send_time else None
                    if plan_time:
                        self.BotDelayMsg(
                            manager=self.manager,
                            chat_id=user.user_id,
                            text=messages,
                            plan_time=plan_time,
                            sent=False,
                        ).save()
                        return True
                if field == 'text':
                    result = self.send_message(user.user_id, text, keyboard=kwargs)
                if field in ['photo', 'video', 'audio', 'file']:
                    attach_set = {'photo': self.send_photo, 'video': self.send_video, 'audio': self.send_audio,
                                  'file': self.send_file}
                    url = tg_message.get(field, {})
                    # filename = tg_message.get(field, {}).get('filename')
                    result = attach_set[field](user.user_id, url)
                if field == 'call' and scenario:
                    call = tg_message.get('call')
                    trigger_id = call.get('trigger_id')
                    scenario_id = call.get('scenario_id')
                    if trigger_id:
                        new_trigger = self.find_trigger(scenario, trigger_id)
                        if new_trigger:
                            result = self.trigger_routine(scenario, new_trigger, user)
                    elif scenario_id:
                        new_scenario = self.find_scenario_by_id(scenario_id)
                        new_trigger = self.find_trigger(new_scenario)
                        if new_trigger:
                            result = self.trigger_routine(scenario, new_trigger, user)
                if field == 'form':
                    form = tg_message.get('form')
                    user.mode = "application:0"
                    user.data = json.dumps({
                        "fields": [field.get('caption') for field in form],
                        "types": [field.get('type') for field in form],
                        "values": []
                    })
                    user.save()
                    self.send_message(user.user_id, form[0].get('caption'))
        return result

    @staticmethod
    def regex_valid(text, regex_type):
        regex_set = {'text': r".*", 'phone': r"\+*[0-9]{10,11}", 'email': r"[\w-]+\@\w+\.\w+", 'digits': r"\d+(\.\d+)*"}
        regular = regex_set.get(regex_type)
        if regular:
            found = re.fullmatch(regular, text.strip())
            if found:
                return found.group()

    def proccess_message(self, message):
        try:
            if not self.BotUsers.objects.filter(manager=self.manager, user_id=message.user_id).exists():
                user = self.BotUsers(manager=self.manager, user_id=message.user_id)
                user.save()
                result = True
                if self.manager.welcome_message:
                    if 'scenario:' in self.manager.welcome_message.lower():
                        scenario = self.find_scenario_by_id(
                            self.manager.welcome_message.lower().replace('scenario:', ''))
                        result = self.trigger_routine(scenario, self.find_trigger(scenario), user)
                    else:
                        result = self.send_message(message.user_id, self.manager.welcome_message)
                    if self.manager.send_welcome_notif and self.manager.welcome_notif_text and self.manager.welcome_admin_id:
                        if self.manager.get_bot('whatsapp').can_work(self.manager):
                            self.manager.get_bot('whatsapp').send_message(self.manager.welcome_admin_id,
                                                                          self.manager.welcome_notif_text)
                return result
            else:
                user = self.BotUsers.objects.get(manager=self.manager, user_id=message.user_id)
            if user.user_data != message.user_data:
                user.user_data = message.user_data
                user.save()
            print(message)
            if user.mode == "main":
                if 'autoride_' in message.text:
                    autoride_name = str(message.text).replace('autoride_', '')
                    autorides = AutoRide.objects.filter(manager=self.manager, trigger_text=autoride_name)
                    if autorides.exists():
                        autoride = autorides[0]
                        result = self.message_routine(autoride.scenario.messages, user)
                        try:
                            if self.manager.application_will_send:
                                notify_message = f"{autoride.trigger_text} - {user.username}"
                                for admin in str(self.manager.application_whatsapp_id).split(','):
                                    if admin:
                                        if self.manager.get_bot('whatsapp').can_work(self.manager):
                                            self.manager.get_bot('whatsapp').send_message(admin, notify_message)
                                for admin in str(self.manager.application_email).split(','):
                                    if admin:
                                        send_message(to=admin, message=notify_message, subject=autoride.trigger_text)
                        except:
                            pass
                        return result

                scenario = self.find_scenario(message.text)
                trigger = self.find_trigger(scenario)
                print(message.text, scenario, trigger)
                if scenario and trigger:
                    result = self.trigger_routine(scenario, trigger, user)
                elif self.manager.default_response:
                    if 'scenario:' in self.manager.default_response.lower():
                        scenario = self.find_scenario_by_id(
                            self.manager.default_response.lower().replace('scenario:', ''))
                        result = self.trigger_routine(scenario, self.find_trigger(scenario), user)
                    else:
                        text = self.manager.default_response
                        result = self.send_message(message.user_id, text)
                else:
                    result = True
                return result

            elif user.mode.startswith("application:"):
                field_index = int(user.mode.split(":")[1])
                if message.text == 'break':
                    user.mode = "main"
                    user.save()
                    return

                data = json.loads(user.data)
                print(data['types'][field_index])
                print(data['types'])
                print(field_index)
                if not self.regex_valid(message.text, data['types'][field_index]):
                    result = self.send_message(message.user_id, data["fields"][field_index])
                    return result
                data["values"].append(message.text)
                user.data = json.dumps(data)

                if len(data["values"]) < len(data["fields"]):
                    user.mode = f"application:{field_index + 1}"
                    result = self.send_message(message.user_id, data["fields"][field_index + 1])
                else:
                    reqdata = dict(zip(data["fields"], data["values"]))
                    print(reqdata)
                    if self.manager.bitrix_key and self.manager.bitrix_domain:
                        requests.post(f"https://{self.manager.bitrix_domain}.bitrix24.ru/rest/crm.lead.add",
                                      params={"auth": self.manager.bitrix_key}, data={
                                "fields": reqdata,
                                "params": {
                                    "REGISTER_SONET_EVENT": "Y"
                                }
                            })
                    if self.manager.amocrm_domain:
                        requests.post(f"https://{self.manager.amocrm_domain}.amocrm.ru/api/v2/leads", data={
                            "add": json.dumps([reqdata])
                        })
                    try:
                        notify_subject = f"[UserID: {user.id} application]"
                        notify_message = f"{self.manager.id}({self.bot_place}): {message.user_id}."
                        for field, value in reqdata.items():
                            notify_message = f"{notify_message} {field}: {value}."
                        for admin in str(self.manager.application_whatsapp_id).split(','):
                            if admin:
                                if self.manager.get_bot('whatsapp').can_work(self.manager):
                                    self.manager.get_bot('whatsapp').send_message(admin, notify_message)
                        for admin in str(self.manager.application_email).split(','):
                            if admin:
                                send_message(to=admin, message=notify_message, subject=notify_subject)
                    except Exception as e:
                        print(e)
                    user.data = "{}"
                    user.mode = f"main"
                    result = self.send_message(message.user_id, "Готово!")
                user.save()
                return result
            else:
                return True
        except Exception as e:
            print(e)
            return True


class TelegramBot(Bot):
    threads = {}
    BotDelayMsg = TelegramDelayMsg
    BotUsers = TelegramUsers
    BotReceivedMsg = TelegramReceivedMsg
    bot_place = "telegram"

    @staticmethod
    def can_work(manager):
        if manager.telegram_token:
            try:
                telebot.TeleBot(manager.telegram_token).get_me()
                return True
            except Exception:
                return False
        return False

    def __init__(self, manager):
        self.manager = manager
        self.token = manager.telegram_token
        try:
            self.bot = telebot.TeleBot(self.token, threaded=False)
            self.bot_username = self.bot.get_me().username
        except:
            self.bot, self.bot_username = None, "None"
        self.manager.telegram_name = self.bot_username

    def start(self):
        if self.manager.telegram or self.is_any_work():
            self.stop()

        self.manager.telegram = True
        self.manager.save()

        self.bot.add_message_handler(self.bot._build_handler_dict(
            self.proccess_messages, content_types=["text"], commands=None,
            func=lambda msg: msg.chat.id == msg.from_user.id, regexp=None
        ))

        self.run_threads([{"name": "polling", "target": self.polling}])

    def stop(self):
        self.manager.telegram = False
        self.manager.save()
        self.bot.stop_polling()
        self.wait_stopping()

    def polling(self):
        while self.manager.telegram:
            try:
                print(f"start polling in {self.manager.id} with {self.token}")
                self.bot.polling(interval=1, timeout=10)
                break
            except Exception as e:
                print(traceback.format_exc())

    def text_format(self, text, message):
        return text.replace(
            "{name}", message.sender_name
        ).replace(
            "{username}", f"@{message.sender_username}"
        )

    def get_hide_link(self, text):
        return f"https://t.me/{self.bot_username}?start={text}"

    def send_message(self, chat_id, text, *args, keyboard=None, **kwargs):
        try:
            if not keyboard:
                keyboard = {}
            text_buttons = keyboard.get('text_buttons', [])
            url_buttons = keyboard.get('url_buttons', [])
            fast_buttons = keyboard.get('fast_buttons', [])
            print(fast_buttons)
            kwargs = {}
            if text_buttons:
                keyboard = telebot.types.ReplyKeyboardMarkup()
                keyboard.add(*[telebot.types.KeyboardButton(text=button.get('caption')) for button in text_buttons])

                kwargs['reply_markup'] = keyboard
            elif fast_buttons:
                keyboard = telebot.types.InlineKeyboardMarkup()
                keyboard.add(
                    *[telebot.types.InlineKeyboardButton(text=button.get('caption'),
                                                         callback_data=button.get('trigger_id'))
                      for button in fast_buttons])

                kwargs['reply_markup'] = keyboard
            self.bot.send_message(chat_id, text, *args, **kwargs)

            return True
        except Exception:
            print(traceback.format_exc())
            return False

    def get_attach(self, filename, url):
        print(url, filename)
        if url:
            return urlopen(url).read()
        if filename and os.path.exists(filename):
            with open(filename, 'rb') as file:
                return file.read()

    def send_photo(self, chat_id, filename=None, url=None, **kwargs):
        attach = self.get_attach(filename, url)
        if attach:
            self.bot.send_photo(chat_id, attach)

    def send_audio(self, chat_id, filename=None, url=None, **kwargs):
        attach = self.get_attach(filename, url)
        if attach:
            self.bot.send_audio(chat_id, attach)

    def send_video(self, chat_id, filename=None, url=None, **kwargs):
        attach = self.get_attach(filename, url)
        if attach:
            self.bot.send_video(chat_id, attach)

    def set_typing(self, chat_id):
        self.bot.send_chat_action(chat_id, 'typing')

    def send_file(self, chat_id, filename=None, url=None, **kwargs):
        attach = self.get_attach(filename, url)
        if attach:
            self.bot.send_document(chat_id, attach)

    def send_document(self, *args, **kwargs):
        self.bot.send_document(*args, **kwargs)

    def get_dialogs_count(self):
        return len(set(msg.chat_id for msg in TelegramReceivedMsg.objects.filter(manager=self.manager)))

    def proccess_messages(self, message):
        try:
            print(message)
            if message.content_type == "text":
                msg = TelegramReceivedMsg(
                    manager=self.manager,
                    text=message.text,
                    chat_id=message.chat.id,
                    user_id=message.from_user.id,
                    sender_username=message.from_user.username,
                    sender_name=message.from_user.first_name,
                    chat_title=message.chat.title,
                    time=message.date,
                    message_id=message.message_id,
                    user_data=json.dumps(
                        {'username': message.from_user.username, "first_name": message.from_user.first_name})
                    # proccesses=result
                )
                if msg.text.startswith("/start ") and msg.text != "/start":
                    msg.text = msg.text[7:]
                result = self.proccess_message(msg)
                msg.proccessed = result
                msg.save()
        except Exception:
            print(traceback.format_exc())


class VkBot(Bot):
    threads = {}
    BotDelayMsg = VkDelayMsg
    BotUsers = VkUsers
    BotReceivedMsg = VkReceivedMsg
    bot_place = "vk"

    @staticmethod
    def can_work(manager):
        return manager.vk_group_access_token and manager.vk_group_id

    def __init__(self, manager):
        self.manager = manager
        self.token = manager.vk_group_access_token
        self.group_id = manager.vk_group_id

    def configur_long_poll_server(self):
        config = self.request("messages", "getLongPollServer", params={"need_pts": 1, "lp_version": 3})["response"]

        self.lp_config = config

    def stop(self):
        self.manager.vk = False
        self.manager.save()
        self.wait_stopping()

    def start(self):

        self.self_messages = []

        if self.manager.vk or self.is_any_work():
            self.stop()

        self.configur_long_poll_server()

        self.manager.vk = True
        self.manager.save()

        self.run_threads([{"name": "handler", "target": self.message_handler}])

    @property
    def long_poll_link(self):
        return "https://{server}?act=a_check&key={key}&ts={ts}&wait=5&mode=2&version=3".format(**self.lp_config)

    def get_updates(self):
        response = requests.get(self.long_poll_link).json()
        if response.get("failed", 0) in [1, 2, 3]:
            if response.get("failed", 0) == 1:
                self.lp_config["ts"] = response["ts"]
            else:
                self.configur_long_poll_server()
            response = requests.get(self.long_poll_link).json()
        self.lp_config["ts"] = response["ts"]
        return response["updates"]

    def request(self, section, method, params=None):
        if params is None:
            params = {}
        params.update({
            "access_token": self.token,
            "group_id": self.group_id,
            "v": "5.95",
        })
        response = requests.post(f"https://api.vk.com/method/{section}.{method}", params).json()
        return response

    def send_message(self, user_id, text, *args, keyboard=None, **kwargs):
        if not keyboard:
            keyboard = {}
        text_buttons = keyboard.get('text_buttons', [])
        url_buttons = keyboard.get('url_buttons', [])
        fast_buttons = keyboard.get('fast_buttons', [])

        if text_buttons:
            buttons = [{
                "color": "secondary",
                "action": {
                    "type": "text",
                    "label": button.get('caption'),
                    "payload": button.get('trigger_text'),
                }
            } for button in text_buttons]
        elif fast_buttons:
            buttons = [{
                "color": "secondary",
                "action": {
                    "type": "text",
                    "label": button.get('caption'),
                    "payload": button.get('trigger_id'),
                }
            } for button in fast_buttons]
        else:
            buttons = []
        message_id = self.request("messages", "send", params={
            "user_id": user_id,
            "message": text,

            "keyboard": json.dumps({
                "one_time": False,
                "buttons": buttons
            }),
            "random_id": "",
        })["response"]
        self.self_messages.append(message_id)
        return message_id

    def send_photo(self, chat_id, filename=None, url=None, **kwargs):
        return self.send_file(chat_id, filename, url)

    def send_audio(self, chat_id, filename=None, url=None, **kwargs):
        return True

    def send_video(self, chat_id, filename=None, url=None, **kwargs):
        return self.send_file()

    def send_file(self, chat_id, filename=None, url=None, ):
        upload_url = self.request("docs", "getMessagesUploadServer", params={"peer_id": chat_id})["response"][
            "upload_url"]
        print(upload_url)
        with open(filename, "rb") as file:
            file_string = requests.post(upload_url, files={"file": file}).content.decode('utf-8')
            print(file_string)
            file_string = json.loads(file_string).get("file")
        return self.request("docs", "save",
                            params={"file": file_string, "title": os.path.basename(filename), "tags": ""})

    def get_dialogs_count(self):
        return len(set(msg.user_id for msg in VkReceivedMsg.objects.filter(manager=self.manager)))

    def message_handler(self):

        while self.manager.vk:
            try:
                if not self.manager.vk:
                    break
                for update in self.get_updates():
                    try:
                        print(update)
                        if not self.manager.vk:
                            break
                        code, *args = update
                        if code != 4:
                            continue
                        code, message_id, flags, peer_id, timestamp, text, ref, *args = update
                        if message_id in self.self_messages:
                            continue
                        if type(ref) == dict and ref.get('ref_source'):
                            text = ref.get('ref_source')
                        print("VkReceivedMsg: ", peer_id, datetime.now().timestamp() - int(timestamp))
                        msg = VkReceivedMsg(
                            manager=self.manager,
                            message_id=message_id,
                            text=text,
                            user_id=peer_id,
                            chat_id=peer_id,
                            time=timestamp,
                        )
                        result = self.proccess_message(msg)
                        msg.save()
                    except Exception:
                        print(traceback.format_exc())
            # time.sleep(1)
            except Exception:
                print(traceback.format_exc())


class FacebookBot(Bot):
    threads = {}
    BotDelayMsg = FacebookDelayMsg
    BotUsers = FacebookUsers
    BotReceivedMsg = FacebookReceivedMsg
    bot_place = "facebook"

    @staticmethod
    def can_work(manager):
        return manager.facebook_token and manager.facebook_group_id

    def __init__(self, manager):
        self.manager = manager
        self.token = manager.facebook_token
        self.group_id = manager.facebook_group_id
        self.bot = FacebookClient(self.token)

    def stop(self):
        print("!!!!stop fb", self.manager.facebook)
        self.manager.facebook = False
        print("!!!!set fb to false")
        self.manager.save()
        print("!!!!fb stopped", self.manager.facebook)
        self.wait_stopping()

    def start(self):
        if self.manager.facebook:
            self.stop()

        self.manager.facebook = True
        self.manager.save()

        self.run_threads()

    def get_hide_link(self, text):
        return f"http://m.me/{self.group_id}?ref={text}"

    def send_photo(self, chat_id, filename=None, url=None, **kwargs):
        self.bot.send_image(chat_id, filename)

    def send_audio(self, chat_id, filename=None, url=None, **kwargs):
        self.bot.send_audio(chat_id, filename)

    def send_video(self, chat_id, filename=None, url=None, **kwargs):
        self.bot.send_video(chat_id, filename)

    def send_raw(self, payload):
        request_endpoint = '{0}/me/messages'.format(self.bot.graph_url)
        response = requests.post(
            request_endpoint,
            params=self.bot.auth_args,
            json=payload
        )
        result = response.json()
        return result

    def send_replies(self, recipient_id, text, buttons):
        payload = {
            'recipient': {
                'id': recipient_id
            },
            "messaging_type": "RESPONSE",
            "message": {
                "text": text,
                "quick_replies": [
                    {
                        "content_type": "text",
                        "title": btn.get('caption'),
                        "payload": btn.get('payload'),
                    } for btn in buttons
                ]
            }
        }
        a = self.send_raw(payload)
        return a

    def send_message(self, user_id, text, *args, keyboard=None, **kwargs):
        if not keyboard:
            keyboard = {}
        text_buttons = keyboard.get('text_buttons', [])
        url_buttons = keyboard.get('url_buttons', [])
        fast_buttons = keyboard.get('fast_buttons', [])

        if fast_buttons:
            return self.send_raw(self.send_replies(user_id, text, fast_buttons))
        if (text_buttons is None or len(text_buttons) <= 0) \
                and (url_buttons is None or len(url_buttons) <= 0):
            return self.bot.send_text_message(user_id, text)
        if text_buttons is None:
            text_buttons = []
        if url_buttons is None:
            url_buttons = []

        buttons = [{"type": "postback", "title": button.get('caption'), "payload": button.get('trigger_text')} for
                   button in text_buttons]
        buttons = buttons + [{"type": "web_url", "url": button.get('url'), "title": button.get('caption')} for button in
                             url_buttons]
        result = self.bot.send_button_message(user_id, text, buttons)
        return result

    def send_file(self, user_id, path):
        return self.bot.send_file(user_id, path)

    def get_dialogs_count(self):
        return len(set(msg.user_id for msg in FacebookReceivedMsg.objects.filter(manager=self.manager)))

    def proccess_event(self, event):
        for msg in event['messaging']:
            print(msg)
            if "text" in msg.get("message", {}):
                text, mid = msg["message"]["text"], msg["message"]["mid"]
            elif "referral" in msg:
                text, mid = msg["referral"]["ref"], None
            else:
                continue
            message = FacebookReceivedMsg(
                manager=self.manager,
                message_id=mid,
                time=msg["timestamp"],
                user_id=msg["sender"]["id"],
                chat_id=msg["sender"]["id"],
                text=text,
            )
            self.proccess_message(message)
            message.save()


class WhatsAppBot(Bot):
    threads = {}
    BotDelayMsg = WhatsAppDelayMsg
    BotUsers = WhatsAppUsers
    BotReceivedMsg = WhatsAppReceivedMsg
    bot_place = "whatsapp"

    @staticmethod
    def can_work(manager):
        return manager.whatsapp_instance and manager.whatsapp_token

    def __init__(self, manager):
        self.manager = manager
        self.instance = manager.whatsapp_instance
        self.token = manager.whatsapp_token
        self.endpoint = f"https://api.chat-api.com/instance{self.instance}"

        if self.can_work(self.manager) and not WhatsAppReceivedMsg.objects.filter(manager=self.manager).exists():
            self.load_last_messages()

    def stop(self):
        self.manager.whatsapp = False
        self.manager.save()
        self.wait_stopping()

    def start(self):
        if self.manager.whatsapp or self.is_any_work():
            self.stop()

        self.update_status()
        self.manager.whatsapp = True
        self.manager.save()

        self.run_threads([{"name": "handler", "target": self.message_handler}])

    def text_format(self, text, message):
        return text.replace(
            "{name}", message.sender_name
        ).replace(
            "{phone}", message.user_id.strip()[:-5]
        )

    def send_message(self, chat_id, text, *args, **kwargs):
        start = time.time()
        resp = requests.post(f"{self.endpoint}/sendMessage", params={
            "token": self.token, 'chatId': chat_id, 'body': text
        }).json()
        print("whatsapp send_message", time.time() - start, resp)
        if not resp.get('sent', False):
            return False
        return True

    def get_attach(self, filename, url):
        if url:
            return f"https://chatlead.io{url}"
        # if filename and os.path.exists(filename):
        #     with open(filename, 'rb') as file:
        #         return file.read()

    def send_file(self, chat_id, filename=None, url=None, **kwargs):
        # return True
        try:
            url = self.get_attach(filename, url)
            return requests.post(f"{self.endpoint}/sendFile", params={"token": self.token, "chatId": chat_id,
                                                                      "body": url, "filename": "file.jpg"}).json()
        except:
            return True

    def send_photo(self, chat_id, filename=None, url=None, **kwargs):
        return self.send_file(chat_id, url=url)

    def send_audio(self, chat_id, filename=None, url=None, **kwargs):
        return self.send_file(chat_id, url=url)

    def send_video(self, chat_id, filename=None, url=None, **kwargs):
        return self.send_file(chat_id, url=url)

    def broadcast(self, text, tag=""):
        # "metadata": {"isGroup": false}
        count = 0
        dialogs = requests.get(f"{self.endpoint}/dialogs", params={"token": self.token}).json()["dialogs"]
        for chat in dialogs:
            if count % 12 == 0:
                time.sleep(60)
            try:
                if not tag or (WhatsAppUsers.objects.filter(manager=self.manager,
                                                            user_id=chat["id"]).exists() and WhatsAppUsers.objects.get(
                    manager=self.manager, user_id=chat["id"]).tag == tag):
                    self.message_routine(text, self.BotUsers(manager=self.manager, user_id=chat["id"]))
            except Exception:
                print(traceback.format_exc())
        return count

    def get_dialogs_count(self):
        try:
            return len(requests.get(f"{self.endpoint}/dialogs", params={"token": self.token}).json()["dialogs"])
        except Exception:
            return 0

    def exports_dialogs(self):
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet["A1"] = "name"
        sheet["B1"] = "id"
        sheet["C1"] = "image"
        dialogs = requests.get(f"{self.endpoint}/dialogs", params={"token": self.token}).json()["dialogs"]
        for i, chat in enumerate(dialogs, 2):
            sheet[f"A{i}"] = chat.get("name", "")
            sheet[f"B{i}"] = chat.get("id", "")
            sheet[f"C{i}"] = chat.get("image", "")
        wb.save(os.path.join(settings.DASE_DIR, "GUI", "static", "dialogs", f"{self.manager.id}_whatsapp.xlsx"))

    def get_screenshot(self):
        return requests.Request("GET", f"{self.endpoint}/screenshot", params={"token": self.token}).prepare().url

    def save_screenshot(self):
        with open(os.path.join(settings.BASE_DIR, "GUI", "static", "screenshots", f"{self.manager.id}.png"),
                  "wb") as file:
            file.write(requests.get(self.get_screenshot()).content)

    def get_qr(self):
        return requests.Request("GET", f"{self.endpoint}/qr_code", params={"token": self.token}).prepare().url

    def save_qr(self):
        with open(os.path.join(settings.BASE_DIR, "GUI", "static", "qr", f"{self.manager.id}.png"), "wb") as file:
            file.write(requests.get(self.get_qr()).content)

    def update_status(self):
        response = requests.get(f"{self.endpoint}/status", params={"token": self.token}).json()
        status = response.get("accountStatus", "")
        manager = Manager.objects.get(id=self.manager.id)
        manager.whatsapp_status = status
        manager.save()

    def get_status(self):
        response = requests.get(f"{self.endpoint}/status", params={"token": self.token}).json()
        status = response.get("accountStatus", "")
        substatus = response.get("statusData", {}).get("substatus", "")
        title = response.get("statusData", {}).get("title", "")
        msg = response.get("statusData", {}).get("msg", "")
        submsg = response.get("statusData", {}).get("submsg", "")
        link = response.get("statusData", {}).get("actions", {}).get("learn_more", {}).get("link", "")
        logout = response.get("statusData", {}).get("actions", {}).get("logout", {}).get("act", "")
        return [(status, substatus, title, msg, submsg, link, logout)]

    def get_updates(self):
        lastMessageNumber = WhatsAppReceivedMsg.objects.filter(manager=self.manager).aggregate(
            models.Max('message_number')
        )['message_number__max'] or 0
        start = time.time()
        messages = requests.get(f"{self.endpoint}/messages", params={
            "token": self.token,
            "lastMessageNumber": lastMessageNumber,
        }).json()["messages"]
        return messages

    def proccess_messages_without_answers(self):
        lastMessageNumber = 0
        received = []
        sended = []
        while True:
            response = requests.get(f"{self.endpoint}/messages", params={
                "token": self.token,
                "lastMessageNumber": lastMessageNumber
            }).json()
            print(response.get("lastMessageNumber", 0))
            if lastMessageNumber >= response.get("lastMessageNumber", 0):
                break
            lastMessageNumber = response["lastMessageNumber"]
            print(lastMessageNumber)

            for msg in response["messages"]:
                print(len(sended), len(received))
                if msg["fromMe"]:
                    sended.append(msg)
                else:
                    received.append(msg)

        for msg in received:
            proc = False
            for send_msg in sended:
                if send_msg["chatId"] == msg["chatId"] and send_msg["time"] >= msg["time"]:
                    print(msg["messageNumber"], "could be proccessed by", send_msg["messageNumber"])
                    proc = True
                    break
            if not proc:
                if not WhatsAppReceivedMsg.objects.filter(
                        manager=self.manager, message_number=msg["messageNumber"], chat_id=msg["chatId"]
                ).exists():
                    print("new proccess", msg["messageNumber"])
                    message = WhatsAppReceivedMsg(
                        manager=self.manager,
                        text=msg["body"],
                        chat_id=msg["chatId"],
                        user_id=msg["author"],
                        sender_name=msg["senderName"],
                        time=msg["time"],
                        message_number=msg["messageNumber"],
                        user_data=json.dumps({'username': msg["senderName"]}),
                    )
                    result = self.proccess_message(message)
                    message.proccessed = result
                    message.save()
                else:
                    print("proccess", msg["messageNumber"])
                    result = self.proccess_message(WhatsAppReceivedMsg.objects.get(
                        manager=self.manager, message_number=msg["messageNumber"], chat_id=msg["chatId"]
                    ))

    def load_last_messages(self):
        messages = requests.get(f"{self.endpoint}/messages", params={
            "token": self.token, "last": "true",
        }).json()["messages"]
        for message in messages:
            if not WhatsAppReceivedMsg.objects.filter(manager=self.manager,
                                                      message_number=message["messageNumber"]).exists():
                WhatsAppReceivedMsg(
                    manager=self.manager,
                    text=message["body"],
                    chat_id=message["chatId"],
                    user_id=message["author"],
                    sender_name=message["senderName"],
                    time=message["time"],
                    message_number=message["messageNumber"],
                    user_data=json.dumps({'username': message["senderName"]}),
                    proccessed=True,
                ).save()
            else:
                msg = WhatsAppReceivedMsg.objects.get(manager=self.manager, message_number=message["messageNumber"])
                msg.proccessed = True
                msg.save()

    def message_handler(self):

        while self.manager.whatsapp:
            try:
                for message in self.get_updates():
                    try:
                        if not self.manager.whatsapp:
                            break
                        if message["fromMe"] or message["chatId"] != message["author"]:
                            continue
                        print("WhatsAppReceivedMsg: ", message["chatId"],
                              datetime.now().timestamp() - int(message["time"]))
                        msg = WhatsAppReceivedMsg(
                            manager=self.manager,
                            text=message["body"],
                            chat_id=message["chatId"],
                            user_id=message["author"],
                            sender_name=message["senderName"],
                            time=message["time"],
                            message_number=message["messageNumber"],
                            user_data=json.dumps({'username': message["senderName"]}),
                        )
                        result = self.proccess_message(msg)
                        if result:
                            msg.proccessed = result
                            msg.save()
                    except Exception:
                        print(traceback.format_exc())
            # time.sleep(1)
            except Exception:
                print(traceback.format_exc())


class BotsManager():
    bots_manager = {}
    bots_classes = {
        "whatsapp": WhatsAppBot,
        "telegram": TelegramBot,
        "vk": VkBot,
        "facebook": FacebookBot,
    }

    @classmethod
    def init(cls, manager, bots="all"):
        if bots == "all":
            bots = ["whatsapp", "telegram", "vk", "facebook"]

        cls.stop(manager, bots)

        for bot_place in bots:
            cls.bots_manager.setdefault(manager.id, {}).update({
                bot_place: cls.bots_classes[bot_place](manager)
            })

    @classmethod
    def start(cls, manager, bots="all"):
        if bots == "all":
            bots = ["whatsapp", "telegram", "vk", "facebook"]

        for bot_place in bots:
            if bot_place not in cls.bots_manager.setdefault(manager.id, {}):
                if not cls.bots_classes[bot_place].can_work(manager):
                    setattr(manager, bot_place, False)
                    manager.save()
                    continue
                cls.init(manager, bots=[bot_place])
            cls.bots_manager.get(manager.id, {}).get(bot_place, None).start()

    @classmethod
    def stop(cls, manager, bots="all"):
        if bots == "all":
            bots = ["whatsapp", "telegram", "vk", "facebook"]
        print("STOP IN BOTSMANAGER", bots)

        print(cls.bots_manager)
        for bot_place in bots:
            print(bot_place)
            if bot_place in cls.bots_manager.get(manager.id, {}):
                cls.bots_manager.get(manager.id, {}).get(bot_place, None).stop()

    @classmethod
    def fix_work_status(cls, manager, bots="all"):
        if bots == "all":
            bots = ["whatsapp", "telegram", "vk", "facebook"]

        for bot_place in bots:
            if bot_place not in cls.bots_manager.setdefault(manager.id, {}):
                if not cls.bots_classes[bot_place].can_work(manager):
                    setattr(manager, bot_place, False)
                    manager.save()
                    continue
                cls.init(manager, bots=[bot_place])
            cls.bots_manager.get(manager.id, {}).get(bot_place, None).fix_work_status()

    @classmethod
    def broadcast(cls, manager, text, tag="", bots="all"):
        if bots == "all":
            bots = ["whatsapp", "telegram", "vk", "facebook"]

        count = 0
        for bot_place in bots:
            print(bot_place, "1")
            if bot_place in cls.bots_manager.setdefault(manager.id, {}):
                print(bot_place, "2")
                trigger = text.triggers.all()
                if trigger.exists():
                    trigger = trigger[0]
                else:
                    return 0
                count += cls.bots_manager.get(manager.id, {}).get(bot_place, None).broadcast(trigger.messages, tag)
        return count

    @classmethod
    def get_dialogs_count(cls, manager, bots="all"):
        if bots == "all":
            bots = ["whatsapp", "telegram", "vk", "facebook"]

        count = 0
        for bot_place in bots:
            if bot_place in cls.bots_manager.setdefault(manager.id, {}):
                count += cls.bots_manager.get(manager.id, {}).get(bot_place, None).get_dialogs_count()
        return count


class Manager(models.Model):
    user = models.ForeignKey('User', on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=1024, null=True, blank=True, unique=False, default="")

    bitrix_key = models.CharField(max_length=1024, null=True, blank=True, unique=False, default="")
    bitrix_domain = models.CharField(max_length=1024, null=True, blank=True, unique=False, default="")
    amocrm_domain = models.CharField(max_length=1024, null=True, blank=True, unique=False, default="")
    application_email = models.CharField(max_length=1024, null=True, blank=True, unique=False, default="")
    application_whatsapp_id = models.CharField(max_length=1024, null=True, blank=True, unique=False, default="")
    application_will_send = models.BooleanField(default=False)
    whatsapp = models.BooleanField(default=False)
    telegram = models.BooleanField(default=False)
    vk = models.BooleanField(default=False)
    facebook = models.BooleanField(default=False)

    whatsapp_status = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")
    whatsapp_token = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")
    whatsapp_instance = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")

    telegram_token = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")
    telegram_name = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")

    vk_group_id = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")
    vk_group_access_token = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")
    vk_name = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")

    facebook_token = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")
    facebook_group_id = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")
    facebook_name = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")

    send_welcome_notif = models.BooleanField(default=False)
    welcome_notif_text = models.CharField(max_length=512, null=True, blank=True, unique=False, default="")
    welcome_admin_id = models.CharField(max_length=256, null=True, blank=True, unique=False, default="")

    default_response = models.CharField(max_length=4096, null=True, blank=True, unique=False, default="")
    welcome_message = models.CharField(max_length=4096, null=True, blank=True, unique=False, default="")
    payed = models.BooleanField(default=False)
    payed_end_date = models.IntegerField(null=True, blank=True, unique=False, default=0)

    def __str__(self):
        return f"[#{self.id}]"

    def get_pay_link(self, amount=100, description="Бот"):
        return f"https://api.paybox.money/payment.php?pg_merchant_id=518428&pg_amount={amount}&pg_currency=KZT&pg_description={description}&pg_salt=S1IpuJvrOSQqqjph&pg_language=ru&pg_sig=44fea46f0f958736d97bae83ff4e071b"

    def get_absolute_url(self):
        return reverse('manager', args=[str(self.id)])

    def get_bot(self, bot):
        return BotsManager.bots_manager.get(self.id, {}).get(bot, BotsManager.bots_classes.get(bot, None)(self))

    @property
    def get_whatsapp(self):
        return self.get_bot("whatsapp")

    def start(self, bots="all"):
        BotsManager.start(self, bots=bots)

    def stop(self, bots="all"):
        print("STOP IN MANAGER")
        BotsManager.stop(self, bots=bots)

    def fix_work_status(self, bots="all"):
        BotsManager.fix_work_status(self, bots=bots)

    def broadcast(self, text, tag="", bots="all"):
        return BotsManager.broadcast(self, text, tag=tag, bots=bots)

    def get_dialogs_count(self, bots="all"):
        return BotsManager.get_dialogs_count(self, bots=bots)

    def reload_bot(self, bot):
        if BotsManager.bots_manager.get(self.id, {}).get(bot):
            BotsManager.bots_manager.get(self.id, {})[bot].stop()
        BotsManager.bots_manager.get(self.id, {})[bot] = BotsManager.bots_classes[bot](self)
