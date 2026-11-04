"""Contrôle a posteriori de la prévision sur des données RÉELLES postérieures à la date d'arrêté.

La prévision s'arrête au 31/12/2025 et projette janvier 2026. Or les banques centrales ont depuis
publié les encours de dépôts de janvier 2026 : on vérifie si l'encours réel (x part de marché) tombe
dans la fourchette P5-P95 prévue pour le 31/01/2026. C'est un test hors échantillon sur du réel.

Les encours publiés sont conservés dans data/sources/depots_reels_janvier_2026.csv (versionné) : le
résultat reste le même d'un lancement à l'autre, même sans Internet ou si une API est en panne. Une
filiale absente du fichier est téléchargée puis ajoutée ; si sa source est indisponible, elle est
écartée et le contrôle est signalé comme incomplet.
"""
from __future__ import annotations

import logging

import pandas as pd

from . import sources_reelles as sr
from .config import DOSSIER_DBT, DOSSIER_SOURCES
from .db import moteur

log = logging.getLogger(__name__)
DATE_CONTROLE = pd.Timestamp("2026-01-31")
FICHIER_DEPOTS_PUBLIES = DOSSIER_SOURCES / "depots_reels_janvier_2026.csv"
FILIALES_SANS_DONNEE = {"CM"}     # bulletin BEAC : pas de point mensuel janvier 2026 en API


def _telecharger_depot(filiale: str) -> dict | None:
    d = sr.SOURCES_DEPOTS[filiale]()
    s = d.set_index("date_ancrage").encours.sort_index()
    if DATE_CONTROLE not in s.index:          # séries hebdo : interpolation au 31/01
        s.loc[DATE_CONTROLE] = float("nan")
        s = s.sort_index().interpolate(method="time")
    if pd.isna(s.get(DATE_CONTROLE)):
        return None
    return {"code_filiale": filiale, "date_controle": DATE_CONTROLE.date().isoformat(),
            "encours_publie": float(s.loc[DATE_CONTROLE]), "source": d.source.iloc[-1]}


def depots_publies() -> pd.DataFrame:
    """Encours publié au 31/01/2026 par filiale, avant application de la part de marché."""
    attendues = [f for f in sr.SOURCES_DEPOTS if f not in FILIALES_SANS_DONNEE]
    connus = pd.read_csv(FICHIER_DEPOTS_PUBLIES) if FICHIER_DEPOTS_PUBLIES.exists() else None
    deja = set() if connus is None else set(connus.code_filiale)
    manquantes = [f for f in attendues if f not in deja]
    if not manquantes:
        return connus
    ancien_debut, ancien_fin = sr.DEBUT, sr.FIN
    sr.DEBUT, sr.FIN = "2025-12-01", "2026-02-28"
    nouveaux = []
    try:
        for filiale in manquantes:
            try:
                ligne = _telecharger_depot(filiale)
            except Exception as exc:              # source indisponible : signalée à la fin
                log.warning("  %s : source indisponible (%s)", filiale, exc)
                continue
            if ligne:
                nouveaux.append(ligne)
    finally:
        sr.DEBUT, sr.FIN = ancien_debut, ancien_fin
    if nouveaux:
        ajout = pd.DataFrame(nouveaux)
        connus = ajout if connus is None else pd.concat([connus, ajout], ignore_index=True)
        connus.to_csv(FICHIER_DEPOTS_PUBLIES, index=False)
    return connus


def controler() -> pd.DataFrame | None:
    engine = moteur()
    prev = pd.read_sql("select code_filiale, date_prevision, depots_p05_devise, depots_p50_devise, depots_p95_devise "
                       "from ml.prevision_tresorerie_quotidienne", engine, parse_dates=["date_prevision"])
    prev = prev[prev.date_prevision == DATE_CONTROLE].set_index("code_filiale")
    parts = pd.read_csv(DOSSIER_DBT / "seeds" / "ref_filiales.csv").set_index("code_filiale").part_de_marche_depots_pct
    depots = depots_publies()
    if depots is None or depots.empty:
        log.warning("Contrôle a posteriori impossible (pas d'accès aux sources) : étape ignorée.")
        return None
    lignes = []
    for ligne in depots.itertuples():
        if ligne.code_filiale not in prev.index:
            continue
        p = prev.loc[ligne.code_filiale]
        reel = ligne.encours_publie * parts[ligne.code_filiale] / 100
        lignes.append({"code_filiale": ligne.code_filiale, "date_controle": DATE_CONTROLE.date(),
                       "depots_reels_devise": reel, "depots_p05_devise": p.depots_p05_devise,
                       "depots_p50_devise": p.depots_p50_devise, "depots_p95_devise": p.depots_p95_devise,
                       "erreur_p50_pct": 100 * (p.depots_p50_devise - reel) / reel,
                       "dans_intervalle_90": bool(p.depots_p05_devise <= reel <= p.depots_p95_devise),
                       "source": ligne.source})
    res = pd.DataFrame(lignes)
    res.to_sql("controle_depots_reels", engine, schema="ml", if_exists="replace", index=False)
    for r in res.itertuples():
        log.info("  %-3s : réel %s | prévu P50 %s (erreur %+.2f %%) | dans [P5;P95] : %s", r.code_filiale,
                 f"{r.depots_reels_devise / 1e6:,.0f} M", f"{r.depots_p50_devise / 1e6:,.0f} M",
                 r.erreur_p50_pct, "oui" if r.dans_intervalle_90 else "NON")
    log.info("Couverture de l'intervalle à 90 %% : %d / %d filiales", res.dans_intervalle_90.sum(), len(res))
    attendu = len(sr.SOURCES_DEPOTS) - len(FILIALES_SANS_DONNEE)
    if len(res) < attendu:
        log.warning("Contrôle incomplet : %d filiales sur %d. Relancer quand les sources seront disponibles.", len(res), attendu)
    return res


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    controler()
