# Eigenständiger E-Auto-Lade-Planer: Zuschnitt (Stand 05.11.2026)

Ergänzt `docs/AUTO_PLANER_PLAN.md`. Entscheidung des Nutzers vom 05.11.2026: Der Lade-Planer wird ein **eigenes Projekt** (eigenes Repository,
eigene Integration), das **auch ohne den Viertelstunden-Wächter** installiert und betrieben werden kann. Der Wächter behält seinen einfachen
Ladeplan und arbeitet mit dem Planer zusammen, wenn beide da sind. Nichts davon ist gebaut.

## 1. Ziel und Abgrenzung
- **Ziel:** Das Auto ist zur Abfahrt bereit, mit möglichst wenig Netzstrom und ohne Lastspitzen. Der Planer **lernt** dafür, wie viel das Auto braucht
  (Kilometer je Wochentag), wann es losfährt und **wo** es geladen wird (zu Hause oder unterwegs).
- **Nicht Ziel:** kein Ersatz für evcc, keine Wallbox-Treiber, kein Tarifvergleich. Der Planer spricht Wallboxen und Autos nur über vorhandene
  Home-Assistant-Entitäten an (wie der Wächter).
- **Zielgruppe:** jeder E-Auto-Fahrer mit Home Assistant, nicht nur Österreich. Der Wächter selbst ist ebenfalls nicht auf Österreich beschränkt
  (siehe Abschnitt 8).

## 2. Was es schon gibt (Kurzrecherche 05.11.2026, nicht vollständig)
| Projekt | Kann | Kann (nach dieser Recherche) nicht |
|---|---|---|
| **evcc** (eigenständiges Ladeprogramm, auch mit Home Assistant nutzbar) | Ladeplan mit Abfahrtszeit und Zielstand, **wöchentlich wiederholbar je Wochentag**, günstigste oder grünste Stunden, Sonne zuerst, liest den Ladestand der Autos | Fahrverhalten lernen (Kilometer, Abfahrt, Ladeort), Hausverbrauch und Lastspitzen in die Planung einbeziehen. Der Planer ist nach der Doku nur in den Modi Solar und Min+Solar aktiv |
| **EV Smart Charging** (HACS, Jonas Karlsson, v1.10.1) | lädt nach Strompreis (Nord Pool, Energi Data Service, ENTSO-E), Preisgrenze, Laden bei niedrigem Ladestand | Fahrverhalten, Hausverbrauch, Sonne |
| **EMHASS** mit evcc als Ausführer | Optimierung der Energieflüsse, evcc führt aus | einfache Einrichtung, Lernen aus dem Auto |

Quellen: [evcc: Ladeplaner](https://docs.evcc.io/en/features/plans), [evcc: dynamische Tarife](https://docs.evcc.io/en/features/dynamic-prices),
[EV Smart Charging](https://github.com/jonasbkarlsson/ev_smart_charging/blob/main/README.md),
[EMHASS mit evcc](https://emhass.readthedocs.io/en/latest/cookbook/ev_evcc_executor.html).

**Folgerung:** Abfahrtszeit und Zielstand sind bei den anderen **von Hand eingegebene Wochenpläne**. Das Alleinstellungsmerkmal wäre, dass der
Planer diesen Wochenplan **selbst aus den Daten des Autos lernt**, mit Reserve, und das Haus (Last-Prognose) einbezieht. Zu prüfen, bevor man
baut: ob evcc oder die HACS-Integrationen das inzwischen anbieten (Releases ansehen) und ob der Planer evcc statt der Wallbox ansteuern könnte
(evcc nimmt Pläne über seine Schnittstelle an; nicht geprüft). Das würde die Hürde für evcc-Nutzer senken.

## 3. Module (alle bis auf `ha_*` reines Python ohne HA-Importe, wie `engine.py`)
1. `learning.py`: lernt je Wochentag Kilometer, Abfahrtsstunde, Ladeort und Verbrauch aus Tageswerten (letzte 8 Werte je Wochentag).
2. `need.py`: berechnet den Bedarf für den nächsten Tag: feste Grundreserve plus gelernter Bedarf (hoher Wert des Wochentags), Winterzuschlag.
3. `plan.py`: wählt die Ladeviertelstunden (Sonne zuerst, dann die ruhigsten Viertelstunden unter der Grenze, optional Preis). Vorbild: `plan.py` des Wächters.
4. `load_forecast.py`: einfache Last-Prognose des Hauses (Wochentag × Viertelstunde). Nur nötig, wenn der Wächter fehlt (Vorbild `forecast.py`).
5. `ha_*`: Konfiguration (Untereinträge Fahrzeug und Wallbox), Sensoren, Dashboard-Ansicht, später die Steuerung.

## 4. Schnittstelle zum Wächter (nur Entitäten, keine Code-Abhängigkeit)
| Von | Nach | Was |
|---|---|---|
| Planer | Wächter | Sensor **Ladeplan** mit Zustand (Geplant, Nicht nötig, Ziel nicht erreichbar, Keine Abfahrt) und Attributen `windows` (Beginn, Ende, kW), `needed_kwh`, `planned_kwh`, `departure`, `target_soc`. Der Wächter nutzt `windows` als erwartete Autolast in seiner Prognose |
| Wächter | Planer | Sensor **Prognose** (typisch und hoch je Viertelstunde, 24 h), **erlaubter Bezug jetzt**, **greift ein**. Der Planer nimmt sie statt seiner eigenen Prognose, wenn der Nutzer sie auswählt |
| beide | Wallbox | **Genau ein Schreiber je Wallbox.** Ist der Wächter eingerichtet, setzt er den Strom; der Planer gibt nur den **Wunschstrom** und Erlauben/Pausieren vor. Der Wächter begrenzt nur nach unten, der kleinere Wert gilt. Ohne Wächter schreibt der Planer selbst |

Einstellung im Planer: „Wallbox wird vom Viertelstunden-Wächter geregelt" (ja/nein). Das ist die wichtigste Regel, damit sich beide nicht gegenseitig überstimmen.

## 5. Kleinste erste Fassung (Version 0.1.0, nur lesen und anzeigen)
- **Enthalten:** Untereintrag *Fahrzeug* (Pflicht: Kilometerstand, Ladestand; optional angesteckt, lädt, Verbrauch, Kapazität), Lernen aus den Statistiken
  (Rückblick beim Start aus den Langzeitstatistiken, wie bei der Last-Prognose), Sensoren *Wochenplan*, *Bedarf morgen*, *Erwartete Abfahrt*,
  Dashboard-Ansicht mit Wochentabelle und Diagramm, Tests, README (Englisch), Anleitung (Deutsch), Schalter (Standard aus), CHANGELOG.
- **Nicht enthalten:** Wallbox steuern, Kalender, Preise, KI.
- **Prüfstein:** Mit den Daten des Autors (244 Tage) trifft der Plan an wie vielen Tagen die Reichweite? Ziel: mindestens 90 % bei einer Grundreserve von 100 bis 120 km.

## 6. Lernen, genauer
- **Eingänge je Tag:** Kilometer (Kilometerstand-Differenz, stündliche Statistik genügt), erste Bewegung (Stunde), Ladeereignisse aus dem Ladestand (Anstieg) mit und ohne Wallbox-Energie → *zu Hause* oder *unterwegs*.
- **Bedarf:** Wochentags-Median allein deckt nur etwa die Hälfte der Tage (Daten des Autors: 51 %). Deshalb **Grundreserve** (Einstellung, Vorschlag 100–120 km) plus
  hoher Wert (P75 bis P85) des Wochentags. Fester Mindeststand als Gegenstück: bei Fahrten über die Reserve hinaus kommt der Kalender (später) oder der Knopf „morgen weit fahren".
- **Verbrauch:** aus dem Auto (kWh/100 km) oder aus Wallbox-Energie geteilt durch Kilometer (Ladeverluste etwa 10 % dazu), Winterzuschlag aus den letzten Wochen.
- **Ladeort:** Wochentage, an denen meist unterwegs geladen wird, bekommen zu Hause nur die Reserve.

## 7. Stufen danach
1. **0.1:** anzeigen. 2. **0.2:** in den Ladeplan rechnen (Zielstand aus dem Bedarf) und mit dem Wächter koppeln. 3. **0.3:** Steuerung der Wallbox (eigener Schalter, Standard aus, nach Neustart aus; Sicherheitsregeln wie beim Wächter).
4. Später: Kalender, Preise (Nord Pool, aWATTar, Tibber), optional KI (Erklärer, Terminverständnis), evcc als Ausführer.

## 8. Markt (Kurzrecherche)
- **Flandern:** Seit 2023 zählt die höchste Viertelstunde des Monats (digitaler Zähler), rund **49–57 € je kW und Jahr** je nach Netzgebiet (2025). Es gibt dafür schon Home-Assistant-Anbindungen zum Mitlesen.
  Quellen: [VREG Tarifliste 2025](https://vlaamsenutsregulator.be/sites/default/files/Distributienettarieven_2025/vereenvoudigde_tarieflijsten_elek_2025.pdf), [Flanders capacity tariffs in Home Assistant](https://nathan-gs-website-raw.pages.dev/2022/11/27/flanders-capacity-electricity-tariffs-in-home-assistant).
- **Österreich:** Leistungspreis ab 2027 (je Netzbetreiber).
- **Skandinavien, Niederlande, Italien:** nicht belegt, bei Bedarf prüfen.
- **Folgerung:** Der Wächter ist nicht nur für Österreich interessant. Die README sagt das schon („in Austria from 2027, elsewhere already"). Eine englische README und Prüfung weiterer Tarife wäre der nächste Schritt.

## 9. Organisatorisches
- **Repository:** neu, öffentlich erst nach Prüfung auf Namen und Adressen, Commits als `mobilewhatelse` mit noreply-Adresse. Ordnerstruktur wie `viertelstunden-waechter` (`custom_components/<domain>/`, `hacs.json`, `tests/`, `docs/`).
- **Lizenz:** wie der Wächter (AGPL-3.0 und Handelslizenz, `LICENSING.md` mit Abschnitt zu Name und Logo).
- **Sprache:** Englisch zuerst, Deutsch als Übersetzung. Tests, hassfest, HACS-Prüfung und Installationstest im Docker wie beim Wächter.
- **Code teilen:** Anfangs `forecast.py` und `plan.py` kopieren; erst wenn sie stabil sind, eine gemeinsame Bibliothek (PyPI) prüfen.
- **Name:** **ReadyBy** (entschieden 05.11.2026; Integrations-Domain `ready_by`; Marke, Domain und HACS-Liste noch nicht geprüft).

## 10. Entscheidungen und offene Punkte
**Entschieden 05.11.2026:**
- Die **Grundreserve ist eine Einstellung** je Fahrzeug (Kilometer), kein fester Wert. Vorschlag als Startwert 100 km (deckt bei den Daten des Autors 87 % der Tage), 120 km (91 %) als Alternative.
- Der Planer bekommt ein **eigenes Repository** (Konto `mobilewhatelse`, zunächst privat).

**Offen:**
1. ~~Name~~ entschieden: ReadyBy (Icon B: Auto mit Blitz und Planstufen). Offen: Prüfung von Marke, Domain und Namenskonflikten vor der Veröffentlichung.
2. evcc als Ausführer in 0.2 prüfen (evcc kennt Lastpunkt-Pläne; Übergabe per API/MQTT nicht geprüft).
3. Wann wird das Repository öffentlich?
4. Soll der Wächter später den Planer als Ladeplan **ersetzen** oder dauerhaft beide Wege anbieten?

## 11. evcc im Quellcode angesehen (05.11.2026, Stichproben, nicht vollständig)
**Was evcc tut:** Planer wählt die günstigsten (oder grünsten) Zeitfenster bis zur Abfahrt, Pläne wiederholen sich wöchentlich, Plan-Sperre; Optimierer (lineares Programm) mit Tarifen,
Solarprognose, 4-Wochen-Grundlastprofil in 15-min-Schritten (Perzentil einstellbar), Batterie- und Fahrzeugziele; Lastkreise (`circuit`) mit festen Grenzen für Strom/Leistung;
Strategien „Spitzen abschwächen" (Bezug, Einspeisung, Bedarf); Wärmebedarfsvorhersage (Tag/Wochentag/Temperatur).
**Gefunden wurde nicht:** Lernen von Kilometern, Abfahrt oder Ladeort aus dem Auto, Auswertung des Kilometerstands; Begriffe wie Leistungspreis, Monatsspitze, capacity tariff
tauchen im Code nicht auf. Die Grenze eines Kreises ist ein fester Wert, kein Monatsmaximum.
**Unterschied des Planers:** (1) lernt den Wochenplan selbst aus Kilometerstand und Ladestand statt Eingabe von Hand, (2) Grundreserve plus gelernter Bedarf, (3) Ziel ist die
Monatsspitze (Leistungspreis), nicht der Preis, (4) läuft als Home-Assistant-Integration ohne weiteres Programm. **Ehrlich:** evcc ist ausgereift; der Vorsprung liegt allein im Lernen
und im Leistungspreis. Wer evcc nutzt, braucht den Planer nur als Lieferant des Plans.

## 12. Flandern (Wächter) – Vorschlag
Belegt: Kapazitätstarif seit 2023 (höchste Viertelstunde des Monats), ca. 49–57 €/kW/Jahr; HA-Gemeinschaft rechnet das schon mit (Blog nathan-gs, Forum-Thread DSMR-Monatsspitze).
1. **Anpassen:** Tarif mit Mindestleistung (in Flandern wird mindestens 2,5 kW abgerechnet; vor Aufnahme prüfen) und Preisfeld je Netzgebiet; nl-BE-Texte; README-Abschnitt „Belgium/Flanders" mit P1/DSMR-Zähler als Quelle (Sensor Viertelstundenmittel oder Momentanleistung).
2. **Testen:** 2–3 flämische Tester über den HA-Community-Thread und die Autoren der Blogs gewinnen; ehrlich „bisher an einer Anlage getestet".
3. **Verbreiten:** Beitrag im HA-Forum (Englisch) und r/homeassistant, Thread „DSMR monthly 15-minute peak values", Tweakers/Reddit r/belgium, Hinweis bei Anbietern von Wallbox/PV-Foren; Screenshot und HACS-Link.
4. **Nicht belegt:** Netzgebiets-Preise je Anbieter, Zählerausstattung, Verbreitung steuerbarer Wallboxen; vor Werbung prüfen.

## 13. Eingänge und Schnittstelle (Entscheidung 05.11.2026)
**Datenaustausch zwischen Integrationen** ist erlaubt und üblich, solange er über Home-Assistant-Mittel läuft (Entitäten, Attribute, Events, Dienste).
Verboten für uns: Code der anderen Integration importieren, `dependencies` im Manifest (der Planer muss ohne Wächter laufen; höchstens `after_dependencies`).

**Quelle je Eingang wählbar** (Einrichtungsdialog des Planers):
1. **Entität:** beliebige Entität; findet der Dialog Entitäten des Wächters (Entity-Registry, Plattform `viertelstunden_waechter`), schlägt er sie vor.
2. **Von Hand:** Feld oder Helfer (fester Grenzwert, Wochenplan).
3. **Selbst lernen:** aus den Statistiken, wie `forecast.py`.

Eingänge: Haus-Prognose, Grenze (erlaubter Bezug), **Verfügbarkeit von Strom** (Sonne, Gemeinschaft, Preis), je Auto Kilometerstand und Ladestand.

**Verfügbarkeits-Schnittstelle** (offener Vertrag, jeder darf liefern, z. B. Wächter mit Genossenschaftsanbindung, Forecast.Solar, Preissignal, Webhook):
- Sensor, Zustand = verfügbare kW jetzt; Attribute:
  - `schema`: 1
  - `valid_until`: ISO-Zeit; danach ignoriert der Planer die Meldung (Signal verfällt)
  - `forecast`: Liste `{start, end, kw}` je Viertelstunde (UTC, `kw` = für das Laden verfügbare Leistung dieses Teilnehmers)
  - optional `source`: Text (z. B. „community", „solar", „price")
- Der Planer behandelt sie wie eine Solarprognose: Ladeviertelstunden bevorzugt dort, wo `kw` verfügbar ist. Fehlt der Sensor, entfällt der Eingang.
- Der Wächter reicht Genossenschaftsdaten **nicht** als Zwischenstation durch, er stellt sie nur als solchen Sensor bereit.

**Vorbehalte zur Genossenschaft:**
- Zuteilung: Hohe Erzeugung des Nachbarn heißt nicht, dass man den Strom bekommt. Bei Tullnerfeld wird die Einspeisung voll zugeteilt; dann zählt nur der eigene Anteil. `kw` muss den **eigenen** Anteil meinen.
- Datenschutz: Daten einzelner Nachbarn nur mit Einwilligung; besser nur Summen oder eigene Anteile.

