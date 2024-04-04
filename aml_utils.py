import time

from django.utils.translation import gettext as _
from datetime import datetime
from decimal import Decimal

from telegram import ParseMode, Bot

from web_site.helpers.settings import SettingsHelper


def normalizer_for_numbers(unit: Decimal or float) -> str:
    """Convert a number to a string in a specific format."""

    return format(unit * 100, ".1f")


def normalizer_for_date(unit: str) -> str:
    """Converting a string date to a datetime object and converting back to a string in a specific format."""

    datetime_ = datetime.strptime(unit, "%Y-%m-%d %H:%M:%S")

    return datetime_.strftime("%d %B %Y %H:%M")


class AMLResponse:
    """A class for processing AML data and generating a response for the Telegram users.

    Local methods:
        __init__(dictionary)  :return None
        __generate_message()  :return String
    """

    __slots__: tuple[str] = (
        "__network",
        "__address",
        "__risk_score",
        "__other",
        "__payment",
        "__wallet",
        "__exchange",
        "__liquidity_pools",
        "__exchange_high_risk",
        "__p2p_exchange_high_risk",
        "__gambling",
        "__sanctions",
        "__stolen_coins",
        "__number_of_transactions",
        "__was_created",
        "__mode",
        "__checked_time",
        "_has_details",
        "result"
    )

    def __init__(self, aml_json: dict) -> None:
        """A magic method to initialize all the necessary data to generate a message."""

        # Address  |  Network  |  Risk score (lowestScore)
        self.__network: str = aml_json.get("data", {}).get("network")
        self.__address: str = aml_json.get("data", {}).get("address")
        self.__risk_score: str = normalizer_for_numbers(unit=aml_json.get("data", {}).get("riskscore", 0.50))

        # ✅ Low risk
        self.__other: str = normalizer_for_numbers(
            unit=aml_json.get("data", {}).get("signals", {}).get("other", 0.0)
        )
        self.__payment: str = normalizer_for_numbers(
            unit=aml_json.get("data", {}).get("signals", {}).get("payment", 0.0)
        )
        self.__wallet: str = normalizer_for_numbers(
            unit=aml_json.get("data", {}).get("signals", {}).get("wallet", 0.0)
        )
        self.__exchange: str = normalizer_for_numbers(
            unit=aml_json.get("data", {}).get("signals", {}).get("exchange", 0.0)
        )

        # ⚠️ Medium risk
        self.__liquidity_pools: str = normalizer_for_numbers(
            unit=aml_json.get("data", {}).get("signals", {}).get("liquidity_pools", 0.0)
        )
        self.__exchange_high_risk: str = normalizer_for_numbers(
            unit=aml_json.get("data", {}).get("signals", {}).get("exchange_mlrisk_high", 0.0)
        )
        self.__p2p_exchange_high_risk: str = normalizer_for_numbers(
            unit=aml_json.get("data", {}).get("signals", {}).get("p2p_exchange_mlrisk_high", 0.0)
        )

        # ⛔ High risk
        self.__gambling: str = normalizer_for_numbers(
            unit=aml_json.get("data", {}).get("signals", {}).get("gambling", 0.0)
        )
        self.__sanctions: str = normalizer_for_numbers(
            unit=aml_json.get("data", {}).get("signals", {}).get("sanctions", 0.0)
        )
        self.__stolen_coins: str = normalizer_for_numbers(
            unit=aml_json.get("data", {}).get("signals", {}).get("stolen_coins", 0.0)
        )

        # Balance  |  Number of transactions  |  Was created
        if aml_json.get("data", {}).get("addressDetailsData"):
            self.__number_of_transactions: str = aml_json.get("data", {}).get("addressDetailsData", {}).get("n_txs", None)

            if "created" in aml_json.get("data", {}).get("addressDetailsData"):
                self.__was_created: str = normalizer_for_date(unit=aml_json["data"]["addressDetailsData"]["created"])
            else:
                self.__was_created = None

            self._has_details: bool = True
        else:
            self._has_details: bool = False

        # Mode  |  Checked time
        self.__mode: str = aml_json.get("amlFlow", "").capitalize()
        self.__checked_time: str = normalizer_for_date(unit=aml_json.get("data", {}).get("timestamp", time.time()))

        # Result
        self.result: str = self.__generate_message()

        # Notify admins if the risk score is greater than 65
        if float(self.__risk_score) > 65.0:
            self.__send_admin_notification()

    def __send_admin_notification(self):
        """The method of sending a message to administrators about operations that have not passed AML"""

        api_token = SettingsHelper.get_bot_token()
        bot = Bot(token=api_token)

        admins = ['*', '*', '*', '*']

        for admin in admins:
            try:
                bot.sendMessage(
                    chat_id=admin,
                    text=f"AML Alert:\n"
                         f"User: {self.__network} - {self.__address}\n"
                         f"Risk Score: {self.__risk_score}%\n"
                         f"Checked Time: {self.__checked_time}\n",
                    parse_mode=ParseMode.HTML
                )

            except Exception as e:
                print(f"Failed to send notification to admin {admin}: {e}")

    def __generate_message(self) -> str:
        """A method for generating a correct message with all valid fields."""

        message = f"<b>{self.__network}</b> " + _("address") + f"\n{self.__address}\n\n"

        if float(self.__risk_score) < 40.0:
            message += "<b>" + _("low_risk_address") + "</b>\n"
        elif 40.0 <= float(self.__risk_score) < 65.0:
            message += "<b>" + _("aml_medium_risk_address") + "</b>\n"
        else:
            message += "<b>" + _("high_risk_address") + "</b>\n"

        message += _("risk") + f"<b>{self.__risk_score}%</b>\n\n"
        message += _("detailed_analysis") + "\n\n"

        message += _("low_risk") + "\n"

        message += _("other") + f" - <b>{self.__other}%</b>\n"
        message += _("payment_management") + f" - <b>{self.__payment}%</b>\n"
        message += _("aml_wallet") + f" - <b>{self.__wallet}%</b>\n"
        message += _("aml_exchange") + f" - <b>{self.__exchange}%</b>\n\n"

        message += _("medium_risk") + "\n"
        message += _("liquidity_pools") + f" - <b>{self.__liquidity_pools}%</b>\n"
        message += _("aml_exchange_high_risk") + f" - <b>{self.__exchange_high_risk}%</b>\n"
        message += _("high_risk_p2p_exchange") + f" - <b>{self.__p2p_exchange_high_risk}%</b>\n\n"

        message += _("high_risk") + "\n"
        message += _("gambling") + f" - <b>{self.__gambling}%</b>\n"
        message += _("aml_sanctions") + f" - <b>{self.__sanctions}%</b>\n"
        message += _("stolen_coins") + f" - <b>{self.__stolen_coins}%</b>\n\n"

        if self._has_details:
            if self.__number_of_transactions:
                message += _("aml_transactions") + f" {self.__number_of_transactions}\n"

            if self.__was_created:
                message += _("was_created") + f" {self.__was_created}\n"

        message += f"\n{self.__mode} " + _("mode") + ". " + _("checked") + f" {self.__checked_time}"

        return message
