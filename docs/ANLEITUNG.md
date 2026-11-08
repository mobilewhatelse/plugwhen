# Plugwhen – Anleitung (Deutsch)

Stand: Version 0.7.0 (in Entwicklung). Plugwhen **plant und zeigt an**, es steuert die Wallbox noch nicht.

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

1. Integration hinzufügen: Einstellungen → Geräte & Dienste → Integration hinzufügen → **Plugwhen**.
2. Auf der Integrationsseite **Fahrzeug hinzufügen** und die Entitäten oben eintragen.
3. Optional über das Zahnrad: den **Viertelstunden-Wächter** wählen (wird vorgeschlagen, wenn er installiert ist), Solarprognose an/aus und Abzug,
   Verfügbarkeits-Sensor, Energiezähler Netzbezug und Leistungspreise für den Potenzialrechner.
4. Dashboard erstellen (siehe unten).

## Wie geplant wird

1. **Bedarf:** Die Reserve ist die Untergrenze der Reichweite bei der Abfahrt. Ist *Kilometer je Wochentag lernen* an, hebt der gelernte hohe Wert
   eines Wochentags sie bei Bedarf an. Daraus folgen Ziel-Ladestand und Energie (mit Ladeverlusten).
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

## Steckzeiten

Home Assistant hebt den Verlauf eines Stecker-Sensors nur wenige Tage auf, Binärsensoren haben keine Langzeitstatistik. Plugwhen schreibt An- und
Abstecken deshalb selbst mit (etwa ein Jahr; beim ersten Start übernimmt es, was der Recorder noch hat). Der Sensor *Bereit zur Abfahrt* zeigt im
Attribut `plugging`: wie oft und wie viele Nächte in vier Wochen angesteckt, typische Ansteck- und Abziehzeit.

**Niemand muss täglich anstecken.** Stecken Sie an wie gewohnt; „Bitte anstecken“ kommt nur, wenn die Reserve bis zur nächsten Abfahrt nicht reicht.

## Die Warnung

*Bereit zur Abfahrt* ist `ready` oder sagt, was zu tun ist: `plug_in` (anstecken), `low` (Steckerzustand unbekannt, zu wenig), `too_late` (auch mit
voller Leistung reicht die Zeit nicht), `not_reachable` (Ziel mit dem Akku nicht erreichbar), `unknown` (kein frischer Ladestand). Ab einer
gewählten Abendstunde, einmal je Abfahrt und Art, an alle eingetragenen Dienste. Texte auf Deutsch und Englisch.

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
Urteil: *lohnt sich*, *Wallbox-Einstellung reicht* (die eigene Funktion der Wallbox schafft fast dasselbe, ohne die Abfahrt zu verpassen), *gering*
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

## Zusammen mit dem Viertelstunden-Wächter

Beide laufen auch allein. Es genügt, die andere Integration in den Einstellungen zu wählen, Entitäten müssen nicht ausgesucht werden:

- Plugwhen liest die **Last-Prognose** des Wächters (erwarteter Bezug, Spitzenziel), seinen Zähler, die Preise und die Grenze.
- Der Wächter liest die **Ladepläne** von Plugwhen (Attribut `windows`) in seine Prognose ein und zeigt sie ab Version 0.14 in seinem Dashboard
  statt seines eigenen Plans. Den eigenen Ladeplan des Wächters dann ausschalten, damit nicht zwei Pläne nebeneinander stehen.
- **Der Wächter hat immer das letzte Wort:** Käme trotzdem eine Spitze, drosselt er wie gewohnt. Plugwhen vergleicht, was wirklich angekommen
  ist, mit dem Plan und verteilt den Rest neu.

## Dashboard

Der Dienst **Dashboard erstellen** (`plugwhen.create_dashboard`, nur Administratoren) baut das Dashboard mit den Entitäten **Ihrer** Installation,
für alle Fahrzeuge, auf Deutsch oder Englisch und in Ihrer Währung: nächste Abfahrt, Ladeplan (woher der Strom kommt), Potenzial mit
Vergleichstabelle, Steckzeiten, Einstellungen und gelernte Woche. Nur Standardkarten.

**So geht's:** Entwicklerwerkzeuge → Aktionen → *Dashboard erstellen* ausführen, das YAML aus der Antwort oder der Benachrichtigung kopieren.
Dann Einstellungen → Dashboards → Dashboard hinzufügen, öffnen, drei Punkte → Bearbeiten → drei Punkte → Roher Konfigurationseditor, einfügen,
speichern. Der Dienst **schreibt nie in ein bestehendes Dashboard**. Nach dem Hinzufügen eines Fahrzeugs neu erstellen.

## Ehrliche Zahlen: was gelernt statt gesetzt wird

Jede Zahl, die vom Haus oder vom Auto abhängt, hat eine Vorgabe, die überall funktioniert, und Plugwhen ersetzt sie durch einen gelernten Wert,
sobald genug Daten da sind (täglich im Hintergrund; das Dashboard sagt, welcher gerade gilt):

| Zahl | Vorgabe | Gelernt aus |
|---|---|---|
| Abfahrt, auf die der Plan zielt | gelernte mittlere Stunde | die **frühe** Abfahrt (20. Perzentil der ersten Fahrten des Wochentags): ein Auto, das zur mittleren Abfahrt fertig ist, ist an etwa der Hälfte der frühen Tage zu spät |
| bevorzugte kleinste Ladeleistung | 4 kW (Einstellung je Auto) | der Plan verteilt nicht flacher; der Lader im Auto hat unter wenigen kW höhere Verluste; bis zum Minimum nur, wenn die Energie sonst nicht passt |
| Ladeverluste | 10 % | Tage mit Laden nur zu Hause: Anstieg des Ladestands × Akkugröße gegen die Wallbox-Energie (begrenzt auf 2 bis 25 %) |
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
  Abfahrt kommt: Sonne im selben Fenster (gelb), mit Sonne vorgeladen (orange), Netz (blau).
- **Eine Vorwarnung am Vorabend:** Ab der Abendstunde der Warnung sagt Plugwhen, dass **morgen** geladen werden muss (mit dem spätesten Start) oder
  dass sich morgen das Vorladen mit Sonne lohnt. Einmal je Tag und Art. Laden, das heute geschehen muss, ist Sache der Anstecken-Warnung.
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

Urteil: **Lernen hilft** (mindestens 5 Prozentpunkte mehr Tage gedeckt), **Lernen hilft bei der Abfahrt** (die Kilometer helfen kaum, aber der frühe
Plan ist an mindestens 10 Punkten mehr Tagen rechtzeitig fertig als der mittlere), **Reserve reicht** (weniger als 2 Punkte: die Reserve allein genügt, der
gelernte Wert kostet nichts, bringt aber wenig), **kaum Unterschied** oder **zu wenig Daten** (weniger als 21 Tage prüfbar). Tage ohne Kilometer
zählen nicht. Beim Auto des Autors deckt die Reserve allein etwa 88 % der Tage, mit dem Gelernten etwa 90 %; am meisten hilft der Verlauf bei der
Abfahrtszeit.

Die Karte des Lernmodus hat eine zweite Grafik: je Tag die Stunden, in denen Plan und Wallbox übereinstimmten (grün), und die Stunden, in denen
sie abwichen (rot).

## Lernmodus

Je Auto hat die Auswahl *Betriebsart* heute zwei Stellungen: **Aus** und **Lernen** (Standard; die letzte Wahl bleibt über einen Neustart
erhalten). Im Lernmodus **schaltet Plugwhen nichts**. Es berechnet nur für jeden Moment, was es tun *würde*, und schreibt es auf:

- der Sensor **Würde schalten** sagt `laden`, `pausieren` oder `keine Entscheidung`, mit Grund (im geplanten Fenster, wartet auf das nächste
  Fenster, der Plan ist abgearbeitet, das Ziel ist knapp also so viel wie möglich sofort, Ladestand unbekannt, Auto nicht angesteckt, nichts
  nötig), wann sich die Entscheidung voraussichtlich ändert und mit welcher Leistung;
- ein **Protokoll** der letzten Entscheidungen (nur Änderungen werden notiert);
- ein **Vergleich mit der Wirklichkeit** je Tag (60 Tage aufgehoben), wenn Sie die Entität *lädt gerade* und/oder den *Energiezähler der
  Wallbox* eingetragen haben: wie lange Entscheidung und Wallbox übereinstimmten, wie viele Stunden die Wallbox lud, obwohl Plugwhen
  pausiert hätte, und wie viel Energie in diesen Stunden kam, und umgekehrt. Beispiel: *hätte 3 h pausiert, aber 9 kWh kamen an*.

Unbekanntes ist nie eine Entscheidung: unbekannter Ladestand, Auto nicht angesteckt, nichts zu laden, keine Abfahrt ergeben *keine Entscheidung*,
die Wallbox macht weiter, was sie macht. Ein Ziel, das bis zur Abfahrt nicht erreichbar ist, ergibt `laden` sofort (nie warten, wenn die Zeit knapp ist).

Das ist der Beleg, auf dem das Schalten später angeboten werden kann: erst wenn das Protokoll zeigt, dass die Entscheidungen von Plugwhen
mehrere Tage lang richtig gewesen wären. **Das Schalten selbst ist noch nicht gebaut.** Das Dashboard hat eine Karte *Lernmodus* mit der
Entscheidung, dem Vergleich der letzten 7 Tage und dem Protokoll.

## Grenzen

Plugwhen plant und zeigt an; **das Ausführen (Wallbox steuern) ist noch nicht gebaut**. Der Plan beruht auf Gewohnheiten und Prognosen, er ist keine
Garantie. Schnellladen unterwegs wird nicht geplant, nur erkannt (der Ladestand steigt, ohne dass der Wallbox-Zähler zählt).
