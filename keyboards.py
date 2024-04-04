import requests
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from wallet import settings
from web_site.helpers.settings import SettingsHelper
from web_site.models import Token, Commission
from django.utils.translation import gettext as _


def aml_keyboard() -> InlineKeyboardMarkup:
    _api_url = SettingsHelper.get_url(type='api')
    tokens = requests.get(url=f'{_api_url}tokenlist/', headers={'Authorization': settings.AUTH_TOKEN}).json()

    buttons = list()
    for token in tokens:
        buttons.append(
            [
                InlineKeyboardButton(text=token['token_name'], callback_data=f'aml_{token["token_name"]}_token')
            ]
        )

    buttons.append([InlineKeyboardButton(text=_('back'), callback_data=f'aml_aml')])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def token_networks(token_name) -> InlineKeyboardMarkup:
    token = Token.objects.filter(token_name=token_name).first()

    networks = token.network.all()

    buttons = list()
    for network in networks:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=network.network_name,
                    callback_data=f'aml_{token_name}_{network.network_type}_network'
                )
            ]
        )
    buttons.append([InlineKeyboardButton(text=_('back'), callback_data=f'aml_aml')])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment_keyboard() -> InlineKeyboardMarkup:
    prices = Commission.objects.all().order_by('token__priority_level')

    tokens = list()
    buttons = list()
    for price in prices:
        if price.token.token_name not in tokens:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=price.token.token_name,
                        callback_data=f'aml_{price.token.token_name}_payment'
                    )
                ]
            )
            tokens.append(price.token.token_name)
    buttons.append([InlineKeyboardButton(text=_('back'), callback_data=f'aml_aml')])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
