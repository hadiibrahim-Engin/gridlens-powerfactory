"""GridLens Installations-Sonde -- rein lesend.

Beantwortet die offenen PowerFactory-API-Fragen vor der Umsetzung des
Szenario-Runners. Das Skript aendert NICHTS: kein Activate, kein Execute,
kein SetAttribute, kein Loeschen. Es liest und meldet.

Verwendung
----------
1. Diese Datei auf den PowerFactory-Rechner kopieren.
2. Das gewuenschte Projekt und Study Case aktivieren.
3. Ein ComPython im Study Case anlegen und diese Datei als externe Datei
   zuweisen. Ausfuehren.
4. Die gesamte Ausgabe aus dem Output-Fenster kopieren und zurueckgeben.

Es ist voellig in Ordnung, wenn einzelne Abschnitte FEHLT oder FEHLER melden --
genau das ist die gesuchte Information.
"""

import sys


# ---------------------------------------------------------------- Ausgabe

_LINES = []


def emit(app, text=""):
    _LINES.append(text)
    try:
        app.PrintPlain(text)
    except Exception:
        pass


def section(app, title):
    emit(app, "")
    emit(app, "=" * 72)
    emit(app, title)
    emit(app, "=" * 72)


def attempt(app, label, function):
    """Run a probe and report the outcome without ever raising."""
    try:
        value = function()
    except Exception as exc:
        emit(app, "  {:<38} FEHLER  {}: {}".format(
            label, type(exc).__name__, exc))
        return None
    emit(app, "  {:<38} OK      {!r}".format(label, value))
    return value


def describe(obj):
    if obj is None:
        return "None"
    try:
        return "{} '{}'".format(obj.GetClassName(), obj.loc_name)
    except Exception:
        return repr(obj)


# ------------------------------------------------------- Attributsondierung

def read_attribute(obj, name):
    """Try every route PowerFactory offers to read one attribute."""
    for route in ("GetAttribute", "getattr"):
        try:
            if route == "GetAttribute":
                return route, obj.GetAttribute(name)
            return route, getattr(obj, name)
        except Exception:
            continue
    return None, None


def probe_attributes(app, obj, candidates, label):
    """Report which candidate attribute names actually exist on obj."""
    emit(app, "")
    emit(app, "  Attributsondierung {} ({})".format(label, describe(obj)))
    if obj is None:
        emit(app, "    Objekt nicht vorhanden -- uebersprungen.")
        return {}

    # Route 1: a build that exposes the full attribute list directly.
    for method in ("GetAttributes", "GetAttributeNames"):
        try:
            listing = getattr(obj, method)()
        except Exception:
            continue
        emit(app, "    {}() vorhanden -> {} Eintraege".format(
            method, len(listing)))
        try:
            interesting = sorted(
                name for name in listing
                if any(token in str(name).lower()
                       for token in ("res", "result", "time", "acti", "stage"))
            )
            emit(app, "    davon relevant: {}".format(interesting))
        except Exception:
            emit(app, "    Liste nicht iterierbar: {!r}".format(listing))
        break
    else:
        emit(app, "    Weder GetAttributes() noch GetAttributeNames() vorhanden.")

    # Route 2: probe the candidate names one by one.
    found = {}
    for name in candidates:
        route, value = read_attribute(obj, name)
        if route is None:
            continue
        found[name] = value
        emit(app, "    {:<16} via {:<13} -> {} | typ {}".format(
            name, route, describe(value) if hasattr(value, "GetClassName")
            else repr(value), type(value).__name__))
    if not found:
        emit(app, "    Kein Kandidat aufgeloest.")
    return found


# ------------------------------------------------------------------ Sonden

RESULT_ATTRIBUTE_CANDIDATES = (
    "p_resvar", "p_result", "p_res", "pResult", "presult", "p_resvar2",
    "results", "resultobj", "p_resbuf", "c_resvar", "p_resvarqds",
)

STAGE_TIME_CANDIDATES = (
    "tAcTime", "tacttime", "t_act", "iSchemeStatus", "cpHeadFold",
    "outserv", "loc_name",
)

CONTAINER_METHOD_CANDIDATES = (
    "AddCopy", "PasteCopy", "CreateObject", "GetContents", "Delete",
)


def probe_environment(app):
    section(app, "1  UMGEBUNG")
    emit(app, "  Python: {}".format(sys.version.replace("\n", " ")))
    for method in ("GetVersion", "GetVersionString", "GetBuild"):
        attempt(app, "app." + method + "()", getattr(
            app, method, lambda: "Methode fehlt"))
    project = attempt(app, "app.GetActiveProject()", app.GetActiveProject)
    study_case = attempt(app, "app.GetActiveStudyCase()", app.GetActiveStudyCase)
    emit(app, "  Projekt    : {}".format(describe(project)))
    emit(app, "  Study Case : {}".format(describe(study_case)))
    return study_case


def probe_comstatsim(app):
    """UNSICHERHEIT 1: Wie wird ComStatsim auf ein bestimmtes ElmRes gelenkt?"""
    section(app, "2  ComStatsim UND ERGEBNISBINDUNG  (Unsicherheit 1)")
    qds = None
    for getter, label in (
        (lambda: app.GetFromStudyCase("ComStatsim"),
         "app.GetFromStudyCase('ComStatsim')"),
        (lambda: app.GetFromStudyCase("ComStatsim.ComStatsim"),
         "app.GetFromStudyCase('ComStatsim.ComStatsim')"),
    ):
        qds = attempt(app, label, getter)
        if qds is not None:
            break
    emit(app, "  Gefunden: {}".format(describe(qds)))
    found = probe_attributes(app, qds, RESULT_ATTRIBUTE_CANDIDATES, "ComStatsim")
    emit(app, "")
    emit(app, "  ERWARTET: genau ein Kandidat liefert ein ElmRes-Objekt.")
    emit(app, "  Dieser Name bindet den Rechenlauf an ein eigenes Ergebnisobjekt.")
    if not any(hasattr(v, "GetClassName") for v in found.values()):
        emit(app, "  -> Kein ElmRes aufgeloest. Dann greift der Fallback:")
        emit(app, "     rechnen lassen und das Ergebnis anschliessend kopieren.")
    return qds


def probe_container_copy(app, study_case):
    """UNSICHERHEIT 2: Kann der Study Case ein ElmRes kopieren?"""
    section(app, "3  KOPIERFAEHIGKEIT DES STUDY CASE  (Unsicherheit 2)")
    if study_case is None:
        emit(app, "  Kein aktives Study Case -- uebersprungen.")
        return
    for name in CONTAINER_METHOD_CANDIDATES:
        method = getattr(study_case, name, None)
        emit(app, "  {:<16} {}".format(
            name, "vorhanden, aufrufbar" if callable(method) else "FEHLT"))
    emit(app, "")
    emit(app, "  ElmRes im aktiven Study Case:")
    try:
        results = study_case.GetContents("*.ElmRes") or []
    except Exception as exc:
        emit(app, "    GetContents fehlgeschlagen: {}".format(exc))
        results = []
    if not results:
        emit(app, "    keine gefunden")
    for item in results:
        rows = columns = "?"
        try:
            item.Load()
            rows = item.GetNumberOfRows()
            columns = item.GetNumberOfColumns()
        except Exception as exc:
            rows = "Ladefehler: {}".format(exc)
        finally:
            try:
                item.Release()
            except Exception:
                pass
        emit(app, "    {:<44} {} Zeilen x {} Spalten".format(
            describe(item), rows, columns))
        # The desc field carries the per-scenario outage list in the design.
        route, value = read_attribute(item, "desc")
        emit(app, "      desc via {}: typ {} -> {!r}".format(
            route, type(value).__name__, value))
    emit(app, "")
    emit(app, "  WICHTIG: 'desc' ist in PowerFactory ueblicherweise eine LISTE")
    emit(app, "  von Strings, kein String. Der Typ oben entscheidet, wie der")
    emit(app, "  Runner die Freischaltungsliste schreibt und zurueckliest.")


def probe_scenarios(app):
    section(app, "4  OPERATION SCENARIOS")
    folder = attempt(app, "app.GetProjectFolder('scen')",
                     lambda: app.GetProjectFolder("scen"))
    emit(app, "  Ordner: {}".format(describe(folder)))
    active = attempt(app, "app.GetActiveScenario()", app.GetActiveScenario)
    emit(app, "  Aktiv : {}".format(describe(active)))
    scenarios = []
    if folder is not None:
        for label, getter in (
            ("GetContents('*.IntScenario', 1)",
             lambda: folder.GetContents("*.IntScenario", 1)),
            ("GetContents('*.IntScenario')",
             lambda: folder.GetContents("*.IntScenario")),
            ("GetChildren(1)", lambda: folder.GetChildren(1)),
        ):
            result = attempt(app, label, getter)
            if result:
                scenarios = result
                break
    emit(app, "")
    emit(app, "  Gefundene Szenarien:")
    flat = []
    for entry in scenarios or []:
        flat.extend(entry if isinstance(entry, (list, tuple)) else [entry])
    if not flat:
        emit(app, "    keine")
    for item in flat:
        has_on = callable(getattr(item, "Activate", None))
        has_off = callable(getattr(item, "Deactivate", None))
        emit(app, "    {:<48} Activate={} Deactivate={}".format(
            describe(item), has_on, has_off))
    emit(app, "")
    emit(app, "  ERWARTET: Deactivate() muss vorhanden sein -- der Referenzfall")
    emit(app, "  REF wird ohne aktives Szenario gerechnet.")


def probe_variations(app):
    """UNSICHERHEIT 3: Reicht Activate() bei Expansion Stages, oder haengt
    die Wirksamkeit an der Study Time?"""
    section(app, "5  NETWORK VARIATIONS UND STUFEN  (Unsicherheit 3)")
    folder = None
    for key in ("scheme", "variations", "netdat"):
        folder = attempt(app, "app.GetProjectFolder('{}')".format(key),
                         lambda k=key: app.GetProjectFolder(k))
        if folder is not None:
            emit(app, "  -> Ordnerschluessel '{}' liefert {}".format(
                key, describe(folder)))
            break
    schemes = []
    if folder is not None:
        schemes = attempt(app, "GetContents('*.IntScheme', 1)",
                          lambda: folder.GetContents("*.IntScheme", 1)) or []
    emit(app, "")
    emit(app, "  Varianten und Stufen:")
    if not schemes:
        emit(app, "    keine gefunden")
    for scheme in schemes:
        emit(app, "    {:<48} Activate={}".format(
            describe(scheme), callable(getattr(scheme, "Activate", None))))
        try:
            stages = scheme.GetContents("*.IntSstage", 1) or []
        except Exception as exc:
            emit(app, "      Stufen nicht lesbar: {}".format(exc))
            continue
        for stage in stages:
            emit(app, "      Stufe {}".format(describe(stage)))
            probe_attributes(app, stage, STAGE_TIME_CANDIDATES, "IntSstage")
    emit(app, "")
    emit(app, "  ERWARTET: ein Zeitattribut je Stufe (vermutlich tAcTime).")
    emit(app, "  Fehlt es, muss der Runner die Study Time setzen statt nur")
    emit(app, "  Activate() aufzurufen -- das entscheidet ueber SCAN_VARIATIONS.")
    for method in ("GetStudyTime", "SetStudyTime"):
        study_case = app.GetActiveStudyCase()
        emit(app, "  IntCase.{:<14} {}".format(
            method, "vorhanden" if callable(
                getattr(study_case, method, None)) else "FEHLT"))


def main():
    import powerfactory

    app = powerfactory.GetApplication()
    if app is None:
        raise RuntimeError("PowerFactory application is unavailable.")

    emit(app, "GridLens Installations-Sonde -- rein lesend, aendert nichts.")
    study_case = probe_environment(app)
    probe_comstatsim(app)
    probe_container_copy(app, study_case)
    probe_scenarios(app)
    probe_variations(app)

    section(app, "ENDE -- bitte die gesamte Ausgabe zurueckgeben")
    emit(app, "  {} Zeilen erzeugt.".format(len(_LINES)))


if __name__ == "__main__":
    main()
