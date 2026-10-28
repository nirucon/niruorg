# NIRUORG — agent-roadmap och arbetsinstruktioner

Du arbetar i NIRUORG-repot:

```text
~/Nextcloud/Projects-Dev/niruorg/niruorg-git
```

Läs hela denna fil innan du ändrar kod. Målet är en **minimalistisk men mycket
kapabel filhanterare** med säker filhantering, bra Nextcloud-stöd och ett
NIRUX-tema som känns som en del av skrivbordet.

Utgångsläge: **NIRUORG 0.4.0**, Python + PySide6, 51/51 regressionstester
gröna vid skrivandet. Behåll den nivån.

---

## 1. Uppdrag

Förbättra NIRUORG i denna ordning:

1. **Stabilitet och dataintegritet**
2. **Inga frysta UI-trådar**
3. **NIRUX-tema och NIRUX-ux**
4. **Nextcloud-delning och synkstatus**
5. **Filhanterarfunktioner som används dagligen**
6. **Arkitektur och releasekvalitet**

Lägg inte till funktioner bara för att de finns i andra filhanterare. Varje
funktion ska lösa ett verkligt arbetsflöde och rymmas i den minimalistiska
ytan.

---

## 2. Absoluta regler

- **Förstå först, ändra sedan.** Läs berörd kod och befintliga tester innan du
  redigerar.
- **Gör inte en stor omskrivning av `niruorg/app.py`.** Dela upp i små,
  testade steg.
- **En fas per branch/commit/PR.** Blanda inte tema, Nextcloud och
  refaktorering i samma ändring.
- **Rör inte användarens data, inställningar eller mounts** under test.
  Använd tillfälliga testfiler.
- **Kör aldrig `git reset --hard`, `git clean -fd`, force-push eller
  destruktiva dataoperationer** utan uttryckligt godkännande.
- **Committa aldrig hemligheter**: app-lösenord, tokens, SSH-nycklar,
  rclone-konfiguration, verkliga serveruppgifter eller användarloggar.
- **Inga shell-strängar med användardata.** Använd argv-listor.
- **Ingen nätverksåtkomst i enhetstester.** Mocka HTTP och `secret-tool`.
- **Remote/FUSE-testning sker bara med utbytbara testfiler**, aldrig med
  produktionsdata.
- **Behåll Python 3.12-kompatibilitet** (CI använder 3.12).
- **Ändra inte språk, teman eller beteenden utanför uppgiften** utan att fråga.
- **Uppdatera tester och dokumentation** när beteendet ändras.
- **Varje ny `*-test.py` ska registreras i `regression-suite.py`.**
- **Kör alltid relevant testnivå innan du säger att något är klart.**
- **Om något är oklart: stanna och fråga** i stället för att gissa.

Det finns för närvarande 69 mode-only-ändringar i arbetskatalogen. De ska inte
blandas in i funktionscommits. Normalisera filrättigheter separat om det
behövs.

---

## 3. Definition av klar

En ändring är klar först när:

- [ ] `python3 -m compileall -q niruorg` lyckas.
- [ ] `python3 regression-suite.py --non-qt` lyckas.
- [ ] `QT_QPA_PLATFORM=offscreen python3 regression-suite.py` lyckas.
- [ ] `python3 niruorg/app.py --self-test` lyckas.
- [ ] `QT_QPA_PLATFORM=offscreen python3 gui-smoke-test.py` lyckas.
- [ ] Berörda funktioner har nya eller uppdaterade regressionstester.
- [ ] Ingen UI-operation kan blockera huvudtråden i mer än trivial tid.
- [ ] Inga hemligheter eller användardata har hamnat i git eller loggar.
- [ ] Dokumentation/CHANGELOG är uppdaterad om användaren märker ändringen.
- [ ] `git diff` innehåller bara avsedda ändringar.

Vid remote-ändringar krävs dessutom manuell test enligt
`docs/TESTING.md`, med utbytbara filer.

---

## 4. Prioriterade faser

### Fas 0 — Baseline och kända fel

**Mål:** grön baseline och rätta uppenbara fel utan att ändra beteende i övrigt.

Uppgifter:

1. Kör hela testsviten och spara resultatet.
2. Rätta split-view-buggen:
   - `niruorg/app.py` använder `self.settings` i
     `_remember_split_sizes()` och `_restore_split_sizes()`.
   - Appen har `self.s`, inte `self.settings`.
   - Byt till `self.s` och lägg till ett regressionstest som drar i
     splittern samt öppnar/stänger högerpanelen.
3. Inventera kvarvarande blockerande operationer i GUI-tråden. Ändra inte
   dem i denna fas; skriv en kort lista i commitmeddelandet eller docs.
4. Normalisera eventuella mode-only-ändringar i en separat commit om ägaren
   godkänner det.

**Klart när:** alla tester är gröna och split-view fungerar utan traceback.

---

### Fas 1 — Ingen blockerande I/O i UI-tråden

**Mål:** appen ska förbli responsiv även när nätverk, FUSE, stora filer eller
externa program är långsamma.

Prioriterade kodvägar:

- `nextcloud_share()` och `_nextcloud_request()` — HTTP.
- `update_quicklook()` — `lstat`, bildladdning, text och `ffprobe`.
- `compress()` och `checksum()` — stora filer.
- `open_cloud()` — `rclone mount` och vänteloop.
- `preview()` — stora filer, arkiv och media.
- Bulk rename — metadata och namnkonflikter.
- Eventuella kvarvarande `subprocess.run()` som kan ta mer än några
  millisekunder.

Rekommenderad lösning:

- Inför en gemensam liten worker-modell eller återanvänd befintliga
  `QRunnable`/`WorkerSignals`.
- Alla operationer ska ha:
  - tydlig början och slut
  - felmeddelande till användaren
  - rimlig timeout
  - möjlighet att avbryta där det är relevant
  - skyddad referenshållning till Qt-objekt
- Quick Look ska debounce:a snabba urval och cacha per
  `(path, mtime, size)`.
- Nätverksanrop får aldrig köras i GUI-tråden.

**Klart när:** man kan byta markering, öppna dialoger och avbryta operationer
medan en långsam operation pågår.

---

### Fas 2 — NIRUX-tema och NIRUX-ux

**Mål:** NIRUORG ska automatiskt följa NIRUX-sviten och kännas som en native
del av skrivbordet.

Läs källor i denna ordning:

1. `~/.config/niruwm/appearance.toml`
   - `[colors]` om användaren har overrides
   - `[font]`, `[spacing]`, `[focus]`, `[motion]`
2. `niructl theme-catalog --json`
   - `active`
   - `themes[].colors`
   - `appearance_overrides`
3. `~/.config/nirux/theme/kitty.conf`
   - genererad fallback med ANSI-färger
4. `Niru Noir`
   - sista reserv

Lägg till valet **`Follow NIRUX`**. Det ska vara standard när NIRUX upptäcks,
men `Follow Omarchy`, de fasta temana och ett korrekt `System`-läge ska finnas
kvar.

Mappning:

| NIRUORG | NIRUX |
|---|---|
| `bg` | `background` |
| `fg` | `foreground` |
| `muted` | `muted` |
| `border` | `border` |
| `accent` | `focus` / `accent` |
| `panel` | `surface`, annars blandning av bg/fg |
| `surface` | `surface`, annars blandning av bg/fg |
| `sel` | `selected`, annars blandning av bg/accent |
| `danger` | `error`, annars temats röda |
| `accentfg` | kontrastfärg mot accent |

Krav:

- Använd `tomllib` för TOML.
- Härledda färger ska ha tillräcklig kontrast, även för ljusa teman som
  Carl Larsson.
- Läs gärna `font.size`, `spacing.padding` och `focus.width`, men ändra inte
  layouten drastiskt utan visuell granskning.
- Lyssna på:
  - `~/.config/niruwm/config.toml`
  - `~/.config/niruwm/appearance.toml`
  - `~/.config/nirux/theme/kitty.conf`
- Använd `QFileSystemWatcher` med debounce. Lägg till filen igen efter
  atomiska filbyten.
- När temat ändras ska färger, ikoner och eventuell font uppdateras utan
  omstart.
- `niructl` får inte anropas i GUI-tråden. Läs filer eller kör i worker och
  cacha resultatet.
- Lägg till tester för:
  - aktivt mörkt tema
  - ljust tema
  - `[colors]`-overrides
  - trasig eller saknad fil
  - fallback till Niru Noir
  - temabyte via watcher

**Klart när:** NIRUX-temabyte syns direkt i NIRUORG och appen fortfarande
fungerar med Omarchy som fallback.

---

### Fas 3 — Nextcloud

**Mål:** säker, förutsägbar och användbar Nextcloud-integration utan att
NIRUORG blir en synkklient.

Nuvarande grund:

- app-lösenord i Secret Service
- OCS-baserad publik delningslänk
- endast ett objekt och endast under `~/Nextcloud`

Förbättringar:

1. Bryt ut Nextcloud till en egen modul, exempelvis
   `niruorg/services/nextcloud.py`.
2. Alla HTTP-anrop ska gå via worker och ha timeout samt tydliga fel.
3. Behåll publik länk som standard med **minsta möjliga behörighet**.
4. Lägg till rimliga val:
   - publik länk
   - utgångsdatum
   - lösenordsskydd
   - läsbar/skrivbar behörighet
   - kopiera länk
   - ta bort delning
5. Stöd flera markerade objekt där det är säkert och begripligt.
6. Logga aldrig app-lösenord, tokens eller fullständiga HTTP-svar med
   känslig information.
7. Synkstatus:
   - kontostatus via Nextcloud-klientens D-Bus är OK
   - lokal sync-databas är intern och låst; använd endast som best-effort
   - visa `unknown` hellre än felaktig status
   - använd aldrig syncstatus som grund för destruktiva beslut
8. Om exakt per-fil-status krävs: dokumentera att Nemo/Nautilus med
   `nemo-nextcloud`/`nautilus-nextcloud` är den robusta lösningen. Bygg inte
   en egen synkmotor.

**Klart när:** delning fungerar utan UI-blockering, med tydliga fel och utan
hemligheter i git/loggar.

---

### Fas 4 — Filhanterarfunktioner

**Mål:** de dagliga arbetsflödena ska kännas snabba och förutsägbara.

Prioriterat:

1. **Lokal automatisk uppdatering**
   - `QFileSystemWatcher` för lokala, synliga kataloger.
   - Debounce.
   - Inga watchers på FUSE/SSHFS.
2. **Bulk rename**
   - Förkontrollera alla mål.
   - Avbryt före första ändringen vid konflikt.
   - Tydlig förhandsgranskning.
   - Rollback där det är möjligt.
3. **Quick Look**
   - Debounce.
   - Cache.
   - Asynkron media-metadata.
4. **Statusrad**
   - antal objekt
   - markerad storlek
   - ledigt utrymme
   - endpoint/remote
   - transferstatus
   - eventuell Nextcloud-status
5. **Ikoner**
   - cacha `SemanticIconProvider`-ikoner per typ och palett.
   - Behåll den minimalistiska stilen; undvik ett stort ikonbibliotek.
6. **Tillgänglighet**
   - tydlig fokusmarkering
   - fungerande Escape/Enter överallt
   - skärmläsarvänliga namn där Qt tillåter.

**Klart när:** lokala filändringar syns automatiskt och bulk rename inte kan
lämna en halvfärdig namnserie.

---

### Fas 5 — Arkitektur och prestanda

**Mål:** göra appen lättare att underhålla utan att ändra beteende.

Dela gradvis upp `niruorg/app.py`:

```text
niruorg/
  ui/
    main_window.py
    pane.py
    dialogs/
  core/
    transfer.py
    rename.py
    search.py
    paths.py
  services/
    theme.py
    nextcloud.py
    remotes.py
  utils/
    logging.py
    workers.py
```

Regler:

- En modul i taget.
- Inga beteendeändringar i samma commit.
- Flytta tester eller lägg till kontraktstester.
- `app.py` får bli mindre, men publik CLI/installationsstart ska fungera
  oförändrat.
- Inför central fel-loggning med användarvänliga meddelanden och teknisk
  detalj på annan nivå.
- Ersätt breda `except Exception: pass` stegvis, inte med risk för regression.

**Klart när:** ansvarsområden är tydliga och testsviten fortsatt är grön.

---

### Fas 6 — Release

**Mål:** en säker release utan överraskningar.

- Uppdatera `VERSION`, `README.md`, `CHANGELOG.md` och `RELEASE_NOTES.md`.
- Verifiera `install.sh` och `rollback.sh` i staging.
- Kör alla tester samt manuell lokal acceptans.
- Kontrollera att inga hemligheter eller stora ZIP-filer finns i git.
- Tagga först efter grön CI.
- Publicera release-ZIP som separat asset; committa inte in den.
- Ingen force-push och inga överskrivna taggar.

---

## 5. Minimalistisk UX-princip

Lägg hellre funktioner i:

- kommandopaletten
- högerklicksmenyn
- en diskret statusrad
- en valfri Quick Look-panel

än i en ny permanent verktygsrad.

NIRUORG ska kännas lugn och snabb. “Minimalistisk” betyder inte “få
funktioner”; det betyder att funktionerna finns där de behövs och inte tar
plats när de inte används.

---

## 6. Testmatris

Kör minst:

```bash
cd ~/Nextcloud/Projects-Dev/niruorg/niruorg-git

python3 -m compileall -q niruorg
python3 regression-suite.py --non-qt
QT_QPA_PLATFORM=offscreen python3 regression-suite.py
python3 niruorg/app.py --self-test
QT_QPA_PLATFORM=offscreen python3 gui-smoke-test.py
```

Vid ändringar i filoperationer:

```bash
python3 transfer-integrity-030-test.py
```

Vid ändringar i tema:

- testa `Niru Forest Vigil` (mörkt)
- testa `Niru Carl Larsson` (ljust)
- testa saknad/trasig konfiguration
- testa live byte av tema

Vid ändringar i Nextcloud:

- mocka OCS-svar
- testa 401, timeout, nätverksfel och saknad app-password
- testa att ingen hemlighet hamnar i logg eller QSettings
- kör inte mot riktig server i CI

Vid ändringar i remote/FUSE:

- använd endast utbytbara testfiler
- verifiera att UI förblir responsivt
- verifiera att owned mounts städas korrekt

---

## 7. Arbetsflöde för agenten

1. Läs `AGENTS.md`, `README.md`, `docs/ARCHITECTURE.md`,
   `docs/TESTING.md` och berörd kod.
2. Kontrollera `git status` och rör inte befintliga orelaterade ändringar.
3. Välj **en** fas och en avgränsad uppgift.
4. Skapa en branch med beskrivande namn.
5. Implementera minsta möjliga ändring.
6. Lägg till eller uppdatera tester.
7. Kör testmatrisen.
8. Granska `git diff` själv.
9. Committa med tydligt meddelande.
10. Rapportera vad som är gjort, testresultat och kvarvarande risker.

Rekommenderade commit-prefix:

```text
fix: ...
perf: ...
feat: ...
test: ...
docs: ...
refactor: ...
```

---

## 8. Stoppvillkor

Stanna och fråga om:

- en ändring kräver att användardata flyttas eller raderas
- en testning kräver riktig server, riktiga nycklar eller produktionsdata
- en refaktorering kräver att stora delar av `app.py` skrivs om
- en ny dependency behövs
- en ändring påverkar installer/rollback eller användarens inställningar
- det finns orelaterade lokala ändringar som riskerar att komma med i commit

---

## 9. Startprompt för nästa agent

Kopiera gärna detta som första instruktion:

```text
Läs AGENTS.md och följ den. Börja med Fas 0: kör baseline-testerna, rätta
self.settings-buggen i split-view och lägg till ett regressionstest. Gör inga
andra beteendeändringar i samma commit. Rapportera testresultat och exakt vad
som ändrades. Om arbetskatalogen har orelaterade ändringar, lämna dem orörda.
```

När Fas 0 är grön är nästa steg **Fas 1: avlasta all långsam I/O från
GUI-tråden**, därefter **Fas 2: Follow NIRUX**.
