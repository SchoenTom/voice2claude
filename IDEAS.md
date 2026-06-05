# voice2claude — Ideen-Dossier

*Synthese aus 7 unabhängigen kreativen Linsen (Erste-Prinzipien-Philosoph,
Multi-Agent-Dirigent, Ambient/Calm, Voice-Interface, Hardware-Remix,
Delight/Persönlichkeit, Pragmatischer Editor). Jede sollte recherchieren,
philosophieren und neu erfinden — und sie konvergierten verblüffend.*

## 🌟 Der Nordstern (die Neudefinition)

Sieben Denker, eine Erkenntnis: voice2claude ist kein „Handy-Keyboard".
Es ist der **Kontrollturm / das Cockpit für eine Flotte autonomer Agenten.**
Autonome Coding-Agenten machen aus dem Menschen vom *Tipper* einen
**Dirigenten**. Sie arbeiten Minuten allein und brauchen dann eine
Entscheidung. Der Engpass ist **nicht mehr Tippen — sondern Aufmerksamkeit
und Urteil, verteilt über viele Agenten.** Das Handy ist kein schlechteres
Keyboard, sondern ein *anderes Organ*: immer in der Hand, ambient, ortsfrei.

> Die eine Aufgabe: **die Latenz zwischen „Agent braucht mich" und „Mensch hat
> entschieden" auf nahe Null bringen.** Alles andere ist Dekoration.

---

## 🏆 TIER 1 — Der Durchbruch: der Aufmerksamkeits-Layer

**Von allen 7 Linsen unabhängig gefunden** (Attention Badge · The Strip ·
Triage Feed · Approval Queue · Gravity · Heartbeat Wall). Das ist *das* Feature,
das verändert, was voice2claude IST.

- **Attention Badge — „Wer braucht mich?"** Pro Session ein Status: läuft /
  wartet / blockiert. Erkennung: letzte N Zeilen der Session lesen +
  Regex auf Claude-Code-Prompts (`Do you want`, `(y/n)`, `❯`, `esc to
  interrupt`, `Permission`). Punkt-Farbe pro Session-Karte. **S5 V5.**
- **Peek — letztes Output** Tap → die letzten ~25 Zeilen als Snapshot (kein
  Stream). „Triagieren ohne hinlaufen." **S4 V4.**
- **Approval Queue / „The Strip"** Eine Ansicht ALLER wartenden Agenten,
  nach Dringlichkeit. Du löst sie wie eine Warteschlange: *erscheinen →
  entscheiden → weg → nächster.* Aus „Supervisor" wird „Resolver". **S4 V5.**

**Minimaler Bauplan (≈100 Zeilen, keine neuen Deps):** `/agents`-Endpoint
iteriert die Sessions, liest je Fenster den sichtbaren Text (System-Events
Terminal-Inhalt / tmux capture), 5 Regex → `{id, state, snippet}`. Frontend:
farbiger Punkt auf jeder Session-Karte (Polling 4 s) + Tap = Peek-Modal +
eine „Wartet (N)"-Queue-Ansicht.

---

## 🎙️ TIER 2 — Stimme als Kommando (nicht nur Diktat)

Aus Voice- + Philosoph-Linse. Macht aus Diktat eine **Kommandobrücke** —
billig auf diesem Stack (Post-Transkriptions-Parsing + macOS `say`).

- **Callsign-Adressierung** Jede Session bekommt ein 2-Silben-Rufzeichen
  („Backend", „Frontend"); „**Backend**, lass die Tests laufen" routet ans
  richtige Fenster. **S4 V5.**
- **Read-Back-Gate** Vor dem Senden liest `say` das Transkript vor; „affirm"
  sendet, „negate" verwirft, 2 s Stille = senden. Löst das Vertrauensproblem
  bei riskanten Befehlen — wie ATC-Readback. **S3 V5.**
- **Phonetische Bestätiger** „affirm"=y/Enter, „negate"=n/Esc, „abort"=Ctrl-C.
  Reiner Keyword-Map. **S5 V4.**
- **SITREP** „Backend, Lage" → letzte Zeilen lokal zusammenfassen + vorlesen.
  Status-Burst per Funk. **S3 V5.**
- **Verb-Grammatik** Imperative („stop", „revert", „broadcast") werden als
  *Aktion* erkannt statt als Prosa eingefügt. **S3 V5.**

---

## 💗 TIER 3 — Präsenz & Persönlichkeit (macht es geliebt)

Aus Delight-Linse: Agenten als *„Menschen im Nebenzimmer"*, nicht Zeilen in
einer Liste. Nahezu Null Kosten, große Wirkung.

- **Heartbeat-Glow** Jeder Orb pulsiert im Arbeitsrhythmus der Session
  (schnell=tief im Loop, langsame Atmung=wartet). **S4 V5.**
- **Name-Voice** Wenn ein Agent fertig ist, sagt das Handy seinen Titel:
  „Refactor fertig." Keine Klingel — eine Ansage von jemandem. **S3 V5.**
- **Last-Word** Letzter Satz des Agenten als Flüstern unter dem Orb. **S4 V5.**
- **Earned Silence** Nach dem Senden dimmt das UI + „coast"-Animation — du
  bist *entlassen*, nicht am Beobachten. **S5 V5.**
- **Session-Temperament** „methodisch / gesprächig / unsicher" aus dem
  Verhalten — du kennst den Arbeitsstil, bevor du reingehst. **S3 V4.**

---

## 🎛️ TIER 4 — Ergonomie der Entscheidung (Hardware-Remix)

- **Radial-Entscheidungsrad** 🏆(Hardware-Durchbruch): Wartet ein Agent,
  erscheint ein Daumen-Radial mit den wahrscheinlichen Antworten (y/n/1/2/3,
  aus der letzten Zeile geparst). Ein Flick — kein Lesen. Baut Muskelgedächtnis.
  **S3 V5.**
- **Edge-Rail** Long-press rechte Kante → Streifen (Enter/Esc/y/n/Stop) genau
  unterm Daumen, ohne hinzusehen. **S5 V4.**
- **Session-Skins** Pro Session ein eigenes Tastenprofil (Stream-Deck-Idee). **S4 V4.**
- **Ritual-Send** Halten = Orb atmet ein, loslassen = senden (Wurf-Metapher). **S4 V5.**
- **PTT-Broadcast mit Kanalwahl** Halten + sprechen, vor dem Loslassen
  Empfänger-Sessions wählen. **S3 V5.**

---

## 🌙 TIER 5 — Ambient / Calm (ehrlich zu iOS-Grenzen)

- **Gravity / gewichtete Signale** Entscheidungs-„Masse" (Datei-Umfang,
  Irreversibilität) → unterschiedlich starke Signale. Kein Alarm-Abstumpfen. **S3 V5.**
- **Cold Shoulder** Nur Abweichung vom Normalrhythmus meldet sich; Stille = „alles ok". **S4 V3.**
- **Constellation View** Sternenkarte statt Liste: Punkt = Agent, Helligkeit =
  Aktivität; räumliches Gedächtnis schlägt Listen. **S3 V5.**
- *iOS-Realität:* kein Web-Push ohne installierte PWA, kein Hintergrund-Mikro,
  keine Web-Haptik. Brücke = installierte PWA / Apple-Shortcuts / (optional) Watch.

---

## 🚀 Moonshots (klingen unmöglich, sind es vielleicht nicht)

- **Dead-Drop / Vorab-Freigabe** Stehende Befehle: „Wenn gefragt wird, ob das
  Schema überschrieben werden soll → ja." Proxy fängt bekannte Prompt-Muster ab
  und antwortet. **V5**, fragil.
- **Shift-Handoff-Report** Du warst 90 min weg → strukturierter Bericht beim
  Öffnen: was 12 Agenten taten/entschieden/brachen (git diff + Logs + lokale
  Zusammenfassung). „Briefing der Crew, die arbeitete, während du weg warst." **V5.**
- **Dead-Man's-Switch** Wartet ein Agent zu lange UND das Handy ist unberührt →
  konfigurierte Default-Antwort, damit nie ein Agent ewig hängt. **S4 V5.**
- **Barge-In** Während `say`/Agent läuft: ein gesprochenes „stop" feuert Esc/Ctrl-C
  (Wake-Word-Schicht — schwerster Teil). **V5.**
- **Whisper-Brief** Beim Entsperren liest dir das Handy in einem Satz die
  Flotten-Lage vor, bevor du hinschaust. **V5.**

---

## 🧱 Fallen (bewusst NICHT bauen)

1. **Natives Web-Push auf iOS** — nur mit installierter PWA + Service Worker;
   ein Safari-Hintergrund-Kill killt das Modell. → Poll-on-Foreground / Shortcuts.
2. **Echtzeit-Terminal-Streaming (PTY/WebSocket)** — Dauer-CPU, bricht bei
   Fokusverlust, iOS killt Sockets. → **Peek-Snapshots** (90 % Wert, 5 % Kosten).
3. **Native Apple-Watch-App** — Xcode/WatchKit-Overkill. → Shortcuts +
   URL-Scheme decken „Trigger vom Handgelenk" gratis ab.
4. **LLM-Klassifikation des Terminal-Outputs** — langsam/teuer/fragil. →
   5 Regex auf die echten Claude-CLI-Prompt-Muster sind schneller & robuster.

---

## ➡️ Empfohlene Reihenfolge (CEO)

1. **Aufmerksamkeits-Layer** (Tier 1) — Badge + Peek + Queue. *Der Sprung von
   „Remote-Keyboard" zu „Kontrollturm". Höchste Hebelwirkung, ~100 Zeilen.*
2. **Voice-Kommandos** (Tier 2) — Callsign + phonetische Bestätiger + Read-Back.
   *Macht die Brücke vertrauenswürdig & freihändig.*
3. **Präsenz-Layer** (Tier 3) — Heartbeat-Glow + Name-Voice + Earned Silence.
   *Macht es geliebt, fast gratis.*
4. Danach selektiv: Radial-Rad, Constellation, ein Moonshot (Shift-Report).
