"""Telegram bot — direct httpx Bot API long-polling FSM."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, cast

import httpx

from apple_caliber_scan import config
from apple_caliber_scan.database.connection import db_conn
from apple_caliber_scan.database.crud import (
    create_batch,
    delete_batch,
    get_batch,
    get_telegram_session,
    list_batches,
    list_reports_for_batch,
    list_scans_for_batch,
    list_varieties,
    upsert_telegram_session,
    upsert_variety,
)

logger = logging.getLogger(__name__)

POLLING_TIMEOUT = 30
API_BASE = "https://api.telegram.org/bot{token}"

# FSM states
STATES = {
    "idle",
    "awaiting_seller_name",
    "awaiting_seller_address",
    "awaiting_variety",
    "awaiting_price",
    "awaiting_ca_date",
    "awaiting_batch_id",
    "awaiting_notes",
    "awaiting_crates_count",
    "awaiting_drive_url",
    "awaiting_delete_confirmation",
}


class TelegramBot:
    def __init__(self, token: str) -> None:
        self.token = token
        self.base = f"https://api.telegram.org/bot{token}"
        self.client = httpx.Client(timeout=60.0)
        self.offset = 0

    def api(self, method: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base}/{method}"
        resp = self.client.post(url, json=kwargs)
        data: dict[str, Any] = resp.json()
        if not data.get("ok"):
            logger.warning("API error %s: %s", method, data.get("description"))
        return data

    def send(self, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
        params: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        if reply_markup:
            params["reply_markup"] = reply_markup
        self.api("sendMessage", **params)

    def get_updates(self) -> list[dict[str, Any]]:
        resp = self.api("getUpdates", offset=self.offset, timeout=POLLING_TIMEOUT)
        updates: list[dict[str, Any]] = cast(list, resp.get("result", []))
        if updates:
            self.offset = updates[-1]["update_id"] + 1
        return updates

    def get_state(self, chat_id: int) -> tuple[str, dict[str, Any]]:
        with db_conn() as conn:
            row = get_telegram_session(conn, chat_id)
        if row is None:
            return "idle", {}
        return row["state"], json.loads(row["context"])

    def set_state(self, chat_id: int, state: str, ctx: dict[str, Any]) -> None:
        with db_conn() as conn:
            upsert_telegram_session(conn, chat_id, state, ctx)

    def reset(self, chat_id: int) -> None:
        self.set_state(chat_id, "idle", {})

    def handle_update(self, update: dict[str, Any]) -> None:
        msg = update.get("message") or update.get("callback_query", {}).get("message")
        callback = update.get("callback_query")
        if not msg:
            return

        chat_id = msg["chat"]["id"]
        text = ""
        if callback:
            text = callback.get("data", "")
            # Answer callback query
            self.api("answerCallbackQuery", callback_query_id=callback["id"])
        else:
            text = msg.get("text", "")

        if not text:
            return

        state, ctx = self.get_state(chat_id)

        # Commands always handled first
        if text.startswith("/"):
            self.handle_command(chat_id, text, state, ctx)
        else:
            self.handle_state(chat_id, text, state, ctx)

    def handle_command(self, chat_id: int, text: str, state: str, ctx: dict[str, Any]) -> None:
        parts = text.strip().split(None, 1)
        cmd = parts[0].lower().split("@")[0]
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/start" or cmd == "/help":
            self.reset(chat_id)
            self.send(chat_id, (
                "🍎 <b>Apple Caliber Scan — Freshora Sp. Z. o. o.</b>\n\n"
                "Dostępne komendy:\n"
                "/newbatch — Utwórz nową partię\n"
                "/batches — Lista ostatnich 10 partii\n"
                "/attachscan &lt;id&gt; — Dołącz skan do partii\n"
                "/report &lt;id&gt; — Linki do raportów partii\n"
                "/web &lt;id&gt; — Link do panelu adnotacji\n"
                "/deletebatch &lt;id&gt; — Usuń partię i wszystkie dane\n"
                "/cancel — Anuluj bieżącą operację\n"
                "/help — Ta pomoc"
            ))

        elif cmd == "/newbatch":
            self.reset(chat_id)
            self.set_state(chat_id, "awaiting_seller_name", {})
            self.send(chat_id, "Podaj imię i nazwisko sprzedawcy:")

        elif cmd == "/cancel":
            self.reset(chat_id)
            self.send(chat_id, "Operacja anulowana.")

        elif cmd == "/batches":
            with db_conn() as conn:
                batches = list_batches(conn, limit=10)
            if not batches:
                self.send(chat_id, "Brak partii.")
                return
            lines = ["<b>Ostatnie partie:</b>"]
            for b in batches:
                lines.append(f"#{b['id']} — {b['seller_name']} — {b['variety']} — {b['status']}")
            self.send(chat_id, "\n".join(lines))

        elif cmd == "/attachscan":
            if not arg:
                self.send(chat_id, "Użycie: /attachscan &lt;batch_id&gt;")
                return
            try:
                bid = int(arg)
            except ValueError:
                self.send(chat_id, "Nieprawidłowe ID partii.")
                return
            self.set_state(chat_id, "awaiting_drive_url", {"batch_id": bid})
            self.send(chat_id, f"Partia #{bid}. Podaj link do pliku skanowania z Google Drive:")

        elif cmd == "/report":
            if not arg:
                self.send(chat_id, "Użycie: /report &lt;batch_id&gt;")
                return
            try:
                bid = int(arg)
            except ValueError:
                self.send(chat_id, "Nieprawidłowe ID partii.")
                return
            with db_conn() as conn:
                reports = list_reports_for_batch(conn, bid)
            if not reports:
                self.send(chat_id, f"Brak raportów dla partii #{bid}.")
                return
            base = config.PUBLIC_BASE_URL
            r = reports[0]
            links = []
            if r["html_path"]:
                links.append(f'<a href="{base}/reports/{r["id"]}.html">Raport HTML</a>')
            if r["pdf_path"]:
                links.append(f'<a href="{base}/reports/{r["id"]}.pdf">Raport PDF</a>')
            self.send(chat_id, f"Raporty partii #{bid}:\n" + "\n".join(links))

        elif cmd == "/web":
            if not arg:
                self.send(chat_id, "Użycie: /web &lt;batch_id&gt;")
                return
            base = config.PUBLIC_BASE_URL
            self.send(chat_id, f"Panel partii #{arg}:\n{base}/batches/{arg}")

        elif cmd == "/deletebatch":
            if not arg:
                self.send(chat_id, "Użycie: /deletebatch &lt;batch_id&gt;")
                return
            try:
                bid = int(arg)
            except ValueError:
                self.send(chat_id, "Nieprawidłowe ID partii.")
                return
            self.set_state(chat_id, "awaiting_delete_confirmation", {"batch_id": bid})
            self.send(
                chat_id,
                f"Czy na pewno chcesz usunąć partię #{bid} i wszystkie powiązane dane? "
                "Odpowiedz <b>TAK</b>.",
            )

        elif cmd == "/skip":
            self.handle_state(chat_id, "/skip", state, ctx)

        else:
            self.send(chat_id, "Nieznana komenda. Wpisz /help aby zobaczyć dostępne komendy.")

    def handle_state(self, chat_id: int, text: str, state: str, ctx: dict[str, Any]) -> None:
        skip = text.strip() == "/skip"

        if state == "idle":
            self.send(chat_id, "Wpisz /help aby zobaczyć dostępne komendy.")

        elif state == "awaiting_seller_name":
            ctx["seller_name"] = text.strip()
            self.set_state(chat_id, "awaiting_seller_address", ctx)
            self.send(chat_id, "Podaj adres sprzedawcy (lub /skip):")

        elif state == "awaiting_seller_address":
            ctx["seller_address"] = None if skip else text.strip()
            self.set_state(chat_id, "awaiting_variety", ctx)
            # Suggest varieties
            with db_conn() as conn:
                varieties = [row["name"] for row in list_varieties(conn, limit=10)]
            keyboard = {"inline_keyboard": [
                [{"text": v, "callback_data": f"variety:{v}"}] for v in varieties
            ] + [[{"text": "Inna odmiana...", "callback_data": "variety:__custom__"}]]}
            self.send(chat_id, "Wybierz odmianę lub wpisz nową:", reply_markup=keyboard)

        elif state == "awaiting_variety":
            if text.startswith("variety:"):
                chosen = text[len("variety:"):]
                if chosen == "__custom__":
                    self.send(chat_id, "Podaj odmianę jabłek:")
                    return
                ctx["variety"] = chosen
            else:
                ctx["variety"] = text.strip()
            with db_conn() as conn:
                upsert_variety(conn, ctx["variety"])
            self.set_state(chat_id, "awaiting_price", ctx)
            self.send(chat_id, "Podaj cenę w PLN/kg (lub /skip):")

        elif state == "awaiting_price":
            if not skip:
                try:
                    ctx["price_pln_per_kg"] = float(text.replace(",", "."))
                except ValueError:
                    self.send(chat_id, "Nieprawidłowa cena. Podaj liczbę (np. 1.85) lub /skip:")
                    return
            else:
                ctx["price_pln_per_kg"] = None
            self.set_state(chat_id, "awaiting_ca_date", ctx)
            self.send(chat_id, "Podaj datę otwarcia CA (RRRR-MM-DD lub /skip):")

        elif state == "awaiting_ca_date":
            ctx["ca_opening_date"] = None if skip else text.strip()
            self.set_state(chat_id, "awaiting_batch_id", ctx)
            self.send(chat_id, "Podaj numer partii/referencję:")

        elif state == "awaiting_batch_id":
            ctx["operator_batch_id"] = text.strip()
            self.set_state(chat_id, "awaiting_notes", ctx)
            self.send(chat_id, "Podaj uwagi (lub /skip):")

        elif state == "awaiting_notes":
            ctx["notes"] = None if skip else text.strip()
            self.set_state(chat_id, "awaiting_crates_count", ctx)
            self.send(chat_id, "Podaj liczbę skrzynek (domyślnie 1):")

        elif state == "awaiting_crates_count":
            try:
                crates = int(text.strip()) if not skip else 1
            except ValueError:
                crates = 1
            ctx["number_of_crates"] = crates
            ctx["total_weight_kg"] = crates * config.DEFAULT_CRATE_WEIGHT_KG
            self._create_batch_from_ctx(chat_id, ctx)

        elif state == "awaiting_drive_url":
            bid = ctx.get("batch_id")
            if not bid:
                self.send(chat_id, "Błąd: brak ID partii.")
                self.reset(chat_id)
                return
            url = text.strip()
            from apple_caliber_scan.storage.drive import extract_drive_file_id

            file_id = extract_drive_file_id(url)
            if not file_id:
                self.send(chat_id, "Nieprawidłowy link Google Drive. Spróbuj ponownie:")
                return
            self.send(
                chat_id,
                f"Link zapisany dla partii #{bid}. "
                f"Przejdź do panelu, aby przetworzyć skan:\n"
                f"{config.PUBLIC_BASE_URL}/batches/{bid}/scan/new\n\n"
                f"(Automatyczne pobieranie przez bota w przyszłej wersji.)"
            )
            self.reset(chat_id)

        elif state == "awaiting_delete_confirmation":
            bid_raw = ctx.get("batch_id")
            if bid_raw is None:
                self.send(chat_id, "Brak identyfikatora partii w kontekście.")
                self.reset(chat_id)
                return
            bid = int(bid_raw)
            if text.strip().upper() == "TAK":
                with db_conn() as conn:
                    batch = get_batch(conn, bid)
                    if batch:
                        scans = list_scans_for_batch(conn, bid)
                        reports = list_reports_for_batch(conn, bid)
                        from pathlib import Path

                        for scan in scans:
                            if scan["preview_path"]:
                                preview = (
                                    config.DATA_DIR / "previews"
                                    / Path(scan["preview_path"]).name
                                )
                                preview.unlink(missing_ok=True)
                        for r in reports:
                            for f in ("html_path", "pdf_path", "json_path"):
                                if r[f]:
                                    Path(r[f]).unlink(missing_ok=True)
                        delete_batch(conn, bid)
                        self.send(
                            chat_id,
                            f"Partia #{bid} i wszystkie powiązane dane zostały usunięte.",
                        )
                    else:
                        self.send(chat_id, f"Partia #{bid} nie istnieje.")
            else:
                self.send(chat_id, "Usuwanie anulowane.")
            self.reset(chat_id)

        else:
            self.send(chat_id, "Nieoczekiwany stan. Wpisz /cancel aby zresetować.")

    def _create_batch_from_ctx(self, chat_id: int, ctx: dict[str, Any]) -> None:
        with db_conn() as conn:
            bid = create_batch(
                conn,
                seller_name=ctx.get("seller_name", "?"),
                variety=ctx.get("variety", "?"),
                seller_address=ctx.get("seller_address"),
                price_pln_per_kg=ctx.get("price_pln_per_kg"),
                ca_opening_date=ctx.get("ca_opening_date"),
                operator_batch_id=ctx.get("operator_batch_id"),
                notes=ctx.get("notes"),
                number_of_crates=ctx.get("number_of_crates", 1),
                total_weight_kg=ctx.get("total_weight_kg", config.DEFAULT_CRATE_WEIGHT_KG),
                telegram_chat_id=chat_id,
            )
        self.reset(chat_id)
        self.send(
            chat_id,
            f"✅ Partia #{bid} utworzona pomyślnie.\n"
            f"Użyj /attachscan {bid} aby dołączyć skan.\n"
            f"Panel: {config.PUBLIC_BASE_URL}/batches/{bid}",
        )

    def run(self) -> None:
        logger.info("Telegram bot polling started.")
        while True:
            try:
                updates = self.get_updates()
                for update in updates:
                    try:
                        self.handle_update(update)
                    except Exception as e:
                        logger.error("Error handling update %s: %s", update.get("update_id"), e)
            except httpx.RequestError as e:
                logger.warning("Network error during polling: %s — retrying in 5s", e)
                time.sleep(5)
            except KeyboardInterrupt:
                logger.info("Bot stopped by operator.")
                break
            except Exception as e:
                logger.error("Unexpected error in polling loop: %s — retrying in 10s", e)
                time.sleep(10)


def run_bot() -> None:
    token = config.TELEGRAM_TOKEN
    if not token:
        logger.warning(
            "ACS_TELEGRAM_TOKEN not set — Telegram bot disabled. "
            "Set the token and restart to enable."
        )
        return

    config.ensure_data_dirs()
    from apple_caliber_scan.database.connection import initialize_schema

    initialize_schema()
    bot = TelegramBot(token)
    bot.run()
