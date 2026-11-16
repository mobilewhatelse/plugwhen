# Plugwhen – Anleitung (Deutsch)

Stand: Version 0.9.0. Plugwhen **plant und zeigt an**. Steuern tut es erst, wenn Sie es wollen: in der Betriebsart „Über evcc“ (Plan in evcc) oder „Direkt“ (Plugwhen schaltet die Wallbox selbst, erst nach bestandenem Lernmodus). Standard ist „Lernen“: Plugwhen schaltet nichts und schreibt nur auf, was es tun würde.

## Wofür?

Plugwhen sorgt dafür, dass das E-Auto **zur Abfahrt bereit** ist, mit möglichst wenig Netzstrom und **ohne Lastspitzen**. Es lernt aus
dem Auto selbst: wie viele Kilometer es je Wochentag fährt, wann es losfährt und wo es geladen wird (zu Hause oder unterwegs). Daraus plant
es das Laden bis zur nächsten Abfahrt.

- **Für wen:** alle mit E-Auto und Home Assistant, mit oder ohne Photovoltaik, mit jeder Wallbox und jedem Auto, das Home Assistant lesen kann.
- **Was es nicht ist:** kein Ersatz für evcc, keine Treiber für Wallboxen oder Autos (es liest nur Entitäten), kein Tarifvergleich, keine
  Planung von Schnellladen unterwegs.

## Was es braucht

| Entität | nötig | wofür |
|---|---|---|
| Kilometerstand (mit Langzeitstatistik) | ja | Fahrten je Wochentag, Abfahrtszeiten |
| Ladestand (%) | ja | was noch fehlt |
| Stecker-Sensor (Auto angesteckt) | empfohlen | Warnung „Bitte anstecken“, Steckzeiten |
| Energiezähler der Wallbox | empfohlen | zu Hause oder unterwegs geladen, Potenzialrechner |
| „Lädt gerade“-Sensor | optional | beim Laden gilt ein Ladestand, der älter als 90 Minuten ist, als unbekannt |
| Abfahrt (Zeit- oder Datum/Zeit-Entität) | optional | ersetzt die gelernte Abfahrt |
| Benachrichtigungsdienste (durch Komma getrennt) | optional | die Warnung, z. B. an zwei Handys |

Je Auto stellen Sie Akkugröße, Reserve (km), Verbrauch (bis der echte Wert gelernt ist) und die **Wallbox-Leistung** ein (höchste und kleinste,
z. B. 11 oder 22 kW und 1,4 kW für einphasig 6 A). Eine bestimmte Marke wird nirgends vorausgesetzt.

## Einrichten

1. Integration hinzufügen: Einstellungen → Geräte & Dienste → Integration hinzufügen → **Plugwhen**. Ein Assistent führt in zwei
   Schritten durch:
   1. **Was ist da?** Plugwhen zeigt, was es gefunden hat: den Viertelstunden-Wächter (wird gleich verbunden) und evcc (Adresse vom
      Wächter oder auf diesem Rechner gefunden). Nur wenn evcc woanders läuft und nicht gefunden wurde, tragen Sie die Adresse ein.
   2. **Ihre Autos:** **Auto hinzufügen**. Das Formular ist aus dem Wächter und evcc vorbefüllt, soweit es geht; nötig sind je Auto
      Kilometerstand und Ladestand. Mehrere Autos nacheinander, dann **Einrichtung abschließen**.
2. Weitere Autos später auf der Integrationsseite: **Fahrzeug hinzufügen**.
3. Optional über das Zahnrad: den **Viertelstunden-Wächter** wählen (wird vorgeschlagen, wenn er installiert ist), Solarprognose an/aus und Abzug,
   Verfügbarkeits-Sensor, Energiezähler Netzbezug und Leistungspreise für den Potenzialrechner.
4. Dashboard erstellen (siehe unten).

## Wie geplant wird

1. **Bedarf:** die Fahrt des Tages (der gelernte hohe Wert des Wochentags, mit *Kilometer je Wochentag lernen*) **plus die Reserve**: Die
   Reserve bleibt nach der Fahrt übrig (Standard ab 0.10). Wer es wie früher will, wählt beim Auto *Mindestreichweite bei der Abfahrt*: dann
   ist die Reserve die Untergrenze, in der die Fahrt schon enthalten ist. Daraus folgen Ziel-Ladestand und Energie (mit Ladeverlusten).
   **Für mehrere Tage auf einmal (ab 0.10):** Geladen wird erst, wenn der Akku unter dem Bedarf der nächsten Fahrt liegt, dann aber gleich
   für die Fahrten der nächsten Tage (Einstellung *Für so viele Tage auf einmal laden*, Standard 3; 1 = jeder Tag für sich), höchstens bis
   zur *Obergrenze im Alltag* (Standard 80 %; eine lange Fahrt oder das wöchentliche Volladen gehen darüber). Das gibt weniger und größere
   Ladungen, und niemand muss täglich anstecken: Warnung, Zusage und Sicherheitsprüfung gelten nur der nächsten Fahrt. **Mit Solaranlage
   kommt zuerst die Sonne:** Was die Prognose für die Zeit verspricht, in der das Auto zwischen den nächsten Fahrten zu Hause steht **und
   üblicherweise angesteckt ist** (gelernt aus den mitgeschriebenen Steckzeiten, nach etwa zwei Wochen), bleibt der Sonne überlassen; nur
   der Rest kommt aus dem Netz. Gerechnet wird nur mit dem, was planbar ist. Die nächste Fahrt wird immer rechtzeitig geladen. Sonnenstrom,
   der kommt, während das Auto angesteckt ist, wird immer genutzt, mit oder ohne Plan: Der Sonnenmodus der Wallbox bleibt zuständig,
   Plugwhen begrenzt ihn nie. Passt die Ladung für mehrere Tage nicht mehr vor die Abfahrt, wird sie auf das gekürzt, was passt; die
   nächste Fahrt geht immer vor.
2. **Zuerst die Sonne:** Solange das Auto zu Hause steht, wird zuerst der erwartete Sonnenüberschuss genutzt. Er kommt aus der **Solarprognose des
   Energie-Dashboards** (jede dort eingerichtete: Forecast.Solar, Solcast, Open-Meteo …) minus einem Abzug für Haus und Hausakku (Standard 0,5 kW).
   Die Last-Prognose des Wächters wird dafür bewusst nicht abgezogen: Sie ist Netzbezug, tagsüber steckt die Sonne schon darin.
   Ein *Verfügbarkeits*-Sensor (z. B. Energiegemeinschaft oder Tarifsignal) kann dazukommen; je Viertelstunde zählt der größere Wert.
3. **Der Rest wird verteilt:** Was die Sonne nicht schafft, wird über die Standzeit mit dem **niedrigsten gleichmäßigen Netzbezug** verteilt: Haus und
   Auto werden auf einen gemeinsamen Pegel aufgefüllt, ruhige Viertelstunden bekommen mehr, belebte weniger oder nichts, nie über dem Spitzenziel.
   Viertelstunden unter dem Wallbox-Minimum fallen weg. Ohne Photovoltaik bleibt nur dieser Schritt.
4. **Ehrlich:** Reicht die Zeit bis zur Abfahrt nicht, sagt der Plan, wie viel fehlt.

Warum verteilen: Eine Wallbox mit „fertig bis“ und vollem Strom lädt spät und kräftig (z. B. 10 kW von 4 bis 6 Uhr) und bestimmt damit die
Monatsspitze. Über die Nacht verteilt braucht dieselbe Energie 2–3 kW.

**Einmal pro Woche voll laden (ab 0.9.2).** Viele Hersteller empfehlen, den Akku ab und zu ganz voll zu laden (z. B. damit die Anzeige des
Ladestands stimmt). Je Auto gibt es dafür den Schalter *Einmal pro Woche voll laden* (Standard aus), die Tage als Leiste
*Mo Di Mi Do Fr Sa So* zum Antippen (ein Schalter je Wochentag, Standard Samstag und Sonntag; kein Tag angetippt heißt kein Volladen) und das *Ziel beim wöchentlichen Volladen* (Standard 100 %). Mit Solarprognose nimmt Plugwhen
von den erlaubten Tagen, die in dieser Woche noch kommen, den mit der meisten Sonne, ohne Photovoltaik den ersten. Für einen Plan, der
diesen Tag enthält, gilt das höhere Ziel: zuerst mit Sonne, der Rest aus dem Netz, damit das Auto sicher voll wird. Wie immer verteilt
der Plan den Netzanteil in die ruhigen Stunden vor der Abfahrt, so steht der Akku nicht lange voll. Ohne Abfahrt an dem Tag ist das Auto
bis 20 Uhr voll. Einmal je Woche (Montag bis Sonntag): ist das Ziel erreicht, gilt bis zur nächsten Woche wieder das normale Ziel.
Die Karte *Einstellungen* zeigt, für welchen Tag das Volladen geplant ist.

**Sicherheitsprüfung vor jeder Abfahrt (ab 0.9.2).** Ab drei Stunden vor jeder Abfahrt prüft Plugwhen jeden Tag, ob das Auto das
zugesagte Ziel noch erreicht. Ist das geplante Ziel gesunken, lädt die Wallbox nicht, obwohl sie laut Plan laden sollte, oder wird die
Zeit knapp, schaltet Plugwhen in den Betriebsarten *direkt* und *evcc* auf „Jetzt laden“ und schickt eine Nachricht mit dem Grund an
die Benachrichtigungsdienste des Autos; dieselbe Meldung steht unter *Benachrichtigungen* in Home Assistant. Gemeldet wird nur, wenn
Plugwhen wirklich eingreift, je Abfahrt und Grund einmal. „Jetzt laden“ endet beim Ziel, bei der Abfahrt oder beim Abstecken. In den Betriebsarten *aus*
und *lernen* fasst Plugwhen die Wallbox nicht an; dort meldet wie bisher die Warnung, wenn das Auto nicht bereit sein wird.

## Steckzeiten

Home Assistant hebt den Verlauf eines Stecker-Sensors nur wenige Tage auf, Binärsensoren haben keine Langzeitstatistik. Plugwhen schreibt An- und
Abstecken deshalb selbst mit (etwa ein Jahr; beim ersten Start übernimmt es, was der Recorder noch hat). Der Sensor *Bereit zur Abfahrt* zeigt im
Attribut `plugging`: wie oft und wie viele Nächte in vier Wochen angesteckt, typische Ansteck- und Abziehzeit.

**Niemand muss täglich anstecken.** Stecken Sie an wie gewohnt; „Bitte anstecken“ kommt nur, wenn die Reserve bis zur nächsten Abfahrt nicht reicht.

## Die Warnung

*Bereit zur Abfahrt* ist `ready` oder sagt, was zu tun ist: `plug_in` (anstecken), `low` (Steckerzustand unbekannt, zu wenig), `too_late` (auch mit
voller Leistung reicht die Zeit nicht), `not_reachable` (Ziel mit dem Akku nicht erreichbar), `unknown` (kein frischer Ladestand). Ab einer
gewählten Abendstunde (bei einer Abfahrt in den nächsten 12 Stunden auch früher), einmal je Abfahrt und Art, an alle eingetragenen
Dienste. Ist das Auto sicher nicht angesteckt und kam die Warnung schon am Tag, kommt ab der Abendstunde einmal eine Erinnerung.
Bei „nicht erreichbar“ und „zu spät“ bittet sie dann trotzdem ums Anstecken (Plugwhen lädt so viel wie möglich). Texte auf Deutsch und Englisch.

## Potenzialrechner

Sensor *Potenzial durch verteiltes Laden* und Dienst `plugwhen.calculate_potential` (nur Administratoren). Er spielt Ihren eigenen Verlauf nach
(90 Tage Netzbezugszähler, Wallbox-Zähler, Kilometerstand) und vergleicht vier Ladeweisen: höchste Viertelstunde je Monat, Leistungspreis und wie
oft das Auto nicht fertig gewesen wäre.

| Ladeweise | Bedeutung |
|---|---|
| wie bisher | was wirklich passiert ist |
| nur Spitzenwächter | wie bisher, aber jede Viertelstunde unter der Grenze des Wächters gehalten (nur wenn der Wächter gewählt ist) |
| Wallbox fertig-bis, kleiner Strom | die eigene Fertig-bis-Funktion der Wallbox mit 4,1 kW |
| verteilt (Plugwhen) | die Energie gleichmäßig über das Standzeit-Fenster |

Das Standzeit-Fenster ist das echte, sobald Steckzeiten mitgeschrieben sind, sonst die Annahme „angesteckt ab Ankunft“.
Urteil: *lohnt sich*, *Einstellung reicht* (die eigene Funktion der Wallbox schafft fast dasselbe, ohne die Abfahrt zu verpassen), *gering*
(weniger als 1 kW Unterschied), *zu wenig Daten* (unter 14 Tagen oder 5 Ladungen) oder *Daten fehlen*.

**So werden die Preise gerechnet:**

- Monatskosten = (Spitze bis zur Schwelle × Preis bis zur Schwelle + Rest darüber × Preis darüber) / 12; im Jahr = Durchschnitt der Monate × 12.
- Spitze eines Monats = höchste Stunde des Hauses + 0,7 kW (so weit liegt eine Viertelstunde über dem Stundenmittel) + das Auto in der jeweiligen Ladeweise.
- **Woher die Preise kommen:** aus den Plugwhen-Einstellungen (Leistungspreis je kW und Jahr bis zur Schwelle, darüber, Schwelle; 0 = ein Preis) oder,
  wenn dort nichts steht, vom gewählten Spitzenwächter.
- **Ohne Wächter** tragen Sie die Preise und den Netzbezugszähler in Plugwhen ein; die Zeile „nur Spitzenwächter“ fehlt dann.
- **Ganz ohne Preise** zeigt er nur kW; das Urteil funktioniert trotzdem, weil es an den kW hängt.
- „Höchste Spitze“ ist der schlechteste Monat, die Kosten sind der Durchschnitt der Monate – deshalb passen die zwei Spalten nicht 1:1 zusammen.
- Eine Schätzung aus Stundenwerten, keine Rechnung.

## Bereit zum Schalten?

Ganz oben in der Übersicht steht je Auto eine Checkliste, wann Plugwhen die Wallbox **selbst** schalten darf (Betriebsart „Direkt“):
Fahrten an jedem genutzten Wochentag gelernt (mindestens 3 Beispiele), **7 Tage mit Vergleich** im Lernmodus (Tage, an denen
geladen oder pausiert würde), **mindestens 80 % gleich entschieden** wie die Wirklichkeit und, mit Solaranlage, **5 Tage geprüfte
Sonnenprognose**. Dazu ein ungefähres Datum. Ist alles erfüllt, kommt einmal eine Nachricht. Bis dahin plant und warnt Plugwhen, und in
der Betriebsart „Über evcc“ lädt evcc nach dem Plan.

## Betriebsart „Direkt“: Plugwhen steuert die Wallbox

Erst wählbar, wenn „Bereit zum Schalten?“ grün ist **und** sich die Wallbox steuern lässt. Plugwhen findet am Gerät der Wallbox selbst
heraus, was sie kann (die Karte „Bereit zum Schalten?“ zeigt es):

- **Abfahrtsmodus der Wallbox** (z. B. Fronius Wattpilot „Next Trip“): Plugwhen trägt nur Abfahrtszeit und Energie ein und stellt auf diesen
  Modus, wenn für eine Abfahrt in den nächsten 24 Stunden geladen werden muss. Die Wallbox nutzt weiter zuerst die Sonne und lädt den Rest
  rechtzeitig. Danach stellt Plugwhen den vorherigen Modus (z. B. Eco) zurück.
- **Moduswechsel** (Lademodus mit Sonnen- und Netzmodus): in den geplanten Netz-Fenstern Netzmodus, sonst zurück.
- **Nur Start/Stopp:** Start am Anfang, Stopp am Ende eines geplanten Fensters.

Plugwhen ändert nur zurück, was es selbst gesetzt hat. Stellen Sie die Wallbox zwischendurch selbst um, lässt Plugwhen sie bis zur
nächsten Abfahrt in Ruhe; nur die Sicherheitsprüfung („Jetzt laden“) greift trotzdem ein. Ist die Wallbox kurz nicht erreichbar,
wartet Plugwhen und vergisst nichts.

**Die Betriebsart entscheidet, wer steuert, und stellt mit um:** „Direkt“ stellt die Wallbox auf ihren Sonnenmodus (z. B. Eco) als
Grundstellung; evcc darf diese Wallbox dann **nur lesen** (oder gar nicht da sein), denn „Off“ heißt in evcc „Laden gesperrt“ und nicht
„evcc hält sich raus“ – steuert evcc die Wallbox, ist „Über evcc“ die richtige Betriebsart; „Über evcc“ stellt die Wallbox auf
ihren Netzmodus (z. B. Default) und lässt evcc regeln; „Aus“ und „Lernen“ geben alles zurück. Zum Ausprobieren lässt sich „Direkt“ in den
Einstellungen **vorzeitig freigeben**, bevor „Bereit zum Schalten“ grün ist.

**Mit evcc steuert evcc, ohne evcc Plugwhen:** Ein Auto, das mit einem evcc-Fahrzeug verknüpft ist, bekommt die Betriebsart „Über evcc“,
ein Auto ohne evcc-Verknüpfung „Direkt“. Nie beides: „Off“ heißt in evcc „Laden gesperrt“, Plugwhen kann also keine Wallbox steuern, die
evcc steuert. Wer „Direkt“ testen will, entfernt beim Fahrzeug die evcc-Verknüpfung. Der
Wächter hat weiter das letzte Wort.

## Fahrten aus dem Kalender, Vorrat

**Wozu?** Plugwhen lernt deine typische Woche. Eine Fahrt, die nicht dazu passt (Linz am Samstag, Urlaub), kann es nicht vorhersehen.
Trag sie in den Kalender ein, dann ist das Auto trotzdem rechtzeitig voll.

- **Kalender mit Fahrten** (je Auto, optional): Jeder Termin in einem Kalender von Home Assistant (zum Beispiel ein lokaler Kalender
  „Fahrten“ oder ein eingebundener Google-/Outlook-Kalender) ist eine Fahrt. Beginn = Abfahrt. **Kilometer** stehen im Titel oder in der
  Beschreibung („Linz 200 km“) und gelten zuerst; sonst rechnet Plugwhen die Strecke von zu Hause zum **Ort** des Termins über die
  Integration **Waze Travel Time** (Schalter in den Einstellungen, Standard aus; die Integration einmal hinzufügen, ohne Konto; Zuhause und
  Ziel gehen an Waze), hin und zurück, außer im Termin steht „einfach“. Der **Ort** kann ein Ortsname, eine Adresse oder
  Koordinaten („48.2082,16.3738“) sein. Weil die Adresssuche von Waze über Home Assistant derzeit nicht funktioniert, sucht Plugwhen den Ort
  zuerst bei **OpenStreetMap** (nur das Ziel geht dorthin, einmal je Ort) und fragt Waze dann mit den Koordinaten. Reichweite bei Abfahrt = Kilometer plus 15 %, mindestens die
  Reserve. Die Fahrt ersetzt die gelernte Abfahrt dieses Tages, im Plan und in der Vorausschau. Ganztägige Termine zählen nicht.
  Karte **„Eingetragene Fahrten“**.
- **Vorrat** (je Auto, Mindest-Ladestand, Standard 0 = aus): Darunter plant Plugwhen nie, damit das Auto auch für eine ungeplante Fahrt
  bereit ist.


**Sonderfahrten werden nicht gelernt:** Die Tage, an denen im Fahrten-Kalender des Autos etwas eingetragen war, lässt Plugwhen beim
Lernen der typischen Woche weg. Eine einzelne Fahrt nach Linz soll nicht die Kilometer aller Donnerstage erhöhen. Wie viele Tage
ausgelassen wurden, steht im Attribut `trip_days_skipped`.

## Mit evcc

- evcc ist **optional** und wird nur **gelesen** (über seine Adresse, evcc kann irgendwo im Netz laufen). Die Adresse kommt aus dem Wächter
  oder wird in den Einstellungen von Plugwhen eingetragen; ein evcc auf demselben Rechner (Add-on) wird vorgeschlagen.
- Kilometerstand und Ladestand bleiben die Sensoren des Autos: ohne sie kann Plugwhen nicht rechnen.
- Beim Hinzufügen eines Fahrzeugs werden die Autos aus evcc angeboten (Name, Akkugröße, Ladeleistung). „Angesteckt“ und „lädt“ kommen aus
  evcc, solange dafür kein Sensor eingetragen ist.
- Karte **„Plan für evcc“**: welchen Plan Plugwhen in evcc schreiben würde, und zwar **für die erste Abfahrt, für die geladen werden muss**
  (aus der Vorausschau, also früh, z. B. schon am Montag „34 % bis Fr 07:00“). Der Plan wird laufend angepasst: mehr Kilometer heben ihn,
  Sonne dazwischen lässt ihn wegfallen, danach kommt die nächste nötige Abfahrt. Dazu **Wochenpläne** aus der gelernten Woche (evcc kennt
  wiederkehrende Pläne je Wochentag; gleiche Zeiten und Ziele werden zusammengefasst, z. B. „Di–Fr 07:00 33 %“). Daneben steht jeweils,
  was in evcc gerade eingestellt ist.
  Es wird noch nichts geschrieben (Lernmodus). Ein in evcc selbst gesetzter Plan würde nie überschrieben. **Ohne evcc** schaltet Plugwhen
  die Wallbox später selbst; im Lernmodus zeigt „Würde schalten“, was es täte.
- **Betriebsart „Über evcc“** (je Auto, neben „Aus“ und „Lernen“, nur bei einem Auto mit evcc-Fahrzeug; die Wahl bleibt nach einem Neustart; es schaltet immer nur einer, evcc oder später Plugwhen direkt, Sie wählen): Plugwhen schreibt den Plan für die erste nötige Abfahrt in evcc und hält ihn aktuell
  (evcc lädt dann); wird er nicht mehr gebraucht, wird er entfernt. Geändert werden **nur Pläne, die Plugwhen selbst geschrieben hat**,
  einen in evcc selbst gesetzten Plan fasst es nie an. Wochenpläne werden vorerst nur vorgeschlagen.
- Karte **„Woher die Daten kommen“**: für jeden Wert, ob er von einem Sensor, aus evcc oder gelernt ist.

## Zusammen mit dem Viertelstunden-Wächter

Beide laufen auch allein. Es genügt, die andere Integration in den Einstellungen zu wählen, Entitäten müssen nicht ausgesucht werden:

- Plugwhen liest die **Last-Prognose** des Wächters (erwarteter Bezug, Spitzenziel), seinen Zähler, die Preise und die Grenze.
  Diese Werte laufen mit: Ändern Sie die Grenze im Wächter, rechnet Plugwhen sofort damit.
- **Wenig einzustellen:** Ist der Wächter schon installiert, wenn Plugwhen eingerichtet wird, ist er sofort verbunden. Beim Hinzufügen eines
  Fahrzeugs füllt Plugwhen das Formular mit dem, was der Wächter über das Auto und die Wallbox weiß: Name, Ladestand, Akkugröße,
  Ladeleistung, Stecker-Sensor, Benachrichtigung, dazu Kilometerstand und Energiezähler vom selben Gerät. Diese Werte werden einmal kopiert,
  Plugwhen läuft also auch weiter, wenn der Wächter später entfernt wird. Die Abfahrtszeit wird bewusst nicht übernommen: Eine feste
  Abfahrtszeit der Wallbox würde die gelernten Abfahrten ersetzen.
- Der Wächter liest die **Ladepläne** von Plugwhen (Attribut `windows`) in seine Prognose ein und zeigt sie ab Version 0.14 in seinem Dashboard
  statt seines eigenen Plans. Den eigenen Ladeplan des Wächters dann ausschalten, damit nicht zwei Pläne nebeneinander stehen.
- **Der Wächter hat immer das letzte Wort:** Käme trotzdem eine Spitze, drosselt er wie gewohnt. Plugwhen vergleicht, was wirklich angekommen
  ist, mit dem Plan und verteilt den Rest neu.

## Dashboard

Der Dienst **Dashboard erstellen** (`plugwhen.create_dashboard`, nur Administratoren) baut das Dashboard mit den Entitäten **Ihrer** Installation,
für alle Fahrzeuge, auf Deutsch oder Englisch und in Ihrer Währung: nächste Abfahrt, Ladeplan (woher der Strom kommt), Potenzial mit
Vergleichstabelle, Steckzeiten, Einstellungen und gelernte Woche. Nur Standardkarten.

**So geht's:** Entwicklerwerkzeuge → Aktionen → *Dashboard erstellen* ausführen, die ganze Antwort (oder das YAML aus der Benachrichtigung) kopieren.
Dann Einstellungen → Dashboards → Dashboard hinzufügen, öffnen, drei Punkte → Bearbeiten → drei Punkte → Roher Konfigurationseditor, einfügen,
speichern. Der Dienst **schreibt nie in ein bestehendes Dashboard**. Nach dem Hinzufügen eines Fahrzeugs neu erstellen.

## Ehrliche Zahlen: was gelernt statt gesetzt wird

Jede Zahl, die vom Haus oder vom Auto abhängt, hat eine Vorgabe, die überall funktioniert, und Plugwhen ersetzt sie durch einen gelernten Wert,
sobald genug Daten da sind (täglich im Hintergrund; das Dashboard sagt, welcher gerade gilt):

| Zahl | Vorgabe | Gelernt aus |
|---|---|---|
| Abfahrt, auf die der Plan zielt | gelernte mittlere Stunde | die **frühe** Abfahrt (20. Perzentil der ersten Fahrten des Wochentags): ein Auto, das zur mittleren Abfahrt fertig ist, ist an etwa der Hälfte der frühen Tage zu spät |
| bevorzugte kleinste Ladeleistung | 4 kW (Einstellung je Auto) | der Plan verteilt nicht flacher; der Lader im Auto hat unter wenigen kW höhere Verluste; bis zum Minimum nur, wenn die Energie sonst nicht passt |
| Ladeverluste | nach der bevorzugten Ladeleistung: etwa 11 % bei 4 kW, 24 % bei 1,4 kW, 7 % bei 11 kW (Startwert aus Messungen des ADAC 2026) | Tage mit Laden nur zu Hause: Anstieg des Ladestands × Akkugröße gegen die Wallbox-Energie (begrenzt auf 2 bis 25 %) |
| Verbrauch nach Außentemperatur | Startkurve: +8 % bei 10 °C, +22 % bei 0 °C, +60 % bei −15 °C gegen 20 °C, etwas mehr über 25 °C (eigene Ableitung aus veröffentlichten Flottenzahlen) | die eigene Gerade durch Verbrauch und Temperatur, ab 8 Tagen über mindestens 8 K |
| Abzug von der Solarprognose | 0,5 kW | die nächtliche Grundlast (Median der Stunden 1 bis 5 des Bezugszählers); eine Einstellung geht vor |
| Viertelstunden-Zuschlag des Potenzialrechners | 0,7 kW | die 5-Minuten-Statistik des Netzbezugs des gewählten Wächters, **nur für das Haus** (Stunden ohne Wallbox-Energie) und **nach Lastzustand** (ruhige, mittlere, hohe Stunden): höchste Viertelstunde über dem Stundenmittel, 80. Perzentil; ein Zustand braucht 12 Stunden, bis dahin gilt dort 0,7 kW; die Stunden werden dauerhaft gesammelt |
| Treffsicherheit der Solarprognose | 1,0 | erwartete gegen gemessene Solarenergie je Tag (Erzeugungsstatistik des Energie-Dashboards), Median der letzten 30 Tage, 0,5 bis 1,5; der Plan rechnet mit der skalierten Prognose |

## Vorausschau: wann muss ich spätestens laden?

Der Plan reicht bis zur nächsten Abfahrt; am selben Tag ist es oft schon zu spät. Die **Vorausschau** geht bis zu **vierzehn Tage und zehn
Abfahrten** weit und beantwortet **bei normalem Verhalten** (den gelernten Fahrten): *Bis wann reicht der Ladestand, und wann muss das Laden
spätestens beginnen?* Für jede Abfahrt wird die fehlende Energie gerechnet (das Auto muss mit mindestens der Reichweite losfahren, die der Bedarf
verlangt; nach jeder Fahrt hat es die erwartete Energie verbraucht) und der **späteste Start**: die Abfahrt minus die Zeit, die bei bevorzugter
Leistung und bei voller Leistung nötig ist.

- **Mit Sonne vorladen** (mit Solarprognose, z. B. aus dem Energie-Dashboard): Sonne, die in einem früheren Fenster übrig ist (zum Beispiel am
  Wochenende), wird für den Netzstrom einer späteren Abfahrt genutzt (zum Beispiel Mittwoch), solange der Akku unter 80 % bleibt und die Sonne reicht.
  Beispiel: *Samstag 10 bis 13 Uhr, 14 kWh, ersetzt Netzstrom vor Mittwoch 07:00.* Die Grafik *Die nächsten Abfahrten* zeigt, woher der Strom jeder
  Abfahrt kommt: Sonne im selben Fenster (gelb), mit Sonne vorgeladen (orange), Netz (blau). **Grau** heißt: Netz, aber die Sonne ist noch nicht bekannt, weil das Fenster hinter dem Ende
  der Solarprognose liegt (die kostenlose Forecast.Solar-Prognose reicht nur bis morgen). Unten steht, bis wann die Prognose reicht.
  Für eine Woche Vorschau eine Prognose mit mehr Tagen im Energie-Dashboard eintragen, z. B. Open-Meteo Solar Forecast.
- **Eine Vorwarnung am Vorabend:** Ab der Abendstunde der Warnung sagt Plugwhen, dass **morgen** geladen werden muss (mit dem spätesten Start) oder
  dass sich morgen das Vorladen mit Sonne lohnt. Einmal je Tag und Art. Laden, das heute geschehen muss, ist Sache der Anstecken-Warnung.
- **Sonnenfenster:** eine Streifengrafik für die nächsten fünf Tage: grau, wo das Auto voraussichtlich zu Hause ist (roter Strich = Abfahrt), gelb, wo in
  dieser Zeit die Sonne Leistung liefert, ein **oranger Rahmen, wo sich das Anstecken lohnt** (es deckt einen Bedarf oder ersetzt Netzstrom vor einer
  späteren Abfahrt). Darunter: *Am sinnvollsten: Sa 10:00–13:00, bis zu 12 kWh.* Sonne ohne Bedarf wird ohne Rahmen gezeigt. Ohne Solarprognose sagt die
  Grafik das; sonst braucht Plugwhen keine Anlage. Nur eine Empfehlung, es wird nichts geschaltet. Die Daten stehen im Attribut `sun_windows` (und
  `best_sun_window`) der Vorausschau.
- **Ohne Solaranlage** wird nichts vorgeladen; die Vorausschau sagt dann nur, was jede Abfahrt aus dem Netz braucht und bis wann.
- Sie **empfiehlt nur, es wird nichts geschaltet.** Die Annahmen sind offen: Wie lange das Auto weg ist, folgt aus der Länge der Fahrt (3 Stunden plus
  1 Stunde je 12 km, 3 bis 10 Stunden), bis es aus den Steckzeiten gelernt wird; die Fahrten sind die typischen. Die Solarprognose reicht so weit, wie
  der Anbieter sie liefert, danach rechnet die Vorausschau mit dem Netz.
- Das Plan-Bild zeigt den spätesten Start bei voller Leistung als gestrichelte Linie.

## Wann laden Sie? (die Ladegewohnheit)

Sensor **Ladegewohnheit** (Anteil der Energie, die nachts, 20 bis 7 Uhr, in den letzten 90 Tagen geladen wurde) und eine Grafik je Wochentag: die Energie an
einem durchschnittlichen Montag, Dienstag und so weiter, **tagsüber (9 bis 17 Uhr)**, **nachts** und dazwischen. Sie braucht nur den Energiezähler der
Wallbox, keine Solaranlage, und sie bewertet nicht (mit Nachtstrom ist nachts laden genau richtig). Sie zeigt, wohin sich das Laden verschieben ließe: Ein Wochentag mit viel
Laden in der Nacht ist, wo Netzstrom und Spitzen herkommen. Unter 28 Tagen Daten steht *zu wenig Daten*.

## Bringt das Lernen etwas? (eine Prüfung am eigenen Verlauf)

Sensor **Bringt das Lernen etwas?** (und eine Karte mit zwei Grafiken im Dashboard). Er geht den Verlauf *Ihres* Autos Tag für Tag durch, und an
jedem Tag kennt das Modell nur die Tage davor. Zwei Fragen:

- **Hätte die Reichweite gereicht?** Mit der festen Reserve allein (was ein Auto ohne Lernen vorhielte) und mit der Reserve, angehoben um das
  für den Wochentag Gelernte (der größere Wert aus Reserve und 80. Perzentil des Wochentags). Zwei Balken zeigen den Anteil der Tage.
- **Wäre das Auto rechtzeitig fertig gewesen?** Ein Plan bis zur üblichen (mittleren) Abfahrt gegen einen bis zur frühen Abfahrt (20. Perzentil), als
  zwei Balken und dann je Wochentag für den frühen Plan. Echte Abfahrten schwanken, deshalb ist nicht „auf die Stunde erraten“ die nützliche Zahl,
  sondern „rechtzeitig fertig“; darum zielt der Plan auf die frühe Abfahrt.

Urteil: **Lernen hilft** (mindestens 5 Prozentpunkte mehr Tage gedeckt), **Hilft bei Abfahrt** (die Kilometer helfen kaum, aber der frühe
Plan ist an mindestens 10 Punkten mehr Tagen rechtzeitig fertig als der mittlere), **Reserve reicht** (weniger als 2 Punkte: die Reserve allein genügt, der
gelernte Wert kostet nichts, bringt aber wenig), **kaum Unterschied** oder **zu wenig Daten** (weniger als 21 Tage prüfbar). Tage ohne Kilometer
zählen nicht. Beim Auto des Autors deckt die Reserve allein etwa 88 % der Tage, mit dem Gelernten etwa 90 %; am meisten hilft der Verlauf bei der
Abfahrtszeit.

Die Karte des Lernmodus hat eine zweite Grafik: je Tag die Stunden, in denen Plan und Wallbox übereinstimmten (grün), und die Stunden, in denen
sie abwichen (rot).

## Lernmodus

Je Auto hat die Auswahl *Betriebsart* die Stellungen **Aus**, **Lernen** (Standard), **Über evcc** (nur mit evcc-Fahrzeug) und
**Direkt** (siehe oben, erst wenn „Bereit zum Schalten?“ grün ist). Die letzte Wahl bleibt über einen Neustart erhalten. Im Lernmodus **schaltet Plugwhen nichts**. Es berechnet nur für jeden Moment, was es tun *würde*, und schreibt es auf:

- der Sensor **Würde schalten** sagt `laden`, `pausieren` oder `keine Entscheidung`, mit Grund (im geplanten Fenster, wartet auf das nächste
  Fenster, der Plan ist abgearbeitet, das Ziel ist knapp also so viel wie möglich sofort, Ladestand unbekannt, Auto nicht angesteckt, nichts
  nötig), wann sich die Entscheidung voraussichtlich ändert und mit welcher Leistung;
- ein **Protokoll** der letzten Entscheidungen (nur Änderungen werden notiert);
- ein **Vergleich mit der Wirklichkeit** je Tag (60 Tage aufgehoben), wenn Sie die Entität *lädt gerade* und/oder den *Energiezähler der
  Wallbox* eingetragen haben: wie lange Entscheidung und Wallbox übereinstimmten, wie viele Stunden die Wallbox lud, obwohl Plugwhen
  pausiert hätte, und wie viel Energie in diesen Stunden kam, und umgekehrt. Beispiel: *hätte 3 h pausiert, aber 9 kWh kamen an*.

Unbekanntes ist nie eine Entscheidung: unbekannter Ladestand, Auto nicht angesteckt, nichts zu laden, keine Abfahrt ergeben *keine Entscheidung*,
die Wallbox macht weiter, was sie macht. Ein Ziel, das bis zur Abfahrt nicht erreichbar ist, ergibt `laden` sofort (nie warten, wenn die Zeit knapp ist).

Das ist der Beleg, auf dem die Betriebsart „Direkt“ angeboten wird: erst wenn der Vergleich zeigt, dass die Entscheidungen von Plugwhen
mehrere Tage lang richtig gewesen wären (siehe „Bereit zum Schalten?“). Das Dashboard hat eine Karte *Lernmodus* mit der
Entscheidung, dem Vergleich der letzten 7 Tage und dem Protokoll.

## Anonyme Daten teilen (freiwillig) und Rückmeldung

**Aus, solange Sie es nicht einschalten.** Der letzte Schritt der Einrichtung fragt danach, danach der Schalter *Anonyme Daten
teilen* am Gerät der Integration. Solange er an ist, geht an `aiwhatelse.eu`:

| Was | Wann | Inhalt |
|---|---|---|
| Nutzungsstatistik | einmal pro Woche | zufällige Kennung, die jeden Monat wechselt, Versionen, Land und Sprache, grob wie lange Plugwhen schon läuft (0–1, 1–3, 3–6, mehr als 6 Monate), welche Gerätearten und Funktionen genutzt werden, aus welchen Integrationen die Entitäten kommen (z. B. `shelly`); bei einer Wallbox in der Betriebsart *Direkt* ihre Integration, Modell und Firmware, wie viele Befehle sie bekam, der Anteil, der nicht binnen 2 Minuten übernommen wurde, und die Zeit, bis sie den neuen Wert zeigte (Median, 95. Perzentil) |
| Fahrtage | einmal am Tag | je Tag mit mindestens 30 km: Automodell (Hersteller und Modell des Geräts mit dem Ladestand), Akkugröße, Kilometer, Verbrauch je km, mittlere Außentemperatur des Tages, Kilometerstand nur auf 10.000 km genau |
| Ladetage | einmal am Tag | je Tag, an dem nur zu Hause geladen wurde (mindestens 3 kWh und 20 % Ladestand): Automodell, Akkugröße, Wallbox-Energie je voller Ladung, mittlere Außentemperatur, Kilometerstand auf 10.000 km genau. Daraus folgen Ladeverluste und die Alterung des Akkus |
| Standtage | einmal am Tag | je ganzem Tag, an dem das Auto stand und nicht geladen wurde: Automodell, Akkugröße, Abfall des Ladestands in % (auf 0,5 genau), mittlere Außentemperatur. Daraus folgt der Verlust im Stand |

**Nie gesendet:** Namen, Entitäts-IDs, Adressen, Standort, Datum oder Uhrzeit einer Fahrt, Kennwörter, Token. Es wird keine
IP-Adresse gespeichert. Die Fahrtage haben keine Kennung und werden gemischt, sie lassen sich keinem Auto zuordnen und daher
auch nicht löschen. Beim Ausschalten wird das Löschen der Nutzungsstatistik jeder noch gemerkten Kennung angefordert (dieser
und voriger Monat), und Plugwhen vergisst die Flottenwerte. Der Dienst löscht die Nutzungsstatistik ohnehin nach 60 Tagen.

**Wofür:** Verbrauchswerte je Automodell (siehe unten), sehen, welche Geräte gut funktionieren, veröffentlichte
Zusammenfassungen und Zusammenfassungen, die an Forschung oder Partner weitergegeben werden. Immer aus mindestens 10
Installationen, nie einzelne Autos oder Haushalte.

**Was Sie davon haben:** Solange Ihr Auto noch keine eigenen Werte hat, rechnet Plugwhen mit dem Verbrauch vieler gleicher Autos
(ab 5 Autos eines Modells, sonst aller Autos), bei Kälte und Wärme. Reihenfolge: eigene Kurve, eigenes Modell, alle Autos,
Startwerte. Das Attribut `fleet` am Sensor *Gelernte Tage* zeigt, was verwendet wird.

**Rückmeldung.** In das Textfeld *Rückmeldung* am Gerät der Integration schreiben und *Rückmeldung senden* drücken, oder die
Aktion `send_feedback` (längere Texte, optional eine Kontaktadresse, mit oder ohne die Übersicht der Einrichtung oben). Sie geht
an den Autor, sonst wird nichts gesendet.

**Fehlerbericht (ab 0.9.1).** Läuft etwas nicht wie erwartet, *Fehlerbericht senden* drücken (ein Text im Feld *Rückmeldung*
geht mit, ist aber nicht nötig). Er enthält je Auto Betriebsart, Ladestand, Ziel, Plan, Entscheidung, die letzten Aktionen an der
Wallbox, wie schnell und verlässlich ihre Einstellungen antworten, ob die Sensoren Werte liefern, und die letzten Warnungen. Namen,
Entitäts-IDs, Adressen und Uhrzeiten sind entfernt. Danach zeigt eine Benachrichtigung genau, was gesendet wurde. Unabhängig von
*Anonyme Daten teilen*.

## Grenzen

Gesteuert wird nur in den Betriebsarten „Über evcc“ und „Direkt“; im Standard „Lernen“ schaltet Plugwhen nichts. Der Plan beruht auf Gewohnheiten und Prognosen, er ist keine
Garantie. Schnellladen unterwegs wird nicht geplant, nur erkannt (der Ladestand steigt, ohne dass der Wallbox-Zähler zählt).
