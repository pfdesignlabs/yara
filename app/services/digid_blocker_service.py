from __future__ import annotations


class DigiDBlockerService:
    def build_reply(
        self,
        *,
        language: str,
        situation_summary: str | None,
        user_message: str | None,
        digid_prerequisite_facts: dict | None = None,
    ) -> str | None:
        summary = (situation_summary or "").lower()
        message = (user_message or "").lower()
        combined = f"{summary} {message}"
        facts = digid_prerequisite_facts or {}

        has_no_bsn = facts.get("has_bsn") is False or "geen bsn" in combined or "no bsn" in combined
        has_no_fixed_address = facts.get("has_fixed_address") is False or "geen vast adres" in combined or "no fixed address" in combined
        has_no_mailing_address = facts.get("has_mailing_address") is False or "geen briefadres" in combined or "no mailing address" in combined
        wants_digid = "digid" in combined

        if wants_digid and has_no_bsn and has_no_fixed_address and has_no_mailing_address:
            if language == "uk":
                return (
                    "Зараз головне не сама заявка на DigiD, а спочатку реєстрація та адреса для пошти. "
                    "Без BSN і без адреси або briefadres подати заявку на DigiD ще не вийде. "
                    "Найкращий перший крок зараз — звернутися до gemeente Den Haag, щоб дізнатися, як у вашій ситуації оформити реєстрацію або briefadres. "
                    "Якщо хочеш, я можу зараз коротко пояснити, що саме запитати в gemeente."
                )
            if language == "en":
                return (
                    "The first step right now is not the DigiD application itself, but your registration and a mailing address. "
                    "Without a BSN and without an address or mailing address, you cannot apply for DigiD yet. "
                    "The best next step is to contact the Municipality of The Hague to ask how you can arrange registration or a mailing address in your situation. "
                    "If you want, I can help you with what to ask them."
                )
            return (
                "De eerste stap is nu nog niet de DigiD-aanvraag zelf, maar eerst je registratie en een adres voor post. "
                "Zonder BSN en zonder adres of briefadres kun je DigiD nog niet aanvragen. "
                "De beste volgende stap is om contact op te nemen met de gemeente Den Haag om te vragen hoe je in jouw situatie registratie of een briefadres kunt regelen. "
                "Als je wilt, kan ik je helpen met wat je precies aan de gemeente kunt vragen."
            )

        return None
