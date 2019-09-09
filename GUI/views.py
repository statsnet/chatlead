import json
import random
import string
import traceback
from datetime import datetime

import requests
from chat_api.settings import REDIRECT_BASE as SITE_NAME
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from .api import UsersVk
from .models import Manager


def uuid():
    return f"{datetime.now().timestamp()}-" + "-".join(
        "".join(random.choices(string.ascii_letters, k=4)) for _ in range(4))


@csrf_exempt
def facebook_webhook(request):
    print(request)
    if request.method == "GET":
        return HttpResponse(request.GET.dict().get("hub.challenge", "123456789"))

    update = json.loads(request.body.decode())
    for event in update.get("entry", []):
        group_id = event.get("id")
        for manager in Manager.objects.filter(facebook=True, facebook_group_id=group_id):
            if manager.get_bot('facebook').can_work(manager):
                try:
                    manager.get_bot('facebook').proccess_event(event)
                except Exception:
                    print(traceback.format_exc())
    return HttpResponse("OK")


def fb_api(request):
    data = request.GET.dict()
    manager_id = data.get('state')
    print("MID:", manager_id)
    if "code" in data:
        manager = Manager.objects.get(id=manager_id)
        code = data["code"]
        user_access_token = requests.get("https://graph.facebook.com/v3.3/oauth/access_token", params={
            "client_id": settings.FB_CLIENT_ID,
            "client_secret": settings.FB_CLIENT_SECRET,
            "redirect_uri": f"{SITE_NAME}/fb_api",
            "code": code,
            "state": manager_id
        }).json()
        print(user_access_token)
        user_access_token = user_access_token["access_token"]
        print(user_access_token)
        groups = requests.get("https://graph.facebook.com/me/accounts",
                              params={"access_token": user_access_token}).json()
        print(groups)
        groups = groups.get("data", [])
        print(groups)
        if len(groups) > 0:
            manager.facebook_token = groups[0]["access_token"]
            manager.facebook_group_id = groups[0]["id"]
            manager.facebook_name = groups[0]['name']
            manager.save()
    return redirect(f'/beta/')
    return HttpResponseRedirect('/app')


def vk_api(request, pk):
    data = request.GET.dict()
    arg = pk
    manager = Manager.objects.get(id=arg)
    state = UsersVk.users[manager.id]["state"]
    if state == "get_user_code":
        code = data["code"]
        response = requests.get("https://oauth.vk.com/access_token", params={
            "client_id": settings.VK_CLIENT_ID,
            "client_secret": settings.VK_CLIENT_SECRET,
            "redirect_uri": f"{SITE_NAME}/vk_api/{manager.id}",
            "code": code
        }).json()
        UsersVk.users[manager.id].update({
            "user_access_token": response["access_token"],
            "user_id": response["user_id"],
            "state": "selec_group"
        })
        response = requests.get("https://api.vk.com/method/groups.get", params={
            "access_token": UsersVk.users[manager.id]["user_access_token"],
            "user_id": UsersVk.users[manager.id]["user_id"],
            "filter": "admin",
            "extended": 1,
            "count": 1000,
            "v": "5.95",
        }).json()
        groups = [{'group_id': abs(group["id"]), 'group_name': group['name']} for group in
                  response["response"]["items"]]
        return render(request, 'select_group.html',
                      {'groups': groups, 'manager_id': manager.id, 'user_token': manager.user.user_token})
        group_id = groups[0].get('id')
        UsersVk.users[manager.id].update({
            "group_id": group_id,
            "state": "get_group_code"
        })
        return HttpResponseRedirect(requests.Request("GET", "https://oauth.vk.com/authorize", params={
            "client_id": settings.VK_CLIENT_ID,
            "scope": "docs",
            "group_ids": group_id,
            "redirect_uri": f"{SITE_NAME}/vk_api/{manager.id}",
            "response_type": "code",
            "v": "5.95",
        }).prepare().url)
        # return redirect(f'/beta/bots/{manager.id}/setup', groups=groups)
        # return render(request, 'select_group.html',
        #               {'groups': groups, 'manager_id': manager.id, 'user_token': manager.user.user_token})
    elif state == "get_group_code":
        manager = UsersVk.users[manager.id]["manager"]
        code = data["code"]
        response = requests.get("https://oauth.vk.com/access_token", params={
            "client_id": settings.VK_CLIENT_ID,
            "client_secret": settings.VK_CLIENT_SECRET,
            "redirect_uri": f"{SITE_NAME}/vk_api/{manager.id}",
            "code": code
        }).json()
        print(response)
        group_id = UsersVk.users[manager.id]["group_id"]
        access_token = response[f"access_token_{group_id}"]
        manager.vk_group_access_token = access_token
        manager.vk_group_id = group_id
        manager.vk_name = UsersVk.users[manager.id]["group_name"]
        manager.save()
        return redirect(f'/beta/bots/{manager.id}/setup')

