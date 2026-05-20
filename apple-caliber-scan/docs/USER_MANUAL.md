# Podręcznik użytkownika — Apple Caliber Scan

**Freshora Sp. Z. o. o.**

---

## 1. Jak wykonać skanowanie (Scaniverse + iPhone + pierścień pomiarowy)

### Przygotowanie sprzętu
- iPhone z czujnikiem LiDAR (iPhone 12 Pro lub nowszy)
- Aplikacja **Scaniverse** (bezpłatna, dostępna w App Store)
- Pierścień pomiarowy 75 mm (lub inny rozmiar — pamiętaj, aby podać właściwy rozmiar w systemie)

### Procedura skanowania
1. Połóż pierścień pomiarowy obok reprezentatywnego jabłka w górnej warstwie skrzyni.
2. Otwórz aplikację **Scaniverse** → stuknij **Nowe skanowanie**.
3. Wybierz tryb **Obiekt** lub **Pomieszczenie**.
4. Trzymaj iPhone bezpośrednio nad skrzynią, skierowany w dół.
5. Przemieszczaj się powoli nad całą powierzchnią górnej warstwy.
6. Poczekaj na przetworzenie skanu w telefonie.
7. Wyeksportuj plik: **Eksportuj → PLY** (zalecany) lub **OBJ**.

---

## 2. Jak wgrać plik na Google Drive i udostępnić go

1. Otwórz **Google Drive** na telefonie lub komputerze.
2. Prześlij wyeksportowany plik PLY/OBJ do dowolnego folderu.
3. Kliknij prawym przyciskiem na pliku → **Udostępnij → Zmień na „Każdy z linkiem"**.
4. Skopiuj link do schowka.

---

## 3. Jak utworzyć nową partię w Telegramie

1. Otwórz czat z botem Freshora.
2. Wpisz `/newbatch` i naciśnij wyślij.
3. Bot zada serię pytań — odpowiedz kolejno:
   - Imię i nazwisko sprzedawcy
   - Adres (lub `/skip`, aby pominąć)
   - Odmiana jabłek (wybierz z listy lub wpisz nową)
   - Cena w PLN/kg (lub `/skip`)
   - Data otwarcia CA (lub `/skip`)
   - Numer partii
   - Uwagi (lub `/skip`)
   - Liczba skrzynek
4. Bot potwierdzi utworzenie partii i poda jej numer.

---

## 4. Jak dołączyć skan przez link Google Drive

### Przez Telegram
1. Wpisz: `/attachscan <numer_partii>` (np. `/attachscan 5`)
2. Wklej skopiowany link Google Drive i wyślij.

### Przez panel webowy
1. Zaloguj się pod adresem `http://localhost:8000`.
2. Wybierz partię z listy.
3. Kliknij **Dołącz skan (Google Drive)**.
4. Wklej link i kliknij **Pobierz i przetwórz skan**.

---

## 5. Jak przejść do panelu przeglądu i wykonać adnotację

1. Po przetworzeniu skanu kliknij **Przeglądaj** przy danym skanie.
2. Na ekranie pojawi się podgląd skanu z zaznaczonymi okręgami.
3. Znajdź okrąg odpowiadający pierścieniu pomiarowemu.
4. Kliknij na ten okrąg → wybierz **Pierścień kalibracyjny**.
5. Panel po prawej stronie pokaże obliczony współczynnik skali i rozkład kalibrażu.
6. Możesz kliknąć inne okręgi, aby oznaczyć je jako **Jabłko** lub **Wyklucz**.
7. Gdy adnotacja jest gotowa, kliknij **Zapisz adnotację i generuj raport**.

---

## 6. Jak wygenerować i pobrać raport

1. Po adnotacji system automatycznie generuje raport.
2. Wróć do szczegółów partii.
3. W sekcji **Raporty** kliknij **HTML** (do przeglądu w przeglądarce) lub **PDF** (do wydruku).

---

## 7. Jak usunąć partię

### Przez panel webowy
1. Wejdź w szczegóły partii.
2. Kliknij **Usuń partię** i potwierdź.

### Przez Telegram
1. Wpisz: `/deletebatch <numer_partii>`
2. Odpowiedz **TAK** na pytanie potwierdzające.

> **Uwaga:** Usunięcie partii jest nieodwracalne. Usuwa wszystkie dane — skany, podglądy i raporty.
