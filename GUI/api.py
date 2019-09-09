import json
import os
import pathlib
import random
import string
import traceback
from datetime import datetime

import requests
from chat_api import settings
from chat_api.settings import REDIRECT_BASE, FB_CLIENT_ID, VK_CLIENT_ID
from chat_api.settings import UPLOAD_PATH
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .models import User, Manager, Trigger, BroadcastMessages, Tag, Scenario, AutoRide, WhatsAppUsers, TelegramUsers, \
    VkUsers, FacebookUsers


class UsersVk():
    users = {}


class UsersFacebook():
    users = {}


def uuid():
    return f"{datetime.now().timestamp()}-" + "-".join(
        "".join(random.choices(string.ascii_letters, k=4)) for _ in range(4))


def have_all_fields(dictionary, keys):
    for key in keys:
        if key not in dictionary or not dictionary[key]:
            return False
    return True


class ApiException(Exception):
    pass


class AuthManager():

    @classmethod
    def check_user_token(cls, user_token):
        if user_token in [user.user_token for user in User.objects.all()]:
            return True
        raise ApiException("Wrong user_token")

    @classmethod
    def get_user_token(cls, login, password):
        try:
            user = User.objects.get(email=login, password=password)
        except Exception as error:
            raise ApiException(str(error))
        if not user.user_token:
            user.user_token = uuid()
            user.save()
        return user.user_token

    @classmethod
    def get_manager(cls, user_token, manager_id):
        cls.check_user_token(user_token)
        try:
            manager = Manager.objects.get(id=manager_id)
        except Exception as error:
            raise ApiException(str(error))
        if manager.user.user_token == user_token:
            return manager
        raise ApiException("Access denied")


class BaseApiMethod():
    methods = ("POST",)
    required_params = ()
    optional_params = ()

    def __init__(self):
        self.methods = self.__class__.methods
        self.required_params = self.__class__.required_params
        self.optional_params = self.__class__.optional_params

    def debug(func):
        def new_func(self, request):
            try:
                return func(self, request)
            except Exception:
                print(traceback.format_exc())
                return HttpResponse(str(traceback.format_exc()))

        return new_func

    @csrf_exempt
    @debug
    def view(self, request):
        if request.method in self.methods:
            get_data = request.GET.dict()
            post_data = request.POST.dict()
            data = {**get_data, **post_data}

            if not have_all_fields(data, self.required_params):
                return HttpResponse(json.dumps({
                    "ok": False,
                    "desc": f"Not enough data {self.required_params}. Received {tuple(data.keys())}"
                }))

            for param in self.required_params + tuple(param for param in self.optional_params if param in data):
                if f"clear_{param}" in dir(self):
                    result = self.__getattribute__(f"clear_{param}")(data[param])
                    if not result["ok"]:
                        return HttpResponse(json.dumps({
                            "ok": False, **result
                        }))
                    data[param] = result["value"]

            if "clear" in dir(self):
                result = self.clear(data)
                if not result["ok"]:
                    return HttpResponse(json.dumps({
                        "ok": False, **result
                    }))
                data = result["value"]

            return HttpResponse(json.dumps({
                **self.proccess(data)
            }))

        return HttpResponse(json.dumps({
            "ok": False,
            "desc": f"Used unavailabled method {request.method}. Available: {self.methods}",
        }))

    def proccess(self, data):
        return {"ok": True}


class GetUserToken(BaseApiMethod):
    required_params = ("login", "password",)

    def proccess(self, data):
        try:
            user_token = AuthManager.get_user_token(data["login"], data["password"])
        except Exception as error:
            return {"ok": False, "desc": str(error)}
        return {"ok": True, "user_token": user_token}


class CreateUser(BaseApiMethod):
    required_params = ("login", "password",)
    optional_params = ("ref", 'utm_source')

    def proccess(self, data):
        try:
            user = User(email=data["login"], password=data["password"])
            user.user_token = uuid()
            utm = data.get('utm_source')
            if utm:
                user.utm_source = utm
            ref = data.get('ref')
            if ref:
                user.ref = ref
            user.save()
        except Exception as error:
            return {"ok": False, "desc": str(error)}
        return {"ok": True, "user_token": user.user_token}


class GetRefLink(BaseApiMethod):
    required_params = ("user_token",)

    def proccess(self, data):
        try:
            user = User(user_token=data["user_token"])
            if user:
                return {"ok": True, "ref_url": f"my.chatlead.io/SignUp?ref={user.id}"}
        except Exception as error:
            return {"ok": False, "desc": str(error)}
        return {"ok": False}


def manager_info(manager):
    return {
        "id": manager.id,
        "name": manager.name,
        "amocrm_domain": manager.amocrm_domain,
        "bitrix_key": manager.bitrix_key,
        "bitrix_domain": manager.bitrix_domain,
        "application_email": manager.application_email,
        "application_whatsapp_id": manager.application_whatsapp_id,
        "application_will_send": manager.application_will_send,
        "facebook_token": manager.facebook_token,
        "facebook_group_id": manager.facebook_group_id,
        "telegram_token": manager.telegram_token,
        "vk_group_id": manager.vk_group_id,
        "vk_group_access_token": manager.vk_group_access_token,
        "whatsapp_token": manager.whatsapp_token,
        "whatsapp_instance": manager.whatsapp_instance,
        "welcome_message": manager.welcome_message,
        "default_response": manager.default_response,
        "facebook_name": manager.facebook_name,
        "vk_name": manager.vk_name,
        "telegram_name": manager.telegram_name,
        "whatsapp_status": manager.whatsapp_status,
        "payed": manager.payed,
        "payed_end_date": manager.payed_end_date
    }


class GetUserManagers(BaseApiMethod):
    required_params = ("user_token",)

    def proccess(self, data):
        try:
            user = User.objects.get(user_token=data["user_token"])
        except Exception as error:
            return {"ok": False, "desc": str(error)}
        return {
            "ok": True,
            "managers": [manager_info(manager) for manager in Manager.objects.filter(user=user)]
        }


class CreateManager(BaseApiMethod):
    required_params = ("user_token",)
    optional_params = ("name",)

    def proccess(self, data):
        try:
            user = User.objects.get(user_token=data["user_token"])
            manager = Manager(user=user, name=data.get("name", ""))
            manager.save()
        except Exception as error:
            return {"ok": False, "desc": str(error)}
        return {"ok": True, "manager": manager_info(manager)}


class GetManager(BaseApiMethod):
    required_params = ("user_token", "manager_id")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
        except ApiException as error:
            return {"ok": False, "desc": str(error)}
        return {
            "ok": True,
            "manager": manager_info(manager)
        }


class GetPaymentLink(BaseApiMethod):
    required_params = ("user_token", "manager_id", "amount", "description")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            return {"ok": True, "url": manager.get_pay_link(data['amount'], data['description'])}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


class EditManager(BaseApiMethod):
    required_params = ("user_token", "manager_id")
    optional_params = (
        "name", "amocrm_domain", "bitrix_key", "bitrix_domain", "application_email", "application_whatsapp_id",
        "facebook_token", "facebook_group_id",
        "telegram_token", "vk_group_id", "vk_group_access_token", "whatsapp_token", "whatsapp_instance",
        "welcome_message", "default_response", 'application_will_send'
    )

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
        except ApiException as error:
            return {"ok": False, "desc": str(error)}
        for field in self.optional_params:
            value = data.get(field)
            if value:
                if value == 'true':
                    value = 'True'
                elif value == 'false':
                    value = "False"
                setattr(manager, field, value)
        # restart = False
        # for field in ["facebook_token", "facebook_group_id", "telegram_token", "vk_group_id", "vk_group_access_token",
        #               "whatsapp_token", "whatsapp_instance"]:
        #     if field in data:
        #         restart = True
        manager.stop()
        manager.start('all')
        manager.save()
        return {"ok": True, "manager": manager_info(manager)}


class DeleteManager(BaseApiMethod):
    required_params = ("user_token", "manager_id")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            manager.delete()
            return {"ok": True}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


class GetTagsMessages(BaseApiMethod):
    required_params = ("user_token", "manager_id")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            tags = {}
            for message in BroadcastMessages.objects.filter(manager=manager):
                tag = message.tag
                tags[tag] = {"count": 0, "socials": {}}
                for social, users in [("whatsapp", WhatsAppUsers), ("telegram", TelegramUsers), ("vk", VkUsers),
                                      ("facebook", FacebookUsers)]:
                    count = len(users.objects.filter(tag__in=tag))
                    tags[tag]["count"] += count
                    tags[tag]["social"][social] = count
            return {"ok": True, "tags": tags}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


def broadcast_info(broadcast):
    return {
        "id": broadcast.id,
        "scenario": scenario_info(broadcast.scenario),
        "tag": broadcast.tag,
        "time": broadcast.time,
        "users_count": broadcast.users_count,
        "sent": broadcast.sent,
        "proccessing": broadcast.proccessing
    }


class GetBroadcastMessages(BaseApiMethod):
    required_params = ("user_token", "manager_id")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
        except ApiException as error:
            return {"ok": False, "desc": str(error)}
        return {
            "ok": True,
            "broadcasts": [
                broadcast_info(broadcast)
                for broadcast in BroadcastMessages.objects.filter(manager=manager)
            ]
        }


class CreateBroadcast(BaseApiMethod):
    required_params = ("user_token", "manager_id", "scenario_id", "time")
    optional_params = ("tag",)

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            broadcast = BroadcastMessages(
                manager=manager,
                scenario=Scenario.objects.get(manager=manager, id=data['scenario_id']),
                tag=data.get('tag', ''),
                time=data["time"],
            )
            broadcast.save()
            return {"ok": True, 'broadcast': broadcast_info(broadcast)}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


class EditBroadcast(BaseApiMethod):
    required_params = ("user_token", "manager_id", "broadcast_id")
    optional_params = ("tag", "scenario_id", "time", "sent")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            broadcast = BroadcastMessages.objects.get(id=data['broadcast_id'], manager=manager)
            scenario_id = data.get('scenario_id')
            if scenario_id:
                broadcast.scenario = Scenario.objects.get(id=scenario_id, manager=manager)
            tag = data.get('tag')
            if tag:
                broadcast.tag = tag
            time = data.get('time')
            if time:
                broadcast.time = time
            sent = data.get('sent')
            if sent:
                broadcast.sent = sent
            broadcast.save()
            return {"ok": True, 'broadcast': broadcast_info(broadcast)}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


class DeleteBroadcast(BaseApiMethod):
    required_params = ("user_token", "manager_id", "broadcast_id")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            broadcast = BroadcastMessages.objects.get(manager=manager, id=data['broadcast_id'])
            broadcast.delete()
            return {"ok": True}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


class FacebookAuth(BaseApiMethod):
    required_params = ("user_token", "manager_id")
    optional_params = ("data",)

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            UsersFacebook.users.update({manager.id: {
                "manager": manager,
                "state": "get_user_code"
            }})
            url = requests.Request("GET", "https://www.facebook.com/v3.2/dialog/oauth", params={
                "client_id": FB_CLIENT_ID,
                "response_type": "code",
                "redirect_uri": f"{REDIRECT_BASE}/fb_api",
                "state": manager.id,
                "scope": "public_profile,manage_pages,pages_messaging,pages_messaging_subscriptions",
            }).prepare().url
            return {'state': 'get_user_code', 'url': url}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


class UploadFile(BaseApiMethod):
    required_params = ("user_token", "manager_id", "type", "file")

    def send_response(self, response):
        return HttpResponse(json.dumps(response))

    def random_filename(self, filename=None, length=8):
        ext = pathlib.Path(filename).suffix
        letters = string.ascii_lowercase
        return f"{''.join(random.choice(letters) for i in range(length))}{ext}"

    @csrf_exempt
    def view(self, request):
        try:
            data = request.POST.dict()
            file = request.FILES.get('file')
            token = data.get("user_token")
            manager_id = data.get("manager_id")
            file_type = data.get('type')
            if not (file and token and manager_id and file_type in ['photo', 'audio', 'video', 'file']):
                return self.send_response({'ok': False, 'desk': "fill all params"})
            manager = AuthManager.get_manager(token, manager_id)
            if manager:
                url = os.path.join(str(manager.user.id), str(manager.id), file_type, self.random_filename(file.name))
                filename = os.path.join(UPLOAD_PATH, url)
                if not os.path.exists(os.path.dirname(filename)):
                    os.makedirs(os.path.dirname(filename))
                with open(filename, 'wb') as save_file:
                    uploaded_file = file.read()
                    save_file.write(uploaded_file)
                return self.send_response(
                    {'ok': True, "message": {file_type: {'filename': filename, "url": f"/app/media/{url}"}}})
            return self.send_response({'ok': False, 'desk': 'some wrong'})
        except Exception as e:
            return self.send_response({'ok': False, 'desk': str(e)})


class VkAuth(BaseApiMethod):
    required_params = ("user_token", "manager_id")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])

            UsersVk.users.update({manager.id: {"manager": manager, "state": "get_user_code"}})
            url = requests.Request("GET", "https://oauth.vk.com/authorize", params={
                "client_id": VK_CLIENT_ID,
                "display": "page",
                "redirect_uri": f"{REDIRECT_BASE}/vk_api/{manager.id}",
                "scope": "groups",
                "response_type": "code",
                "v": "5.95"}).prepare().url
            return {'ok': True, "url": url}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


class VkAuthGroup(BaseApiMethod):
    required_params = ("user_token", "manager_id", "group_id", "group_name")

    def proccess(self, data):
        manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
        UsersVk.users[manager.id].update({
            "group_id": data.get('group_id'),
            "state": "get_group_code",
            "group_name": data["group_name"]
        })
        return {"ok": True, "url": requests.Request("GET", "https://oauth.vk.com/authorize", params={
            "client_id": settings.VK_CLIENT_ID,
            "scope": "messages,docs",
            "group_ids": data.get('group_id'),
            "redirect_uri": f"{REDIRECT_BASE}/vk_api/{manager.id}",
            "response_type": "code",
            "v": "5.95",
        }).prepare().url}


def trigger_info(trigger):
    return {'id': trigger.id, 'keyboard': trigger.keyboard, 'messages': trigger.messages, 'caption': trigger.caption,
            'tags': [{'action': tag.action, 'tag_name': tag.tag_name} for tag in trigger.tags.all()]}


def scenario_info(scenario):
    return {
        "id": scenario.id,
        "destination": scenario.destination,
        "trigger_text": scenario.trigger_text,
        "triggers": [trigger_info(trigger) for trigger in
                     Trigger.objects.filter(scenario=scenario)]
    }


class GetScenarios(BaseApiMethod):
    required_params = ("user_token", "manager_id")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
        except ApiException as error:
            return {"ok": False, "desc": str(error)}
        return {
            "ok": True,
            "scenarios": [scenario_info(scenario) for scenario in Scenario.objects.filter(manager=manager)]
        }


class GetQRCodeUrl(BaseApiMethod):
    required_params = ("user_token", "manager_id")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            if manager.get_bot('whatsapp') and manager.get_bot('whatsapp').instance and manager.get_bot(
                    'whatsapp').token:
                return {
                    "ok": True,
                    "url": manager.get_bot('whatsapp').get_qr()
                }
            return {
                "ok": False,
                "desk": "whatsapp bot not found"
            }
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


class CreateScenario(BaseApiMethod):
    required_params = ("user_token", "manager_id", "trigger_text")
    optional_params = ('destination',)

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            scenario = Scenario(manager=manager, trigger_text=data['trigger_text'])
            if data.get('destination'):
                scenario.destination = data.get('destination', '')
            scenario.save()
            Trigger(scenario=scenario, caption='Начальный шаг').save()
            return {"ok": True, 'scenario': scenario_info(scenario)}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


class GetScenario(BaseApiMethod):
    required_params = ("user_token", "manager_id", "scenario_id")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            scenario = Scenario.objects.get(manager=manager, id=data['scenario_id'])
            return {"ok": True, 'scenario': scenario_info(scenario)}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


class EditScenario(BaseApiMethod):
    required_params = ("user_token", "manager_id", "scenario_id", "trigger_text")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            scenario = Scenario.objects.get(manager=manager, id=data['scenario_id'])
            scenario.trigger_text = data['trigger_text']
            scenario.save()
            return {"ok": True, 'scenario': scenario_info(scenario)}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


class DeleteScenario(BaseApiMethod):
    required_params = ("user_token", "manager_id", "scenario_id")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            scenario = Scenario.objects.get(manager=manager, id=data['scenario_id'])
            scenario.delete()
            return {"ok": True}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


def create_tags(data, trigger):
    for field, target in [("AddTags", 'add'), ("RemoveTags", 'remove')]:
        for tag_name in data.get(field, '').split(','):
            if tag_name:
                if not Tag.objects.filter(action=target, tag_name=tag_name.strip(), trigger=trigger).exists():
                    tag = Tag(action=target, tag_name=tag_name.strip(), trigger=trigger)
                    tag.save()


class CreateTrigger(BaseApiMethod):
    required_params = ("user_token", "manager_id", "scenario_id", "messages")
    optional_params = ("caption", "AddTags", "RemoveTags", 'keyboard')

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            scenario = Scenario.objects.get(id=data.get('scenario_id'), manager=manager)
            step = f"{len(Trigger.objects.filter(scenario=scenario)) + 1} шаг"
            trigger = Trigger(caption=data.get('caption', step) or step, scenario=scenario, social='telegram',
                              messages=json.loads(data.get('messages', '[]')),
                              keyboard=json.loads(data.get('keyboard', '{}')))
            trigger.save()
            create_tags(data, trigger)
            return {"ok": True, 'trigger': trigger_info(trigger)}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


class EditTrigger(BaseApiMethod):
    required_params = ("user_token", "trigger_id")
    optional_params = ("messages", "caption", "AddTags", "RemoveTags", "clear_tags", 'keyboard')

    def proccess(self, data):
        try:
            # manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            trigger = Trigger.objects.get(id=data['trigger_id'])
            user = User.objects.get(user_token=data['user_token'])

            if not trigger.scenario.manager.user == user:
                raise ApiException('Bad request 403')

            caption = data.get('caption')
            if caption:
                trigger.caption = caption
            create_tags(data, trigger)
            for tag_name in data.get('clear_tags', '').split(','):
                if tag_name:
                    tag = Tag.objects.filter(trigger=trigger, tag_name=tag_name.strip())
                    if tag.exists():
                        tag[0].delete()
            messages = data.get('messages')
            keyboard = json.loads(data.get('keyboard', '{}'))
            if keyboard:
                trigger.keyboard = keyboard
            if messages:
                trigger.messages = json.loads(messages)
            trigger.save()
            return {"ok": True, 'trigger': trigger_info(trigger)}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


class DeleteTrigger(BaseApiMethod):
    required_params = ("user_token", "trigger_id")

    def proccess(self, data):
        try:
            # manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            user = User.objects.get(user_token=data['user_token'])
            trigger = Trigger.objects.get(id=data['trigger_id'])
            if not trigger.scenario.manager.user == user:
                raise ApiException('Bad request 403')
            trigger.delete()
            return {"ok": True}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


class GetTrigger(BaseApiMethod):
    required_params = ("user_token", "trigger_id")

    def proccess(self, data):
        try:
            user = User.objects.get(user_token=data['user_token'])
            trigger = Trigger.objects.get(id=data['trigger_id'])
            if not trigger.scenario.manager.user == user:
                raise ApiException('Bad request 403')
            return {"ok": True, 'trigger': trigger_info(trigger)}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


class LaunchBots(BaseApiMethod):
    required_params = ("user_token", "manager_id", "state")
    optional_params = ("telegram", "whatsapp", "vk", "facebook")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            bots = [bot for bot in ["whatsapp", "telegram", "vk", "facebook"] if data.get(bot)]
            if not bots:
                bots = 'all'
            if data.get('state') == 'start':
                manager.start(bots)
            else:
                manager.stop(bots)

        except ApiException as error:
            return {"ok": False, "desc": str(error)}
        return {"ok": True}


class StateBots(BaseApiMethod):
    required_params = ("user_token", "manager_id")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            manager.fix_work_status()
            return {"ok": True,
                    'states': {'whatsapp': manager.whatsapp, 'facebook': manager.facebook, 'telegram': manager.telegram,
                               'vk': manager.vk}}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


def auto_ride_info(auto_ride):
    return {"id": auto_ride.id, "trigger_text": auto_ride.trigger_text,
            "scenario": scenario_info(auto_ride.scenario)}


class GetAutoRide(BaseApiMethod):
    required_params = ("user_token", "manager_id")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
        except ApiException as error:
            return {"ok": False, "desc": str(error)}
        return {
            "ok": True,
            "auto_rides": [auto_ride_info(auto_ride) for auto_ride in AutoRide.objects.filter(manager=manager)]
        }


class GetAutoRideLink(BaseApiMethod):
    required_params = ("user_token", "manager_id", "autoride_id", "social")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            auto_ride = AutoRide.objects.get(manager=manager, id=data['autoride_id'])
            social = data['social']
            auto_ride_text = auto_ride.trigger_text
            if social == 'vk':
                link = f"vk.com/write-{manager.vk_group_id}?ref_source={auto_ride_text}"
            elif social == 'telegram':
                link = f"t.me/{manager.telegram_name}?start={auto_ride_text}"
            elif social == 'facebook':
                link = f"m.me/{manager.facebook_group_id}?ref={auto_ride_text}"
            elif social == 'whatsapp':
                link = f"https://api.whatsapp.com/send?phone={manager.whatsapp_instance}&text={auto_ride_text}"
            else:
                return {"ok": True, "links": {
                    "vk": f"vk.com/write-{manager.vk_group_id}?ref_source={auto_ride_text}",
                    'telegram': f"t.me/{manager.telegram_name}?start={auto_ride_text}",
                    'facebook': f"m.me/{manager.facebook_group_id}?ref={auto_ride_text}",
                    'whatsapp': f"https://api.whatsapp.com/send?phone={manager.whatsapp_instance}&text={auto_ride_text}"
                }}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}
        return {
            "ok": True,
            "link": link
        }


class CreateAutoRide(BaseApiMethod):
    required_params = ("user_token", "manager_id", "trigger_text", "scenario_id")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            auto_ride = AutoRide(manager=manager, trigger_text=data['trigger_text'],
                                 scenario=Scenario.objects.get(id=data['scenario_id']))
            auto_ride.save()
            return {"ok": True, 'auto_ride': auto_ride_info(auto_ride)}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


class EditAutoRide(BaseApiMethod):
    required_params = ("user_token", "manager_id", "auto_ride_id",)
    optional_params = ("trigger_text", "scenario_id")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            auto_ride = AutoRide.objects.get(manager=manager, id=data['auto_ride_id'])
            trigger_text = data.get('trigger_text')
            if trigger_text:
                auto_ride.trigger_text = trigger_text
            scenario = data.get('scenario_id')
            if scenario:
                auto_ride.scenario = Scenario.objects.get(id=scenario)
            auto_ride.save()
            return {"ok": True, 'auto_ride': auto_ride_info(auto_ride)}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


class DeleteAutoRide(BaseApiMethod):
    required_params = ("user_token", "manager_id", "auto_ride_id")

    def proccess(self, data):
        try:
            manager = AuthManager.get_manager(data["user_token"], data["manager_id"])
            auto_ride = AutoRide.objects.get(manager=manager, id=data['auto_ride_id'])
            auto_ride.delete()
            return {"ok": True}
        except ApiException as error:
            return {"ok": False, "desc": str(error)}


all_methods = [
    CreateUser,
    GetUserToken,
    GetRefLink,

    GetAutoRide,
    CreateAutoRide,
    EditAutoRide,
    DeleteAutoRide,
    GetAutoRideLink,
    GetUserManagers,
    CreateManager,
    GetManager,
    EditManager,
    DeleteManager,

    GetBroadcastMessages,
    CreateBroadcast,
    EditBroadcast,
    DeleteBroadcast,

    GetScenarios,
    CreateScenario,
    GetScenario,
    EditScenario,
    DeleteScenario,

    CreateTrigger,
    GetTrigger,
    EditTrigger,
    DeleteTrigger,
    GetPaymentLink,
    UploadFile,
    LaunchBots,
    StateBots,
    GetTagsMessages,
    FacebookAuth,
    VkAuth,
    VkAuthGroup,
    GetQRCodeUrl,
]
