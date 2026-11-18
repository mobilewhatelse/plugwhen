# Changelog

## Unreleased (0.10.1)

- **Charts full width:** tap a chart on the dashboard and it opens on a page of its own in the dashboard, over the whole width, with its caption; held sideways it is large. The app is not loaded again, the back arrow leads back. **Create the dashboard again** to get it. Also: right after a restart a dashboard card no longer writes a template error to the log while its sensor is not back yet. *Deutsch:* Grafiken über die ganze Breite: Ein Tipp auf eine Grafik im Dashboard öffnet sie auf einer eigenen Seite im Dashboard, über die ganze Breite und mit ihrer Beschriftung; quer gehalten wird sie groß. Die App lädt dabei nicht neu, der Zurück-Pfeil führt zurück. **Dashboard neu erstellen**, damit es kommt. Außerdem: Direkt nach einem Neustart schreibt eine Dashboard-Karte keinen Template-Fehler mehr ins Protokoll, solange ihr Sensor noch nicht wieder da ist.
- **Charge the evening before: only for a later trip of the same day (week replay):** a test over a whole week with a real setup (every 15 minutes, learned and calendar trips, weekly full charge, charging for three days) found two faults. The charge before the first trip rolled on night after night and filled the battery to 95-100 % for trips two days later, past the everyday limit, with a deadline after the car had already left. And a first trip that needed a little itself (0.2 kWh) hid the evening trip, so a car not plugged in between left in the evening with 40 % instead of 62 %. Now only the later trips of the same day count, all of them, never more than the battery takes, done by the first departure. The week test stays in the test chain. *Deutsch:* Laden am Vorabend nur für eine spätere Fahrt am selben Tag (Wochen-Testlauf): Ein Test über eine ganze Woche mit einer echten Einrichtung (alle 15 Minuten, gelernte und Kalenderfahrten, wöchentliches Volladen, Laden für drei Tage) fand zwei Fehler. Das Laden vor der ersten Fahrt rollte Nacht für Nacht weiter und füllte den Akku für Fahrten zwei Tage später auf 95-100 %, über die Alltagsgrenze, mit einer Frist nach der Abfahrt. Und eine erste Fahrt, die selbst ein wenig brauchte (0,2 kWh), verdeckte die Abendfahrt: Ein Auto, das dazwischen nicht angesteckt war, fuhr am Abend mit 40 % statt 62 % los. Jetzt zählen nur die späteren Fahrten desselben Tages, alle, nie mehr als der Akku aufnimmt, fertig bis zur ersten Abfahrt. Der Wochentest bleibt in der Testkette.
- **Weekly full charge for the first departure only:** the full target counted for every departure up to the one it was kept for; with a trip in the morning and another in the evening the look-ahead wanted the battery full again after the morning trip ("charging needed tomorrow, 11 kWh"). Now only the first departure it counts for gets the full target. *Deutsch:* Wöchentliches Volladen nur für die erste Abfahrt: Das volle Ziel galt für jede Abfahrt bis zur vorgemerkten; bei einer Fahrt am Morgen und einer am Abend wollte die Vorausschau den Akku nach der Morgenfahrt wieder voll („Morgen wird Laden nötig, 11 kWh“). Jetzt bekommt nur die erste Abfahrt, für die es gilt, das volle Ziel.
- **Safety check and "next trip" wallboxes:** a wallbox that already charges as fast as it is allowed to (in its grid or next-trip mode) is left alone and no message is sent; for a wallbox that was given the departure and the energy the check waits longer before it takes over (it starts late on purpose) and a plan window without charging is no alarm. The plan card says that the windows are a proposal there. *Deutsch:* Sicherheitsprüfung und Wallboxen mit „Next Trip“: Lädt die Wallbox schon so schnell, wie sie darf (Netz- oder Next-Trip-Modus), bleibt sie unberührt und es kommt keine Meldung; bei einer Wallbox, die Abfahrtszeit und Energie bekommen hat, wartet die Prüfung länger, bevor sie übernimmt (sie startet absichtlich spät), und ein Plan-Fenster ohne Laden ist kein Alarm. Die Plan-Karte sagt dort, dass die Fenster ein Vorschlag sind.
- **The first departure counts, all night:** a calendar trip in the evening no longer replaces the learned departure in the morning of the same day (only a trip within two hours of it is the same trip). The charge before the first trip now holds through the whole night - it was dropped at midnight and the deadline jumped back two hours before the departure. Mode evcc gets the same deadline, a charge that does not fit is cut to what fits instead of "cannot be reached", and ticking a weekday opens a done week only when the day was off. *Deutsch:* Die erste Abfahrt zählt, die ganze Nacht: Eine Kalenderfahrt am Abend ersetzt die gelernte Abfahrt am Morgen desselben Tages nicht mehr (nur eine Fahrt innerhalb von zwei Stunden ist dieselbe Fahrt). Das Laden vor der ersten Fahrt hält jetzt die ganze Nacht – bisher fiel es um Mitternacht weg, und zwei Stunden vor der Abfahrt sprang die Frist zurück. Die Betriebsart evcc bekommt dieselbe Frist, eine Ladung, die nicht passt, wird auf das Machbare gekürzt statt „nicht erreichbar“, und ein Wochentag öffnet eine erledigte Woche nur, wenn er vorher aus war.
- **Charged the evening before:** if the car leaves tomorrow, comes back and leaves again, the energy for the later trip is charged in the standing time before the first one, not "at the latest" the next afternoon. The limit for several days never cuts this need; the tip says "Charging beforehand" and no "charging needed tomorrow" message is sent. *Deutsch:* Am Vorabend geladen: Fährt das Auto morgen weg, kommt zurück und fährt noch einmal, wird die Energie für die spätere Fahrt in der Standzeit vor der ersten geladen, nicht „spätestens“ am nächsten Nachmittag. Die Grenze für mehrere Tage kappt diesen Bedarf nie; der Tipp sagt „Wird schon vorher geladen“, eine Meldung „Morgen laden nötig“ entfällt.
- **Weekly full charge can be opened again:** ticking a weekday (or switching the main switch on) opens a week that was marked done, for "once more this week". *Deutsch:* Wöchentliches Volladen lässt sich wieder öffnen: Ein Wochentag (oder der Hauptschalter) von aus auf an öffnet eine als erledigt markierte Woche für „noch einmal diese Woche“.
- **Latest messages on the dashboard:** the overview lists the latest messages sent to the phone (date, time, text), so a message
  swiped away there can still be read. *Deutsch:* Letzte Hinweise im Dashboard: Die Übersicht zeigt die letzten Meldungen ans Handy (Datum, Uhrzeit, Text); eine dort weggeklickte Meldung bleibt so lesbar.
- **Settings as full-width tiles:** on a phone the names in the settings list were cut off; each setting is now a tile with the
  name on its own line, shorter names, the days without the unit "d". "Would switch" only appears while the trial run is on
  ("off" only puzzled). *Deutsch:* Einstellungen als Kacheln über die ganze Breite: Am Handy waren die Namen abgeschnitten; jede Einstellung ist jetzt eine Kachel mit eigener Namenszeile, kürzere Namen, die Tage ohne Einheit „d“. „Würde schalten“ erscheint nur noch bei laufendem Probelauf („aus“ verwirrte nur).
- **Charging for several days on the dashboard:** "Charge for this many days at once" and the limit (%) are now in the settings
  card of each car. They change the same value as the car's settings form, take effect at once and do not reload the integration.
  *Deutsch:* Laden für mehrere Tage im Dashboard: „Für so viele Tage auf einmal laden“ und die Grenze (%) stehen jetzt in der Einstellungen-Karte jedes Autos. Sie ändern denselben Wert wie das Einstellungsformular des Autos, wirken sofort und laden die Integration nicht neu. Danach: Dashboard neu erstellen.
- **Charging plan readable on a phone:** an orange line marks the current time ("now 19:52"), the chart is narrower with larger
  type, each window shows from when to when and how many kWh, and midnight is "0" with the new day written below it (a bare "Wed"
  was read as "charging on Wednesday"). A narrow window at the right edge gets its start time and kWh.
  *Deutsch:* Ladeplan am Handy lesbar: Ein orangener Strich zeigt die aktuelle Uhrzeit („jetzt 19:52“), die Grafik ist schmaler mit größerer Schrift, jedes Fenster zeigt von wann bis wann und wie viele kWh, Mitternacht ist „0“ mit dem neuen Tag darunter (ein bloßes „Mi“ wurde als „am Mittwoch laden“ gelesen). Ein schmales Fenster am rechten Rand bekommt Startzeit und kWh.
- **No lone quarter hour any more:** a grid piece of at most half an hour next to other windows is folded into them (each takes a
  little more power), if the highest grid import rises by at most 0.5 kW and stays below the peak target. Found in the field:
  12.4 + 7.3 + 1.0 kWh at 06:45 became 13.1 + 7.6 kWh. Sun windows are never moved.
  *Deutsch:* Keine einzelne Viertelstunde mehr: Ein Netz-Stück von höchstens einer halben Stunde neben anderen Fenstern wird auf diese verteilt (jedes etwas mehr Leistung), wenn der höchste Netzbezug um höchstens 0,5 kW steigt und unter dem Spitzenziel bleibt. Gefunden im Praxistest: aus 12,4 + 7,3 + 1,0 kWh um 06:45 wurden 13,1 + 7,6 kWh. Sonnenfenster werden nie verschoben.
- **Goes well with: Viertelstunden-Wächter:** without the peak guard installed the overview ends with a short tile and a link.
  After installing it: create the dashboard again. *Deutsch:* Passt dazu: Viertelstunden-Wächter: Ohne Wächter endet die Übersicht mit einer kurzen Kachel und Link. Nach der Installation: Dashboard neu erstellen.

## 0.10.0 - 2026-11-17 - the reserve stays after the trip, charging for several days

- **Safety check: fewer messages (found in the field test):** after a message about "charge now" there is no further one for three
  hours, whatever the reason (it had sent seven in 18 minutes while settings were tried out). The wallbox is still switched.
  *Deutsch:* Sicherheitsprüfung: weniger Meldungen (gefunden im Praxistest): Nach einer Meldung zu „Jetzt laden“ kommt drei Stunden lang keine weitere, egal aus welchem Grund (es waren sieben in 18 Minuten, während Einstellungen ausprobiert wurden). Die Wallbox wird weiter umgeschaltet.
- **Full charge: the card shows the range of the full target** instead of the reserve range ("100 % (100 km)"). *Deutsch:* Volladen: Die Karte zeigt die Reichweite des vollen Ziels statt der Reserve („100 % (100 km)“).
- **The reserve is left after the trip (new default, selectable per car).** Until now the reserve was the least range at the
  departure and already contained the trip: with 100 km reserve and a 46 km day the car left with 100 km and came home with 54.
  Now it is charged for the trip plus the reserve. *Least range at the departure* (as before) can be chosen in the car's settings.
  **This changes the targets of existing cars: they get higher.**
- **Charging for several days at once.** Charging starts when the battery is below what the next trip needs and then fills for
  the trips of the next days (default 3, 1 = every day on its own) up to an everyday limit (default 80 %). Replayed with 255 real
  days of one car: 3.2 charges a week of 26 kWh instead of 5.6 of 13 kWh, a third of them below 8 kWh. The warning, the promise
  and the safety check only look at the next trip, so nobody is told to plug in every day.
- **With a solar plant the sun comes first:** what the forecast promises while the car stands at home between the coming trips
  and is usually plugged in (learned from the recorded plug-in times) is left to the sun, only the rest is taken from the grid.
  Without a forecast nothing is left out. Solar power that comes while the car is plugged in is always used, plan or not.
  In a plan with sun the grid part now lies behind the sun hours whenever it fits there without a higher power: the battery
  keeps room for a sun that turns out stronger than forecast (before, a quiet morning could be charged from the grid first).
- **Without a peak guard and without a demand charge the plan charges compactly and at once** (at least three quarters of
  the wallbox power, from the moment the car is plugged in; smaller amounts at the car's preferred power) instead of flat at
  4 kW shortly before the departure: where peaks cost nothing, flat charging gains nothing and loses a little in the car's
  charger, and a car that charges slower than set has the whole parking time. With a guard, a load forecast or a demand
  charge nothing changes. Capping peaks stays the guard's job.
- **Several cars:** a charge for several days of one car never takes the time (a shared wallbox) or the room below the peak
  limit that another car needs for its next trip; then nobody charges ahead.
- **Evening reminder to plug in (found in the field test):** a warning sent during the day (for example "not reachable" at
  noon for a trip at 22:00) was the last word; in the evening the car was still not plugged in and nothing came. Now a car
  known not to be plugged in gets one reminder from the evening hour on. "Not reachable" and "too late" also ask to plug
  in all the same when the car is not plugged in, and the title says today, tomorrow or the weekday.
- **Once a week full, two fixes from the field test:** a full charge kept for a departure that then went away (a calendar trip
  deleted) blocked the full charge for the next one, now the day is chosen again; and a trip from the calendar got the full
  target only in the plan, not in the look-ahead (it then told to charge again the day after).
- **Once a week full on the dashboard:** while the switch is off only the switch is shown; the target, the days and the status
  appear when it is switched on (the ticked days are kept).
- Create the dashboard again: the status line shows the target of the next trip and, while it runs, what a charge ahead fills to.
  *Deutsch:* **Die Reserve bleibt nach der Fahrt übrig (neuer Standard, je Auto wählbar).** Bisher war die Reserve die
  Mindestreichweite bei der Abfahrt, die Fahrt war darin schon enthalten: mit 100 km Reserve und einem Tag mit 46 km fuhr das Auto
  mit 100 km los und kam mit 54 km heim. Jetzt wird für die Fahrt plus die Reserve geladen. *Mindestreichweite bei der Abfahrt*
  (wie bisher) ist in den Einstellungen des Autos wählbar. **Das ändert die Ziele bestehender Autos: sie werden höher.**
  **Für mehrere Tage auf einmal laden.** Geladen wird, wenn der Akku unter dem Bedarf der nächsten Fahrt liegt, dann gleich für
  die Fahrten der nächsten Tage (Standard 3, 1 = jeder Tag für sich) bis zu einer Obergrenze im Alltag (Standard 80 %). Mit 255
  echten Tagen eines Autos nachgerechnet: 3,2 Ladungen pro Woche mit 26 kWh statt 5,6 mit 13 kWh, davon ein Drittel unter 8 kWh.
  Warnung, Zusage und Sicherheitsprüfung gelten nur der nächsten Fahrt, niemand wird täglich zum Anstecken ermahnt.
  **Mit Solaranlage kommt zuerst die Sonne:** Was die Prognose für die Zeit verspricht, in der das Auto zwischen den nächsten
  Fahrten zu Hause steht und üblicherweise angesteckt ist (gelernt aus den Steckzeiten), bleibt der Sonne überlassen, nur der
  Rest kommt aus dem Netz. Ohne Prognose wird nichts ausgelassen. Sonnenstrom, der kommt, während das Auto angesteckt ist,
  wird immer genutzt, mit oder ohne Plan. In einem Plan mit Sonne liegt der Netzanteil jetzt hinter den Sonnenstunden, wenn er
  dort ohne höhere Leistung Platz hat: Der Akku behält Platz für eine Sonne, die stärker ausfällt als die Prognose (bisher
  konnte zuerst ein ruhiger Vormittag aus dem Netz geladen werden).
  **Ohne Spitzenwächter und ohne Leistungspreis lädt der Plan kompakt und sofort** (mindestens drei Viertel der
  Wallbox-Leistung, ab dem Anstecken; kleine Mengen mit der bevorzugten Leistung des Autos) statt flach mit 4 kW kurz vor der
  Abfahrt: Wo Spitzen nichts kosten, bringt flaches Laden nichts und verliert etwas im Ladegerät des Autos, und ein Auto, das
  langsamer lädt als eingestellt, hat die ganze Standzeit. Mit Wächter, Lastprognose oder Leistungspreis ändert sich nichts.
  Das Kappen von Spitzen bleibt Aufgabe des Wächters.
  **Mehrere Autos:** Die Ladung für mehrere Tage eines Autos nimmt einem anderen Auto nie die Zeit (gemeinsame Wallbox) oder
  den Platz unter der Spitzengrenze für dessen nächste Fahrt; dann lädt niemand im Voraus.
  **Erinnerung am Abend (gefunden im Praxistest):** Eine Warnung am Tag (etwa „nicht erreichbar“ zu Mittag für eine Fahrt
  um 22:00) war das letzte Wort; am Abend war das Auto noch nicht angesteckt, und es kam nichts mehr. Jetzt bekommt ein Auto,
  das sicher nicht angesteckt ist, ab der Abendstunde einmal eine Erinnerung. „Nicht erreichbar“ und „zu spät“ bitten bei
  nicht angestecktem Auto trotzdem ums Anstecken, und die Überschrift sagt heute, morgen oder den Wochentag.
  **Einmal pro Woche voll, zwei Korrekturen aus dem Praxistest:** Ein für eine Abfahrt gemerktes Volladen, deren Fahrt dann
  wegfiel (Kalendertermin gelöscht), verhinderte das Volladen für die nächste; jetzt wird der Tag neu gewählt. Und eine Fahrt aus
  dem Kalender bekam das volle Ziel nur im Plan, nicht in der Vorausschau (die meldete dann für den Tag danach erneut Laden).
  **Einmal pro Woche voll im Dashboard:** Solange der Schalter aus ist, steht nur der Schalter da; Ziel, Tage und Status erscheinen
  beim Einschalten (die angehakten Tage bleiben gemerkt).
  Dashboard neu erstellen: Die Statuszeile zeigt das Ziel der nächsten Fahrt und, solange es läuft, bis wohin im Voraus geladen wird.

## 0.9.2 - 2026-11-17 - once a week full

- **evcc: own connection, own password (HACS review):** Plugwhen talks to evcc on a client session of its own (one per
  installation), so evcc's login cookie never reaches Home Assistant's shared session. The evcc address may still come from the
  quarter-hour peak guard, its password never: an evcc with a password needs it in Plugwhen's own settings. *Deutsch:* evcc mit
  eigener Verbindung und eigenem Passwort (HACS-Prüfung): Plugwhen spricht mit evcc über eine eigene Sitzung, das Anmelde-Cookie von
  evcc landet nie in der gemeinsamen Sitzung von Home Assistant. Die Adresse darf weiter aus dem Wächter kommen, das Passwort nie:
  ein evcc mit Passwort braucht es in den Einstellungen von Plugwhen.
  A wrong evcc password is now refused when saving (evcc reads without a login, so before it never showed), and leaving the mode
  *via evcc* removes the plan Plugwhen wrote into evcc (a plan you changed in evcc stays). *Deutsch:* Ein falsches evcc-Passwort
  wird beim Speichern abgelehnt (evcc liest auch ohne Anmeldung, vorher fiel es nie auf), und wer *Über evcc* verlässt, dem nimmt
  Plugwhen seinen in evcc geschriebenen Plan wieder heraus (ein in evcc geänderter Plan bleibt).
- **Safety check before every departure (wish of a user after the field test):** from three hours before every departure, every
  day, Plugwhen compares what it promised for this departure with reality. If the target it planned fell below the promise, the
  wallbox does not charge although the plan says so, or the time left is getting short, it switches the wallbox to "charge now"
  (the wallbox's grid mode, its start button, or evcc "now") and sends a message with the reason (to the car's notify services and
  into Home Assistant's notifications; only when it acts, once per departure and reason). A message alone in the night would
  not be read. "Charge now" ends at the target, at the departure or when the car is unplugged, then everything is given back. In
  the modes *off* and *learn* Plugwhen does not touch the wallbox; there the warning "car will not be ready" tells as before.
  *Deutsch:* Sicherheitsprüfung vor jeder Abfahrt (Wunsch eines Nutzers nach dem Praxistest): ab drei Stunden vor jeder Abfahrt,
  jeden Tag, vergleicht Plugwhen, was es für diese Abfahrt zugesagt hat, mit der Wirklichkeit. Ist das geplante Ziel unter die Zusage
  gefallen, lädt die Wallbox nicht, obwohl sie laut Plan laden sollte, oder wird die Zeit knapp, schaltet es die Wallbox auf
  „Jetzt laden“ (Netzmodus der Wallbox, Start-Taste oder evcc „Sofort“) und schickt eine Nachricht mit dem Grund (an die
  Benachrichtigungsdienste des Autos und unter *Benachrichtigungen* in Home Assistant; nur wenn es eingreift, je Abfahrt und Grund
  einmal). Eine Nachricht
  allein würde in der Nacht niemand lesen. „Jetzt laden“ endet beim Ziel, bei der Abfahrt oder wenn das Auto abgesteckt wird,
  danach wird alles zurückgegeben. In den Betriebsarten *aus* und *lernen* fasst Plugwhen die Wallbox nicht an; dort meldet wie bisher
  die Warnung „Auto wird nicht bereit sein“.

- **Fixes from a code review of the safety check and the wallbox control (before the release):**
  no false alarm "target fell" when the weekly full charge is done at 99 %; a wallbox that is not reachable for a while (Wi-Fi
  restart at night) is left alone, nothing is forgotten and nothing counts as written, and it no longer looks like "does not
  charge"; evcc's mode is reliably given back after "charge now"; a calendar trip that was deleted or moved takes its promise
  with it; a mode you set on the wallbox by hand stays until the next departure (before: only a few minutes); the message is
  sent after switching and says so if the wallbox could not be switched; unticking the day ends a full charge already planned.
  *Deutsch:* Korrekturen aus einer Code-Durchsicht der Sicherheitsprüfung und der Wallbox-Steuerung (vor der Veröffentlichung):
  kein Fehlalarm „Ziel gefallen“, wenn das Volladen bei 99 % erledigt ist; eine kurz nicht erreichbare Wallbox (WLAN-Neustart in
  der Nacht) wird in Ruhe gelassen, nichts wird vergessen oder als geschrieben gemerkt, und sie gilt nicht mehr als „lädt nicht“;
  der Modus von evcc wird nach „Jetzt laden“ sicher zurückgegeben; ein gelöschter oder verschobener Kalendertermin nimmt seine
  Zusage mit; ein von Hand gesetzter Modus der Wallbox bleibt bis zur nächsten Abfahrt (vorher nur wenige Minuten); die Nachricht
  kommt nach dem Umschalten und sagt es, wenn die Wallbox nicht umgeschaltet werden konnte; einen Tag abwählen beendet ein schon
  geplantes Volladen.

- **Once a week full (wish of a user):** per car a switch *Once a week full* (default off), the days as a bar Mo to Su to
  tap (one switch per weekday, default Saturday and Sunday) and the target (default 100 %). With a solar forecast the sunniest allowed day still ahead this week is chosen, without solar
  the first one. Sun first, the rest from the grid, so the car really gets full; full shortly before the departure (without one
  by 8 pm). A full charge planned for a departure stays until that departure, also when the car charges after midnight of the
  chosen day (found in the field test: Sunday evening plugged in, Monday morning only the normal target). Once per week, then
  the normal target again. Create the dashboard again to see the settings in the card *Settings*.
  *Deutsch:* Einmal pro Woche voll laden (Wunsch eines Nutzers): je Auto Schalter *Einmal pro Woche voll laden* (Standard aus), die Tage
  als Leiste Mo bis So zum Antippen (ein Schalter je Wochentag, Standard Samstag und Sonntag) und Ziel (Standard 100 %). Mit Solarprognose der sonnigste erlaubte Tag dieser Woche, ohne
  Photovoltaik der erste. Zuerst Sonne, der Rest aus dem Netz, damit das Auto sicher voll wird; voll kurz vor der Abfahrt (ohne Abfahrt
  bis 20 Uhr). Ein für eine Abfahrt geplantes Volladen bleibt bis zu dieser Abfahrt, auch wenn das Auto nach Mitternacht des
  gewählten Tages lädt (gefunden im Praxistest: Sonntagabend angesteckt, Montag früh nur das normale Ziel). Einmal je Woche,
  danach wieder das normale Ziel. Dashboard neu erstellen, damit die Einstellungen in der Karte
  *Einstellungen* erscheinen.

- **Mode *direct* with a next-trip wallbox (e.g. Wattpilot): no more stops while charging (found in the field test):** Plugwhen wrote
  the remaining energy again whenever it fell during charging, and the wallbox stopped every time to plan again (ten stops in
  80 minutes). Now the energy is written again only if the need really changes (new departure, weekly full charge, the car was
  driven), not because the car is charging.
  *Deutsch:* Betriebsart *direkt* mit einer Wallbox mit „Nächste Fahrt“ (z. B. Wattpilot): keine Ladepausen mehr (gefunden im
  Praxistest): Plugwhen schrieb die Restenergie jedes Mal neu, wenn sie beim Laden sank, und die Wallbox stoppte jedes Mal, um neu
  zu planen (zehn Pausen in 80 Minuten). Jetzt wird die Energie nur neu geschrieben, wenn sich der Bedarf wirklich ändert (neue
  Abfahrt, Volladen, das Auto ist gefahren), nicht weil das Auto lädt.

## 0.9.1 - 15.11.2026 - fixes before the Marketplace, bug report on request

- **Bug report on request:** new button *Send bug report* next to the feedback (text optional). One press sends it, and the
  notification then shows exactly what was sent. It holds what is needed to find an error: version, per car the mode, state of
  charge and its age, plugged in, charging, target and need, departure only as a distance in hours, the next windows of the plan,
  the decision, the last ten actions on the wallbox, per wallbox setting its integration, model and firmware, the value now and its
  list, how fast and how often commands arrived or failed, whether the sensors deliver values, and the last 20 warnings of
  Plugwhen. Names, entity ids, addresses, IP addresses and identifiers are removed first, no clock times. Independent of *Share
  anonymous data*. Create the dashboard again to see the button in the card *Feedback*.
  *Deutsch:* Fehlerbericht auf Knopfdruck: neuer Knopf *Fehlerbericht senden* bei der Rückmeldung (Text optional). Ein Druck
  sendet ihn, die Benachrichtigung zeigt danach genau, was gesendet wurde. Er enthält, was zur Fehlersuche nötig ist: Version, je
  Auto Betriebsart, Ladestand und sein Alter, angesteckt, lädt, Ziel und Bedarf, Abfahrt nur als Abstand in Stunden, die nächsten
  Fenster des Plans, die Entscheidung, die letzten zehn Aktionen an der Wallbox, je Wallbox-Einstellung Integration, Modell und
  Firmware, aktueller Wert und Liste, wie schnell und wie oft Befehle ankamen oder fehlschlugen, ob die Sensoren Werte liefern, und
  die letzten 20 Warnungen von Plugwhen. Namen, Entitäts-IDs, Adressen, IP-Adressen und Kennungen werden vorher entfernt, keine
  Uhrzeiten. Unabhängig von *Anonyme Daten teilen*. Dashboard neu erstellen, damit der Knopf in der Karte *Rückmeldung* erscheint.

- **A changed setting acts at once:** reserve, target or mode now reach the wallbox and evcc right away, not only at the next run
  in up to five minutes. *Deutsch:* Eine geänderte Einstellung (Reserve, Ziel, Betriebsart) wirkt sofort auf Wallbox und evcc,
  nicht erst im nächsten Lauf nach bis zu fünf Minuten.

- **Slow wallbox over the cloud:** Plugwhen never runs two controls at once. A wallbox over the cloud may take 20 s or more per
  command; a second run meanwhile could send the same command again (e.g. press start twice). A run asked for meanwhile
  follows once afterwards, with the newest values. Error texts are readable: an error without a text of its own (e.g. no answer
  in time) shows at least its kind instead of an empty text.
  *Deutsch:* Langsame Wallbox über die Cloud: Plugwhen steuert nie zweimal gleichzeitig. Eine Wallbox über die Cloud braucht
  für einen Befehl manchmal 20 s oder länger; ein zweiter Durchlauf in der Zeit konnte denselben Befehl noch einmal senden
  (z. B. Start zweimal drücken). Ein Durchlauf, der in der Zeit fällig wird, folgt einmal danach, mit den neuesten Werten.
  Fehlertexte sind lesbar: Ein Fehler ohne eigenen Text (z. B. keine Antwort rechtzeitig) zeigt zumindest seine Art statt
  eines leeren Textes.

## 0.9.0 - 2026-11-14 - trips from a calendar, plans written into evcc, a stock

- **Sharing, new text (version 2):** the weekly statistics now use a random id that changes every month (the fixed id of
  older versions is deleted on the service once), plus a rough class of how long Plugwhen has been running. New: with a wallbox in the mode *Direct*, how fast and how reliably it takes a new value (per model and
  firmware, no names), and per whole day parked the loss of charge (no date, like the trip days). The text names every purpose,
  also summaries passed on to research or partners, always from at least 10 installations. The text is shorter: what is sent,
  never, what for, deleting; the details are on the privacy page. The service keeps the weekly data at most 60 days.
  *Deutsch:* Teilen mit neuem Text (Version 2): Die Wochenstatistik hat jetzt eine zufällige Kennung, die jeden Monat wechselt
  (die feste Kennung früherer Versionen wird am Dienst einmal gelöscht), dazu grob, wie lange Plugwhen schon läuft. Neu: bei einer Wallbox in der Betriebsart *Direkt*, wie schnell und verlässlich sie einen neuen
  Wert übernimmt (je Modell und Firmware, ohne Namen), und je ganzem Standtag der Ladungsverlust (ohne Datum, wie die Fahrtage).
  Der Text nennt alle Zwecke, auch Zusammenfassungen für Forschung oder Partner, immer aus mindestens 10 Installationen. Er ist
  kürzer: gesendet, nie, wofür, löschen; die Einzelheiten stehen auf der Datenschutzseite. Der Dienst behält die Wochendaten
  höchstens 60 Tage.

- **Review before the release (three fixes):** (1) The mode *direct* (and writing the plan into evcc) now also acts in the
  regular run every five minutes, not only when a sensor changes: a sleeping car at night does not report for hours, and the
  window of the plan begins at a time. Without a peak guard the wallbox could miss the start of the window. (2) "The learn mode
  is through" is remembered for good; it fell out after eight other messages and came again every week or two. (3) With a
  wallbox controlled by start/stop buttons, switching to *off* or *learn* now presses stop if Plugwhen had started charging.
  *Deutsch:* Durchsicht vor der Release, drei Korrekturen: (1) Die Betriebsart *Direkt* (und das Schreiben des Plans in evcc)
  handelt jetzt auch im regelmäßigen Lauf alle fünf Minuten, nicht nur, wenn sich ein Sensor ändert – ein schlafendes Auto meldet
  sich nachts stundenlang nicht, das Fenster des Plans beginnt aber zu einer Uhrzeit. (2) „Der Lernmodus ist durch“ wird dauerhaft
  gemerkt und kommt nicht mehr alle ein bis zwei Wochen. (3) Bei einer Wallbox mit Start/Stopp-Knöpfen drückt der Wechsel auf
  *Aus* oder *Lernen* Stopp, wenn Plugwhen das Laden gestartet hatte.
- **Create dashboard answers with the dashboard itself:** the whole response from the developer tools can be pasted into the
  raw configuration editor as it is (before it held the YAML text and the dashboard side by side, which the editor did not take).
- **The heads-up also in the dashboard (from feedback):** the evening notification "charge tomorrow" (with the sun, or when
  charging is needed) was only on the phone. The charge plan sensor now has the attribute `tip` with the same text, and the
  dashboard shows it under the state of the car: from the morning before, and on the day itself until the sun window is over
  ("Today it pays to charge ahead with the sun ..."). Also without a notify service. Create the dashboard again to get the line.
- **A drive home after midnight is not a departure (from feedback):** a first trip between 0:00 and 4:00 belongs to the evening
  before when that weekday mostly starts by day. Two drives home shortly after midnight had set the early departure on Sundays to
  0:00 (and the heads-up said "before the departure Sun 00:00"); 0.8.1 only caught trips already running before midnight. A
  weekday that mostly starts at night (shift work) keeps its night departures. The kilometres still count for the day.
- **Addresses with door, staircase or floor are found (from feedback):** OpenStreetMap does not find "Hauptstraße 5/2/7, Stiege 2,
  1010 Wien" as written. Plugwhen now tries the street without door, staircase and floor, then postcode and town alone (good enough
  for the kilometres). A location found nowhere is not asked again for a week.
- **Consumption per km is learned (it was not before):** from the falls of the state of charge on days with at least 30 km
  (times the capacity), median of the last 20 days; until 3 days are known the typed-in value. Attributes `consumption_source`,
  `consumption_days_with_temp`, `departure_temp_c` on the learned week sensor.
- **Consumption by outdoor temperature (optional):** with an outdoor temperature (own option or taken from the Wächter) each
  day gets its mean temperature. The need for a departure uses the temperature expected then (hourly weather forecast, else the
  sensor's current value within a day): the car's own line once 8 days over 8 K are known (colder never costs less), before that
  a rule of thumb (about 1 % per kelvin below 18 deg C, at most +40 %); a typed-in value only ever gets more. Without a
  temperature nothing changes.

- **Special trips are not learned:** the days of the events in the car's trip calendar are left out of the learned week (a single
  trip to Linz must not raise the kilometres of every Thursday). Attribute `trip_days_skipped` on the learned week sensor.
- **Share anonymous data, voluntary (default off):** asked in the last step of the set-up, afterwards the switch *Share
  anonymous data*. Weekly a usage statistic: a random id, versions, country and language, kinds of devices and the integrations
  their entities come from; switching off requests its deletion. Once a day the **trip days** (days with at least 30 km): car
  model, battery size, km, kWh per km, the day's mean outdoor temperature and the odometer only as a 10,000 km step; for days
  charged only at home the wallbox energy per full charge (charging losses, battery ageing). Without date, place or id (they
  cannot be deleted, they belong to no one). The service files the car under a model of a public list (open data) and says
  which; a car it does not know keeps its own name, and a model added to the list later is filed correctly without an update. Never names, entity ids, places or passwords. **Feedback:** a text field and a button on the device,
  and the action `send_feedback`.
- **Fleet values:** with sharing on, Plugwhen fetches the consumption of many cars of the same model (from 5 cars, else all cars)
  and uses it while the car has no values of its own: own curve, own model, all cars, start values. Attribute `fleet` on the
  learned days sensor; while sharing is off, a quiet card on the tab *Learning* says what the fleet values would bring.
  Sending or fetching never disturbs Plugwhen (service off, no network: everything as before, next try the next day).
- **Odometer and state of charge found through evcc:** evcc reports both for the car at its loadpoint; the car form proposes the
  sensors of Home Assistant that show the same values (the car's own integration before a copy of evcc's value, the state of charge only
  from the same device as the odometer, nothing when it is not unambiguous).
- **Set-up assistant:** two steps instead of an empty page. *What is there* says what was found (the Wächter is linked right away, evcc by
  the Wächter's address or on this machine; an address is asked only if evcc was not found). *Your cars* adds one car after the other,
  each prefilled from the Wächter and evcc; what is needed per car is its odometer and its state of charge.
- **Look-ahead: departures beyond the solar forecast are grey.** A window with daylight after the end of the forecast (the free
  Forecast.Solar reaches until tomorrow) is not "no sun" but "sun not known yet": its bar is grey, the chart says until when the
  forecast reaches, and each day carries `sun_known`, the look-ahead `sun_until`. Night-only windows are never marked.
- **Trips from a calendar** (per car, optional): every event in a calendar of Home Assistant is a trip. Start = departure; kilometres
  written in the title or description ("Linz 200 km") win, otherwise the route from home to the event's location via the Waze travel time
  integration (switch, default off; home and destination go to Waze), there and back unless the event says "einfach"/"one way". The range
  to have is the trip plus 15 %, at least the reserve. A trip replaces the learned departure of its day, in the plan and in the look-ahead.
  All-day events are ignored. Card **Planned trips**.
- **Mode "Via evcc"** (the mode per car gets a third choice, only for a car linked to an evcc car; the chosen mode is kept over a restart): the plan for the first departure that needs charging is written into evcc and kept up
  to date; when it is not needed any more it is removed. Only plans Plugwhen wrote itself are changed: a plan set in evcc by hand is never
  touched. The card says whether it is written. Repeating plans are still only proposed.
- **Stock** (per car, minimum state of charge, default off): Plugwhen never plans below it, so the car is ready for an unplanned trip.
- **Fix: the solar check stayed at 0 days.** Pairing the forecast with what the plant produced ran once a day inside the calibration
  and was skipped whenever an earlier part failed (e.g. the recorder not ready after a restart). It is its own step now, every 15 minutes,
  looks back 7 days, and the charge plan shows `solar_check` (forecasts remembered, days measured, last error).
- **The mode decides who controls, and sets what belongs to it:** "direct" puts the wallbox in its sun mode (e.g. Eco) as the base
  (evcc must only read this wallbox then: "off" in evcc blocks charging, so Plugwhen does not touch evcc's loadpoint); "via evcc" puts the wallbox in its grid mode
  (e.g. Default) and lets evcc regulate; "off"/"learn" give back everything Plugwhen set. Only what Plugwhen set itself is changed back.
- **With evcc, evcc controls; without evcc, Plugwhen:** a car linked to evcc is offered "via evcc", a car without evcc "direct" - never
  both (evcc's "off" blocks charging, so Plugwhen cannot control a wallbox evcc controls).
- **"Direct" can be released early** (setting, for trying it out) before "ready to switch" is green.
- **Locations for Waze are looked up at OpenStreetMap first:** the address search of the Waze integration fails at the moment
  (a place or address gives an error, coordinates work). Plugwhen finds the coordinates at OpenStreetMap (Nominatim, only the destination
  goes there, kept for good) and asks Waze with them. Coordinates in the location are used as they are.
- **A plan in evcc whose time has passed** (evcc keeps it) counts as done, not as your own plan: Plugwhen may replace it. A valid own
  plan is still never touched.
- **Mode "Direct": Plugwhen controls the wallbox**, offered only once "Ready to switch?" is green and the wallbox can be controlled. What it
  does depends on the wallbox, found on its device without settings: (A) a wallbox with its own next-trip mode (e.g. Fronius Wattpilot
  "Next Trip"): Plugwhen fills in departure and energy for a departure within 24 hours and switches to that mode, the wallbox keeps using
  the sun first; (B) a mode select with a sun and a grid mode: grid mode during the planned grid windows; (C) only start/stop: in the windows.
  Only what Plugwhen set is changed back; if you change the wallbox in between, it is left alone. The guard keeps the last word.
- **Ready to switch?** (sensor and card at the top of the overview): a checklist when Plugwhen may switch the wallbox itself (mode
  "direct", later): trips learned on every weekday the car is used, 7 days with a comparison in learn mode, at least 80 % decided the
  same as reality, and with a solar plant 5 days of checked solar forecast; with a rough date. One message per car when it is ready.
- **Dashboard in three tabs:** *Overview* (ready for the next departure, charge plan, planned trips with a calendar view and a short how-to,
  the next departures, plan for evcc), *Learning* (learn mode, does learning help, charging habit, plug-in times), *Details* (potential,
  sun and learned values, where the data comes from, settings). The most important first.

## 0.8.1 (unreleased) - trips over midnight

- **A trip that started the evening before and is still running after midnight is not a departure of the new day.** The learned early
  departure on Sundays was 00:00 in one house (Saturday-night trips home), which also showed up in the proposed evcc plans. The kilometres
  still count for the day.

## 0.8.0 (unreleased) - little to set with the guard

- **Adding a vehicle is filled in from the quarter-hour peak guard** when it knows the car: name, state of charge, capacity, charging
  power (the car's own, else computed from the wallbox currents), plug sensor and notify services, plus the odometer next to the state
  of charge and the energy counter next to the wallbox power (same device, counters win over measurements such as the range). Copied
  once: Plugwhen keeps working without the guard. The departure is not taken over (it would replace the learned departures).
- **evcc as an optional source** (read only, through its API; evcc may run anywhere on the network): address and password come from
  the guard or an own setting, a local evcc (add-on) is suggested. Adding a vehicle offers evcc's cars (the one at a loadpoint first)
  and fills in name, capacity and the charging power of the loadpoint. Plugged in and charging come from evcc when no sensor is set.
  Odometer and state of charge stay the car's own sensors: Plugwhen cannot calculate without them.
- **Card "Plan for evcc"** per car (attribute `evcc_plan` of the charge plan): the plan Plugwhen would write into evcc for the **first
  departure of the look-ahead that needs charging** (written early, e.g. "34 % by Friday 07:00" already on Monday, and following what
  happens: more kilometres raise it, sun in between drops it, then the next needed departure), and **repeating plans per weekday** from
  the learned week (equal times and targets grouped, e.g. "Tue-Fri 07:00 33 %"), each next to what evcc has now (`plan`, `repeatingPlans`), whether both are the same, and that nothing is written yet (learn
  mode). A plan already set in evcc that differs is shown as the user's own plan, which Plugwhen would never overwrite. Without evcc the
  card says that Plugwhen will switch the wallbox itself later (see "Would switch").
- **Card "Where the data comes from"** per car (attribute `sources`): sensor, evcc or learned for each value, the evcc connection,
  whether the plan is only a recommendation, and what the car was set up with.
- **An installed guard is connected when Plugwhen is set up**, so its grid counter, prices, limit and load forecast follow without a setting.

## 0.7.5 (unreleased) - the plan says that it is not executed

- The charge plan has a new attribute **`executed`** (`false`: Plugwhen recommends, it does not switch the wallbox). The quarter-hour
  peak guard reads it: before, a plan "not needed" took the car out of the guard's forecast although the car charged whenever it
  was plugged in (expected peak 2.5 kW, real 9.1 kW in one house).

## 0.7.4 (unreleased) - weak sun

- Sun that never reaches 1 kW in a quarter hour is not counted in the look-ahead any more: a wallbox cannot charge with it. Before,
  a pre-charge could be recommended without a sun window, and the text card *The next departures* broke on it.

## 0.7.3 (unreleased) - any sensor with the right unit

- **Odometer, state of charge, wallbox energy counter and grid energy can be any sensor**, also a template sensor without a device class.
  Before, such sensors were missing from the list (the same problem was reported for the peak guard). Instead of the device class the dialog
  now checks the **unit** when saving (kilometres or miles; percent; Wh, kWh or MWh) and says what to add if it does not fit.
  A sensor without any unit is accepted where Plugwhen assumes one (kilometres, percent, kWh).

## 0.7.2 (unreleased) - learn mode says when it is still learning

- The learn-mode chart *Plan against reality* shows **"Still learning · x of 7 days with a comparison"** instead of bars until seven days
  could be compared (days on which Plugwhen decided to charge or pause). A value only when it says something.
- **Shorter tile names and states** so that nothing is cut off on a phone: *Potential* (was *Potential of spreading the charging*), *Learning useful?*,
  states *Setting is enough* and *Helps with departure*.

## 0.7.1 (unreleased) - sun windows

- **Sun windows:** when does plugging in with the sun make sense? A strip chart for the next five days (car at home, sun available, orange
  frame where charging with the sun covers a need or replaces grid energy later) and the best window as a line below. Attributes
  `sun_windows` and `best_sun_window` in the look-ahead, attribute `sun_chart` at the charge plan; a card in the dashboard under *The next
  departures*. Works without a solar plant (the chart then says there is no forecast).

## 0.7.0 (unreleased) - look ahead, charging habit, house-only add

- **Look-ahead: when must I charge at the latest?** Up to fourteen days and ten departures ahead, for normal behaviour (the learned trips):
  until when the charge lasts (`lasts_until`), the first charging that is needed (`first_need`: day, latest start at the preferred power and at
  full power) and per departure the energy that is missing. Chart *The next departures* (sun in the same window, sun charged ahead, grid).
- **Charge ahead with the sun** (needs a solar forecast, works without a plant: then nothing is pre-charged): sun left over in an earlier window
  (the weekend) covers the grid energy of a later departure (Wednesday), as far as the battery stays below 80 %. A recommendation, nothing is switched.
- **Heads-up on the evening before:** tomorrow charging is needed (with the latest start), or charging ahead with the sun pays tomorrow. Once per
  day and kind, German and English texts. The plan chart shows the latest start at full power as a dashed line.
- **Charging habit:** sensor and chart, the energy per weekday during the day (9 to 17 h), at night (20 to 7 h) and in between, from the energy
  counter of the wallbox only (no solar plant needed, no judgement).
- **The quarter-hour add is measured for the house alone and by load level.** One learned value (0.26 kW in one house) was wrong: quiet hours
  need about 0.1 kW, loaded hours several, and in loaded hours the car's own current steps and the throttling are in the grid import and are modelled
  separately. Hours without wallbox energy are collected for good (the recorder keeps 5-minute values for ten days); a load level with fewer than
  12 hours uses the default 0.7 kW.
- **Learn mode also records the energy delivered although nothing was needed** (for example charging with the sun): `kwh_needless` and
  `needless_h` in the summary, a line on the card. The automatic mode needs that number.

## 0.6.1 (unreleased) - the check says what it knows about the departure

- **The check *Does learning help?* no longer shows "departure guessed right within one hour"** (31 to 46 % in one house, which looked
  like a failure and is the wrong question, because real departures vary). It shows what the plan aims at: ready in time with the plan
  until the usual departure against the early one (52 against 85 % in that house), and per weekday for the early plan.
- **New verdict `departure_helps`** (*Learning helps for the departure*): the kilometres hardly help, but the early plan is ready in
  time on at least 10 points more days than the median plan. The card says it in two plain lines, kilometres and departure.
  Attributes `ready_median_pct`, `ready_early_pct`, `departure_gain_points`, per weekday `ready_early_pct` and `ready_median_pct`.

## 0.6.0 (unreleased) - honest numbers

- **The plan aims at the early departure** (20th percentile of the weekday's first trips) instead of the median: a car that is ready at
  the median departure is late on about half of the early days. The check *Does learning help?* shows both as bars (ready in time:
  plan until the usual departure against plan until the early departure).
- **Preferred lowest charging power** (setting per car, default 4 kW): the rest is spread no flatter than this, because the car's charger
  wastes more energy at very low power; down to the wallbox minimum only if the energy does not fit. Attribute `spread_floor_kw`.
- **House-specific numbers learned instead of set** (daily, defaults until enough data, overridable): charging losses from days with
  home charging only; the deduction from the solar forecast from the night-time base load (the setting is optional now); the
  quarter-hour add of the potential calculator from the 5-minute statistics of the peak guard's grid import (was a fixed 0.7 kW measured
  in one house). Attributes `efficiency`, `efficiency_learned`, `solar_deduct_kw`, `solar_deduct_source`, `quarter_add_kw`.
- **Accuracy of the solar forecast**: predicted against measured solar energy per day (production statistic of the Energy dashboard);
  the median ratio of the last 30 days scales the forecast before the plan uses it (0.5 to 1.5). Attribute `solar_factor`.
- Dashboard: one line under the plan chart says which numbers are learned, set or default.

## 0.5.1 (unreleased) - does the learning help, two charts

- **Sensor "Does learning help?"**: walks through the history of the car day by day (the model only knows the days before each day):
  how many days the range would have been enough with the fixed reserve alone and with the learned value, and how often the departure
  hour was guessed right (within one hour) per weekday. Verdict: *learning helps*, *reserve is enough*, *little difference*, *too little
  data* (fewer than 21 days).
- **Two charts as SVG** (attribute `chart`, shown by a normal markdown card, no custom card): the check above (two bars and one bar per
  weekday) and, in learn mode, plan against reality per day (green = agreed, red = differed). German and English labels.
- Dashboard: card *Does learning help?* with the verdict in plain words and the chart; the learn mode card has its chart.
- **Three more charts** (attribute `chart` / `plug_chart`): the charge plan as a timeline from now to the departure (windows as bars,
  yellow = sun, blue = grid, departure marked), the potential as one bar per way of charging (highest quarter hour, demand charge,
  how often not ready), the plug-in times of the last 14 days as one strip per day.
- **Dashboard cleaned up, graphics first** (user feedback): fewer cards, charts instead of text and tables, one short line where a number
  needs words, settings stay. Left out: range needed and target state of charge (in the status line), the plan tile and text, the
  table of the learned week (the learning check shows it as a chart), explanation texts.

## 0.5.0 (unreleased) - learn mode

- **Mode per car** (select, *Off* or *Learn*, default Learn, the last choice survives a restart) and the sensor **Would switch**:
  in learn mode Plugwhen switches nothing, it works out what it *would* do (charge, pause, no decision, with the reason, until when,
  planned power) and writes it down. Unknown state of charge, a car that is not plugged in, nothing to charge or no departure are never
  decisions; a target that cannot be reached gives *charge* at once.
- **Comparison with reality** (needs the charging entity and/or the wallbox energy counter): per day how long decision and wallbox
  agreed, hours the wallbox charged although Plugwhen would have paused and the energy that came in, and the other way round; journal of
  the last decisions; both kept in a small store (60 days). Gaps longer than 20 minutes (restart, outage) are not attributed.
- Dashboard: card *Learn mode* (decision with reason, comparison of the last 7 days, journal, mode). Documentation: section *Learn mode*.
- Preparation for switching (planned): the log is the evidence on which it can be offered; switching itself is not built yet.

## 0.4.0 (unreleased) - sun first, the rest spread, real plug-in times

- **Sun first, the rest spread** (one logic for every household): the plan takes the expected solar surplus first while the
  car is at home, and spreads what is left over the parking time with the lowest even grid import (house plus car topped
  up to one level; quiet quarter hours get more). Before, the rest went into the quietest quarter hours at full power and,
  without a load forecast, bunched at the end like a wallbox "ready by" at full current. Without solar the rest is simply
  spread. Quarter hours below the wallbox minimum are dropped and the rest filled again.
- **Solar forecast of the Energy dashboard** (option, default on): any forecast set up there (Forecast.Solar, Solcast,
  Open-Meteo ...) counts as available power, minus a deduction for the house and a home battery (default 0.5 kW). An
  availability entity, if chosen, is used as well (the larger value per quarter hour). Attribute `availability_source`.
- **Plug-in times are written down** (when a plug entity is set): the recorder keeps them only for a few days, so Plugwhen
  stores them itself (about a year; the first start takes what the recorder still has). The readiness sensor shows how the
  car was plugged in over four weeks (`plugging`: plug-ins, nights plugged in, typical plug-in and unplug time). Nobody
  plugs in every day: the warning *plug in* only comes when the reserve would not last.
- **Potential calculator with real parking windows:** with recorded plug-in times the window starts at plugging in and ends
  at unplugging instead of assuming "plugged in from arrival" (`sessions_with_plug_times`).
- **The dashboard comes with the integration:** service `plugwhen.create_dashboard` (administrators) builds it with the
  entities of this installation, all vehicles (headings with the vehicle name when there are several), in German or English
  and in the currency of Home Assistant: next departure, charge plan with where the power comes from, potential with the
  comparison table, plug-in times, settings, learned week. Returned as YAML and shown as a notification; it never writes into
  an existing dashboard. Weekday names follow the language.
- Documentation: detailed README (what it needs, how it plans, plug-in times, warning, potential calculator and how the prices
  are calculated with and without the peak guard, cooperation with the guard, dashboard, entities, limits) and a German guide
  `docs/ANLEITUNG.md`.

## 0.3.0 (unreleased) - potential calculator

- **Potential calculator** (sensor *Potential of spreading the charging* per vehicle, service `plugwhen.calculate_potential`):
  replays the household's own history (grid import counter, wallbox counter, odometer; 90 days) with four ways of charging -
  as it was, spread evenly over the parking time, the wallbox's own "ready by" with 4.1 kW, and the peak guard - and compares the
  monthly peak quarter hour, the demand charge and how often the car would not have been ready. Result: *worth it*, *wallbox
  setting is enough*, *little*, *too little data* or *data missing*. Read only, an estimate; it says which data it used.
- Takes grid counter, prices, limit and measured peaks from the chosen quarter-hour peak guard; for the model check only months
  the guard did not change are used. Without prices only kW are shown.
- The estimate of the car's real quarter-hour power: inside a charging block its hourly mean, at the edges the block's level
  (a car that already charges slowly is not counted as a full-power peak; that would overstate the saving).
- Options: grid import counter, demand charge per kW and year (two levels and a threshold).

## 0.2.0 (unreleased) - plan, warning, connections

- **Charge plan** per vehicle (sensor *Charge plan*): in which quarter hours to charge until the departure. Available power
  (sun, community, tariff) first, then the quietest quarter hours under the peak target. The attributes `windows`,
  `needed_kwh`, `planned_kwh`, `departure`, `target_soc` are the interface other integrations read.
- **Warning that the car will not be ready** (sensor *Ready for departure*, switch, message through any notify service,
  from a chosen evening hour on, once per departure and kind): *plug in*, *too late* (not enough time even at full power),
  *not reachable*, or *too low* when the plug state is unknown. A plan does not silence the warning while the car is not
  plugged in. German and English texts.
- **Connections (options, all optional, Plugwhen also works alone):** the load forecast of the quarter-hour peak guard
  (found automatically and suggested) and a sensor of the *availability interface* (`schema`, `valid_until`, `forecast`).
- **Departure from an entity** (time or date-time) replaces the learned one; wallbox power (max/min), a *charging* entity.
- Reacts at once when the car is plugged in, starts charging or a watched entity changes, not only every five minutes.
- **Unknown state of charge** (for example while Home Assistant is starting): no energy to charge, no plan and no warning;
  the sensors say *unknown*.
- Several notify services can be named, separated by commas (one warning to every phone).
- **Connect by choosing the other integration:** in the options you choose the quarter-hour peak guard (a config entry), no entities
  by hand; its load forecast is found automatically. Suggested if exactly one is installed. The guard can do the same with Plugwhen.
  Tested with both integrations in one Home Assistant (16 checks, `tests/install/itest_both.py`).
- **Maximum age of the state of charge** (per vehicle, default 12 h, 0 = no limit; while the car is charging 90 minutes without a new
  value already count): a stale state of charge counts as unknown (no plan, no warning), for cars that send nothing while charging.
  Attributes `soc_stale`, `soc_age_h`.
- Installation test extended to 54 checks (plan, warning once, worse warning, switch off, connections, restart).

## 0.1.0 (unreleased) - show only

- First Home Assistant layer: one config entry, vehicles as subentries (odometer, state of charge, capacity, reserve,
  consumption, optional plug and wallbox energy counter).
- Learns per weekday from the long-term statistics (kilometres, departure hour, share of charging at home).
- Per vehicle: *Energy to charge*, *Range needed*, *Target state of charge*, *Expected departure*, *Learned days*
  (attribute `week`), the number *Reserve* and the switch *Learn kilometres per weekday* (default on).
- Pure-Python modules with tests: `learning`, `history`, `need`, `plan`, `notice` (plan and notice are not wired up yet).
- Installation test in Docker (`tests/install`).
