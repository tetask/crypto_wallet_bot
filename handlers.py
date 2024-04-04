import requests

from django.http import HttpResponse
from django.utils.translation import gettext

from telegram import ParseMode
from telegram_bot.handlers.utils import get_chat_id

from wallet import settings
from web_site.helpers.settings import SettingsHelper
from web_site.models import Profile, Token, Commission, AML

# Local utilities to help generate an AML response for the Telegram user
from .aml_utils import AMLResponse

# Keyboards
from .keyboards import aml_keyboard, token_networks, payment_keyboard


class AMLHandler:
    __slots__: tuple[str] = ("bot", "data", "api_url", "telegram_id")

    def __init__(self, data: dict, bot, callback_title: str):
        self.bot = bot
        self.data: dict = data
        self.api_url: str = SettingsHelper.get_url(type='api')
        self.telegram_id: int = data['callback_query']['from']['id']

        callback_title: str = callback_title.replace('aml_', '')

        if callback_title == 'aml':
            AMLHandler.show_aml_menu(bot=self.bot, data=self.data['callback_query'])

        elif 'token' in callback_title:
            self.show_token(callback_title=callback_title)

        elif 'network' in callback_title:
            token_name, token_network, *_ = callback_title.split('_')

            self.show_token_detail(token_name=token_name, token_network=token_network)

        elif 'payment' in callback_title:
            self.show_payment_token(callback_title=callback_title)

    @staticmethod
    def show_aml_menu(bot, data: dict) -> HttpResponse:
        _chat_id: int = get_chat_id(data=data)

        user = Profile.objects.get(telegram_id=_chat_id)
        user.step = ""
        user.save()

        text = gettext('account_id') + f"<b>{_chat_id}</b>\n"
        text += gettext('selected_aml')

        bot.sendMessage(chat_id=_chat_id, text=text, reply_markup=aml_keyboard(), parse_mode=ParseMode.HTML)

        return HttpResponse(content="", status=200)

    @staticmethod
    def process_address(bot, data: dict, step: str, asset: str = "") -> HttpResponse:
        aml, token_name, network_type, payment_token, *_ = step.split("_")
        price = Commission.objects.filter(token__token_name=payment_token).first()

        if network_type == 'trc20':
            asset = 'TRX'
        elif network_type == 'erc20':
            asset = 'ETH'
        elif network_type == 'btc':
            asset = 'BTC'
        elif network_type == 'ltc':
            asset = 'LTC'
        elif network_type == 'bsc':
            asset = 'BSC'

        api_url: str = SettingsHelper.get_url(type="api")
        address: str = data['message']['text']
        json_data: dict = {'address': address, 'asset': asset}

        aml: dict = requests.post(
            url=f'{api_url}aml/',
            headers={'Authorization': settings.AUTH_TOKEN},
            json=json_data
        ).json()

        user = Profile.objects.get(telegram_id=data["message"]["from"]["id"])
        if 'lowestScore' not in aml:
            bot.sendMessage(
                chat_id=get_chat_id(data=data),
                text="Incorrect address or we don't have info about your wallet.",
                parse_mode=ParseMode.HTML
            )

            return HttpResponse(content="", status=200)

        AML.objects.create(profile=user, address=address, score=float(aml['lowestScore']))

        _message: str = AMLResponse(aml_json=aml["AML"]).result
        bot.sendMessage(chat_id=get_chat_id(data=data), text=_message, parse_mode=ParseMode.HTML)

        current_balance = requests.get(
            url=f'{api_url}balancelist/?telegram_id={data["message"]["from"]["id"]}&token_name={payment_token}',
            headers={'Authorization': settings.AUTH_TOKEN}
        ).json()[0]

        requests.patch(
            url=f'{api_url}balancelist/{data["message"]["from"]["id"]}/{payment_token}/',
            json={'amount': float(current_balance['amount']) - float(price.aml_check)},
            headers={'Authorization': settings.AUTH_TOKEN}
        )

        return HttpResponse(content="", status=200)

    def show_token(self, callback_title: str) -> HttpResponse:
        token_name = callback_title.split('_')[0]

        token = Token.objects.get(token_name=token_name)
        networks = token.network.all()
        networks_count = networks.count()

        if networks_count > 1:
            self.show_networks_by_token(token_name=token_name)
        else:
            self.show_token_detail(token_name=token_name, token_network=networks.first().network_type)

        return HttpResponse(content="", status=200)

    def show_networks_by_token(self, token_name: str) -> HttpResponse:
        message = gettext('selected') + f' <b>{token_name}</b>\n'
        message += gettext('select_chain')

        self.bot.sendMessage(
            chat_id=self.telegram_id,
            text=message,
            reply_markup=token_networks(token_name=token_name),
            parse_mode=ParseMode.HTML
        )

        return HttpResponse(content="", status=200)

    def show_token_detail(self, token_name: str, token_network) -> HttpResponse:
        token = Token.objects.get(token_name=token_name)
        network = token.network.get(network_type=token_network)

        user = Profile.objects.get(telegram_id=self.telegram_id)
        user.step = f'AML_{token_name}_{token_network}'
        user.save()

        message = gettext('selected') + f' <b>{token_name}</b>\n\n'
        message += gettext('select_chain') + f' <b>{network.network_name}</b>\n'
        message += gettext('aml_select_pay_currency')

        self.bot.sendMessage(
            chat_id=self.telegram_id,
            text=message,
            reply_markup=payment_keyboard(),
            parse_mode=ParseMode.HTML
        )

        return HttpResponse(content="", status=200)

    def show_payment_token(self, callback_title: str):
        user = Profile.objects.get(telegram_id=self.telegram_id)

        aml, token_name, token_network, *_ = user.step.split('_')

        payment_token_name = callback_title.split('_')[0]
        price = Commission.objects.filter(token__token_name=payment_token_name).first()

        balance = requests.get(
            url=f'{self.api_url}balancelist/',
            params={'telegram_id': self.telegram_id, 'token_name': payment_token_name},
            headers={'Authorization': settings.AUTH_TOKEN}
        ).json()[0]

        try:
            _checking_number = format(price.aml_check, ".1g")
            if "e-" in _checking_number:
                price.aml_check = format(price.aml_check, f".{int(_checking_number[-2:])}f")

            if float(balance['amount']) <= float(price.aml_check):
                message = f'<b>{payment_token_name}</b> ' + gettext('aml_payment_token_1') + '\n'
                message += gettext('available_balance') + f' <b>{balance["amount"]} {payment_token_name}</b>\n'
                message += gettext('fee') + f' <b>{price.aml_check} {payment_token_name}</b>\n'
                message += gettext('aml_insufficient_funds')

                self.bot.sendMessage(chat_id=self.telegram_id, text=message, parse_mode=ParseMode.HTML)

            else:
                user = Profile.objects.get(telegram_id=self.telegram_id)
                user.step = f'{user.step}_{payment_token_name}_ADDR'
                user.save()

                message = f'<b>{payment_token_name}</b> ' + gettext('aml_payment_token_1') + '\n'
                message += gettext('available_balance') + f' <b>{balance["amount"]} {payment_token_name}</b>\n'
                message += gettext('fee') + f' <b>{price.aml_check} {payment_token_name}</b>\n'
                message += gettext('aml_enter_address')

                self.bot.sendMessage(chat_id=self.telegram_id, text=message, parse_mode=ParseMode.HTML)

            return HttpResponse(content="", status=200)

        except Exception as error:
            print(f"User ({self.telegram_id}) raise an error - {error}")

            return HttpResponse(content="", status=200)
