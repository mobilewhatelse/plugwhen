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
- **Name:** **Plugwhen** (entschieden 05.11.2026 nach Recherche, siehe 14 und 15; Integrations-Domain `plugwhen`; Marke in TMview/EUIPO noch nicht geprüft). Arbeitsname war ReadyBy, verworfen wegen Wallbox-Begriff „Ready-By" und gleichnamiger Software.

## 10. Entscheidungen und offene Punkte
**Entschieden 05.11.2026:**
- Die **Grundreserve ist eine Einstellung** je Fahrzeug (Kilometer), kein fester Wert. Vorschlag als Startwert 100 km (deckt bei den Daten des Autors 87 % der Tage), 120 km (91 %) als Alternative.
- Der Planer bekommt ein **eigenes Repository** (Konto `mobilewhatelse`, zunächst privat).

**Offen:**
1. ~~Name~~ entschieden: Plugwhen (Icon B: Auto mit Blitz und Planstufen). Offen: Marke in TMview/EUIPO/Patentamt prüfen und Domain sichern (plugwhen.com, .io, .app, .eu, .dev hatten per DNS keinen Eintrag), vor der Veröffentlichung.
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

## 14. Namensprüfung ReadyBy (verworfen, 05.11.2026, Stichproben, keine Rechtsberatung)
- **HACS und Home Assistant:** In der HACS-Standardliste (4944 Einträge) und unter den Home-Assistant-Integrationen gibt es nichts mit `readyby`/`ready_by`; auf GitHub keine Integration mit dem Ordner `custom_components/ready_by`. Domain `ready_by` ist damit frei.
- **Internet-Domains (nur DNS-Abfrage, kein Registrar-Test):** `readyby.com` und `readyby.eu` sind belegt (Seiten nicht lesbar); `readyby.app` gehört einer App „ReadyBy“ (ReadyBy Ltd, Rückwärtsplanung von Terminen, nichts mit Auto oder Energie); `getreadyby.com` ist belegt, die Seite leer. Ohne DNS-Eintrag: `.at`, `.io`, `.dev`, `.energy` (das heißt nicht, dass sie frei sind).
- **Marke:** In den Suchtreffern keine Eintragung gefunden. TMview, EUIPO und das Österreichische Patentamt sind damit **nicht** geprüft (Suchmaschinen indizieren sie kaum); das muss direkt dort geschehen, bevor es kommerziell wird.
- **Risiken:** (1) „Ready-by“ ist im Ladebereich ein beschreibender Begriff (Wallbox nennt eine Planungsfunktion seiner App „Ready-By“), als Marke schwach und mit einem Hersteller-Begriff verwechselbar. (2) Eine Software mit gleichem Namen („ReadyBy“, Terminplanung) existiert; bei Software (Klasse 9) kann das kollidieren, auch wenn der Zweck verschieden ist.
- **Empfehlung:** Als Projektname im Open-Source-Betrieb unkritisch. Vor kommerzieller Nutzung TMview prüfen; ein Zusatz hilft (z. B. „ReadyBy Charge“) und die Domain mit Zusatz sichern.


## 15. Alternativnamen (Recherche 05.11.2026, Stichproben)
Geprüft: Namen auf GitHub, in der HACS-Standardliste (4944) und bei Home-Assistant-Integrationen, DNS von .com/.io/.app/.eu/.dev (belegt/„frei?" ohne Registrar-Test), Websuche nach Produkt oder Marke.
Marken wurden **nicht** in TMview/EUIPO geprüft.

| Name | GitHub/HACS/HA | Domains (DNS) | Websuche | Anmerkung |
|---|---|---|---|---|
| **Plugwhen** | kein Treffer | alle frei?, auch .com | nichts gefunden | sagt, wann man ansteckt; selbsterklärend, leicht beschreibend |
| **Dawnplug** | kein Treffer | alle frei?, auch .com | nichts; ähnlich: Wallbox „Charge Amps Dawn" | Bezug auf Morgen/Abfahrt; „Dawn" ist ein Wallbox-Produktname eines Herstellers |
| Plugcast | kein Treffer | .com belegt | nichts gefunden | gut, aber .com weg |
| Chargewhen, Chargeby, Plugready | kein Treffer | .com belegt | nicht einzeln geprüft | |
| Departly, Wattwhen, Fullby | wenige kleine Treffer | .com belegt | nicht einzeln geprüft | |
| Wakeful, Amply, Topup, Kwhen, Carplan | viele oder bekannte Treffer | belegt | | **nicht verwenden** |

Empfehlung: **Plugwhen** (frei auf allen geprüften Wegen, kein Treffer in Websuche und Listen), zweite Wahl **Dawnplug**. ReadyBy bleibt Arbeitsname, bis entschieden ist.

## 16. Benachrichtigung „Auto morgen nicht bereit" (Idee des Nutzers 05.11.2026, Entscheidungsteil gebaut)
Modul `notice.py` (rein Python, 12 Tests): vergleicht den Bedarf von `need.py` mit dem, was geschieht, und liefert eine Meldung oder nichts.
- **Arten:** `not_reachable` (Ziel größer als Akku oder erlaubtes Maximum), `too_late` (auch mit voller Ladeleistung bis zur Abfahrt nicht zu schaffen), `plug_in` (Auto bekannt nicht angesteckt und unter dem Ziel),
  `low` (Zustand des Steckers unbekannt, nichts geplant). Keine Meldung bei kleinem Fehlbetrag (< 0,5 kWh), laufender Ladung oder einem Plan, der den Fehlbetrag deckt.
- **Zeitpunkt:** ab einer einstellbaren Abendstunde bis zur Abfahrt (`should_check`); einmal je Abfahrtstag und Art (`dedupe_key`, eine schlimmere Art ist eine neue Meldung).
- **Noch zu bauen (Home-Assistant-Schicht):** Wahl des Notify-Dienstes, Meldungstexte Deutsch/Englisch, Schalter (Standard an), Abendstunde als Einstellung, Eingänge „angesteckt" und „lädt" aus den Auto-/Wallbox-Entitäten.

## 17. Bauart: eigenständig, mit dem Wächter verbindbar, HACS-tauglich (Vorgabe des Nutzers 05.11.2026)
**Drei Forderungen, ein Aufbau:**
1. **Eigenständig installierbar.** Keine Abhängigkeit vom Wächter (`dependencies` leer, höchstens `after_dependencies` für `recorder`, `energy`). Alle Eingänge sind **Entitäten-Auswahlfelder** mit drei Quellen
   (Entität / von Hand / selbst lernen, siehe 13). Ohne Wächter lernt der Planer die Hauslast selbst (`load_forecast.py`, noch nicht gebaut) oder arbeitet ganz ohne Last-Prognose
   (`plan.py` kennt auch „keine Last, keine Spitzengrenze").
2. **Mit dem Wächter verbindbar, nur über Entitäten.** Der Planer *erkennt* Entitäten des Wächters in der Registry (Plattform `viertelstunden_waechter`) und schlägt sie im Einrichtungsdialog vor
   (Prognose, erlaubter Bezug, „greift ein"); der Wächter bekommt den Plan als Sensor *Ladeplan* (Attribute `windows`, `needed_kwh`, `planned_kwh`, `departure`, `target_soc`) und die
   Meldung. Dazu kommt die Verfügbarkeits-Schnittstelle (13). Regel „genau ein Schreiber je Wallbox": Einstellung „Wallbox wird vom Viertelstunden-Wächter geregelt" (ja/nein); bei „ja" gibt der Planer nur den Wunschstrom vor.
3. **HACS-Integration, die wir in die Standardliste einreichen.** Anforderungen (vom Wächter bekannt):
   - ein Repo = eine Integration, Ordner `custom_components/plugwhen/`, `manifest.json` (Domain, Version, Codeowner, `documentation`, `issue_tracker`, `integration_type: service`, `iot_class: calculated`), `hacs.json` (liegt schon), Icons in `brand/` (liegen schon),
   - Repo öffentlich, Beschreibung und Themen (Topics) gesetzt, README mit „What is this for?", Releases mit Tags,
   - Workflows `hassfest` und `hacs/action` grün (Vorlage `docs/validate.yml.vorlage`; das GitHub-Token braucht dafür das Recht `workflow`: `gh auth refresh -s workflow` durch den Nutzer),
   - Aufnahme per Pull Request in `hacs/default`; Prüfung dort dauert und verlangt, dass die Integration schon läuft (Installationstest wie `tests/install` beim Wächter, im Docker mit hassfest).

**Schichten (nur die oberste kennt Home Assistant):**
`learning.py`, `need.py`, `plan.py`, `notice.py` (fertig, rein Python, getestet) → `coordinator.py` (liest Entitäten, ruft die Module, hält Zustand und Speicher) → Plattformen `sensor`, `switch`, `number`, `select`, `button` → `config_flow.py` mit Untereinträgen (Fahrzeug, Wallbox).

**Reihenfolge der HA-Schicht (jede Stufe lauffähig und testbar):**
1. 0.1.0 *nur anzeigen*: Einrichtung (ein Eintrag, Untereintrag Fahrzeug mit Kilometerstand, Ladestand, Kapazität, Reserve, optional angesteckt/lädt), Lernen aus den Langzeitstatistiken, Sensoren Wochenplan, Bedarf morgen, Abfahrt; Schalter „Kilometer je Wochentag lernen" (Standard an).
2. 0.2.0 Ladeplan als Sensor, Verfügbarkeits-Eingang, Verbindung zum Wächter (Vorschläge, Wallbox-Regel), Benachrichtigung „Auto morgen nicht bereit" (Notify-Dienst, Schalter, Abendstunde).
3. 0.3.0 Steuerung der Wallbox (eigener Schalter, nach Neustart aus), danach Veröffentlichung und Antrag bei HACS.

## 18. Prognosebetrieb ohne Echtzeitdaten (Idee des Nutzers 05.11.2026, für Stufe 0.3, nichts gebaut)
**Anlass:** Haushalte ohne schnellen Zähler (zum Beispiel nur das Portal des Netzbetreibers, Werte alle 15 Minuten bis am nächsten Tag) können den Viertelstunden-Wächter
nicht zum Regeln nutzen: Er braucht alle paar Sekunden einen Messwert. Das Auto ist aber der größte Verbraucher und die Spitzen kommen oft vom Laden am Abend oder frühmorgens.
Plugwhen kann auch mit Stundenwerten arbeiten (Lernen aus der Langzeitstatistik, Plan, Warnung).

**Modus „Prognosebetrieb" (Schalter, später mit der Wallbox-Steuerung der Stufe 0.3):**
- Plugwhen legt das Laden in die ruhigen Stunden (wie der Plan heute) **und begrenzt den Ladestrom** auf das, was unter die Grenze passt:
  `Strom = Grenze − erwarteter hoher Hausbezug (Prognose „hoch") − Sicherheitsabstand`, aufgerundet auf die kleinste Wallbox-Stufe, nie unter dem Minimum der Wallbox.
- **Sicherheitsabstand einstellbar**, Vorschlag 2 bis 3 kW, weil ein Stundenmittel nur eine Untergrenze seiner vier Viertelstunden ist. Mit echten 15-Minuten-Werten (zum Beispiel aus dem Portal als
  importierte Statistik) kann der Abstand kleiner sein.
- Ohne Echtzeitdaten gibt es **keine Rückmeldung**: Eine unvorhergesehene Last (Backrohr, Trockner) in derselben Viertelstunde sieht niemand. Der Modus senkt die typischen Spitzen, garantiert aber nichts.
- Läuft der Wächter mit Echtzeitdaten, ist er die genauere Lösung; beide schließen sich nicht aus (Regel „genau ein Schreiber je Wallbox", siehe 4 und 17).

**Ehrliche Aussage in der Anleitung:** was der Modus kann (Laden in ruhige Zeiten, Strom begrenzen, Warnung) und was nicht (kurzfristige Spitzen, Echtzeit-Schutz).
**Voraussetzung:** mindestens Stundenwerte des Netzbezugs als Statistik; bessere Prognose mit 15-Minuten-Werten.


## 19. Was bringt es wirklich? Ergebnis einer Auswertung mit echten Daten (06.11.2026)
Simulation auf den Stundenwerten eines Haushalts (Netzbezug, Wallbox, Kilometerstand; zwei Monate), kalibriert mit Viertelstundenwerten; das Modell trifft die
gemessenen Spitzen ohne Steuerung auf etwa ±0,7 kW. Verglichen wurden: ohne Steuerung, nur Wächter (verschiedene Grenzen), nur Planer (Laden gleichmäßig über
die Standzeit verteilt, ohne Echtzeit), Planer + Wächter, nur Wallbox-Einstellung („fertig bis“ mit kleinem Strom).

**Allgemeine Schlüsse (Mechanismen, nicht Zahlen):**
1. Spitzen entstehen, wenn das Auto in einem kurzen Fenster mit voller Leistung lädt (spät vor der Abfahrt oder sofort beim Heimkommen).
2. Der größte Hebel ist das **Verteilen der Ladeenergie über die Standzeit**. Es senkt die Spitze stärker als eine niedrige Wächter-Grenze und braucht keine
   Echtzeitdaten. Ein Wächter allein kann einen späten Ladebeginn nur drosseln; mit niedriger Grenze wird das Auto dann nicht fertig.
3. Der Wert hängt ab von: Tarif (€/kW, Schwellen), Energiebedarf im Verhältnis zur Standzeit, Hauslast, und ob die Wallbox selbst „fertig bis“ mit
   einstellbarem Strom kann (dann holt man viel schon ohne Software).
4. Warnung „nicht bereit“ und das Lernen der Kilometer bringen wenig; Abfahrtszeit und Standzeit zählen.
5. Der Echtzeit-Wächter bleibt der Schutz vor ungeplanten Spitzen (Herd, Trockner) und lohnt sich zusätzlich.

**Folgerung für Plugwhen:** Zuerst ein **Potenzialrechner** (jeder Nutzer bekommt diese Rechnung auf seinen eigenen Daten: Spitze und Kosten mit und ohne
verteiltes Laden, wie oft das Auto fertig wird, ob eine Wallbox-Einstellung reicht). Danach die Steuerung (0.3): Bedarf gleichmäßig bis zur Abfahrt verteilen,
mit Aufholregel; eine Last-Prognose ist dafür nicht nötig.

**Für den Betrieb ohne Wächter fehlt:** Steuerung der Wallbox über Entitäten (Strom, Phasen, Start/Stopp) oder über deren „fertig bis“-Funktion, Aufholregel
(liegt die Ladung hinter dem Plan → hochregeln; sehr niedriger Ladestand → sofort laden), Rückfallregeln (Auto lädt bei kleinem Strom nicht, Ladestand unbekannt),
Anstecken als Fensterbeginn. Vorhanden: Abfahrt, Bedarf, Plan, Warnung.

## 20. Potenzialrechner gebaut (06.11.2026) und Regel für die Steuerung (0.3)
- `potential.py` (rein Python, Tests) + Sensor *Potenzial durch verteiltes Laden* + Dienst `plugwhen.calculate_potential`. Rechnet täglich und auf Abruf,
  nur lesend, aus der Langzeitstatistik (Netzbezug, Wallbox-Zähler, Kilometerstand, 90 Tage). Übernimmt Zähler, Preise, Grenze und Monatsspitzen vom gewählten Wächter.
  Am Wächter muss dafür **nichts** geändert werden.
- Mit den Daten des Autors deckt sich das Modul mit der Auswertung (verteilt 212 €/Jahr, Wallbox-Einstellung 201, Wächter allein 321, wie bisher 492;
  Ersparnis verteilt ≈ 280 €/Jahr gegen wie bisher, ≈ 109 €/Jahr gegen Wächter allein; Urteil „lohnt sich").
- **Regel für 0.3 (Nutzer 06.11.):** Der Wächter steuert weiter in Echtzeit, sobald eine Spitze droht, und hat das letzte Wort (begrenzt nur nach unten, der kleinere
  Wert gilt). Drosselt er, muss Plugwhen den Rest **neu verteilen** (Aufholen bis zur Abfahrt) und bei Bedarf „zu spät" melden.
- **Wie Plugwhen vom Drosseln erfährt (Nutzer 06.11.):** nur über Entitäten, am Wächter wird nichts geändert. Hauptweg: Plugwhen vergleicht, was tatsächlich
  angekommen ist (Wallbox-Zähler, Ladestand), mit dem Plan und holt auf, egal warum es weniger war (Wächter, Auto, Wallbox). Zusatz, wenn der Wächter gewählt ist:
  dessen Status-Sensor („greift ein", Attribut `interventions`, Sensor „Entlastung jetzt") als Erklärung und als Anstoß, sofort neu zu rechnen.
  Beide Integrationen bleiben einzeln voll lauffähig.


## 21. Sonne zuerst, Rest verteilt, echte Steckzeiten (gebaut 06.11.2026, Version 0.4.0)
- **Vorgaben des Nutzers 06.11.:** allgemeingültig (nicht jeder hat einen Fronius/Wattpilot, nicht jeder hat PV), **niemand steckt täglich an**,
  lieber mit Sonne laden als nachts, aber beide Fälle müssen gehen (ohne PV wird nachts geladen).
- **Eine Logik für alle:** (1) erwarteter Sonnenüberschuss zuerst, solange das Auto zu Hause steht; (2) der Rest über die Standzeit verteilt, mit dem
  niedrigsten gleichmäßigen Netzbezug („Auffüllen wie Wasser": Haus plus Auto auf einen gemeinsamen Pegel, ruhige Viertelstunden bekommen mehr; Viertelstunden
  unter dem Wallbox-Minimum fallen weg). Ohne PV entfällt (1). Vorher landete der Rest ohne Lastprognose mit voller Leistung am Ende – genau das Muster von
  „Nächste Fahrt" beim Wattpilot, das die Spitzen verursacht.
- **Sonne:** Solarprognose aus dem Energie-Dashboard (jede dort eingerichtete, Option Standard an) minus fester Abzug für Haus und Hausakku (Standard 0,5 kW).
  Nicht die Lastprognose des Wächters abziehen: die ist Netzbezug, tagsüber ist die Sonne darin schon verrechnet (sonst doppelt).
- **Steckzeiten:** Recorder hält den Stecker-Verlauf nur ~10 Tage, Binärsensoren haben keine Langzeitstatistik → Plugwhen schreibt An/Ab selbst mit (Store, ~1 Jahr,
  Erststart aus dem Recorder), Zusammenfassung am Bereitschafts-Sensor (`plugging`). Der Potenzialrechner nimmt damit die echten Fenster statt „ab Ankunft".
- **Befund beim Autor (27.10.–06.11.):** von 10 Nächten 5 angesteckt, dann jeweils gleich bei der Ankunft (19:15 nach Ankunft 19:12, 18:01 nach 18:00); tagsüber
  mehrmals mit Sonne. Die Annahme „angesteckt ab Ankunft" stimmte für die Nächte mit Ladung. Für Nutzer heißt das: **nichts ändern, normal anstecken**;
  „Bitte anstecken" kommt nur, wenn die Reserve nicht reicht.
- Plugwhen steuert weiterhin **nicht** (Stufe 0.5); der Plan ist Anzeige und Schnittstelle (`windows`).
