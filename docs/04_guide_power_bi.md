# 04 — Cockpit Power BI

## 1. Ouvrir le projet déjà construit

Le rapport est fourni au format **projet Power BI (`.pbip`)** dans `powerbi/Cresus/` : 15 tables importées du schéma `marts`, 4 paramètres What-if, 20 relations, 48 mesures DAX, 3 rôles de sécurité et 5 pages (42 visuels), sur 3 ans (2023-2025). Procédure complète et valeurs attendues : [docs/09](09_procedure_pas_a_pas.md), § 10 et 11.

1. Lancer le pipeline (`python pipeline.py`) pour remplir le schéma `marts` de PostgreSQL.
2. Ouvrir **Power BI Desktop** (version de mi-2025 ou plus récente) → *Fichier → Ouvrir* → `powerbi/Cresus/Cresus.pbip`.
   - Si Power BI refuse le fichier (version plus ancienne) : *Fichier → Options → Fonctionnalités en préversion* → cocher « Option d'enregistrement de projet Power BI (.pbip) », « Stocker le modèle sémantique au format TMDL » et « Stocker les rapports au format PBIR », puis redémarrer.
3. *Accueil → Actualiser*. Aux identifiants demandés pour PostgreSQL, choisir l'onglet **Base de données** : `postgres` / `postgres`. En cas de message sur le chiffrement, cliquer sur **OK** (base locale).
4. Si la base n'est pas sur `localhost:5432` / `cresus` : *Transformer les données → Modifier les paramètres* (`ServeurPostgres`, `BasePostgres`).
5. Pour garder une copie en un seul fichier : *Fichier → Enregistrer sous → .pbix*.

Le projet est produit par `powerbi/generer_pbip.py`, à partir de la structure réelle des tables, et de `powerbi/mesures_dax.dax`, source unique des mesures. Il a été ouvert dans Power BI Desktop 2.159 et contrôlé le 04/11/2026 : valeurs comparées à la base, simulateur recoupé avec `mart_stress_test`, rôles testés par requêtes DAX et dans *Afficher comme rôles*.

## 2. Modèle

Schéma en étoile : `dim_date`, `dim_filiale`, `dim_devise` et `dim_scenario_stress` filtrent les faits et les marts (relations 1 → *, filtrage simple).

| Dimension | Tables filtrées |
|---|---|
| `dim_date[date_jour]` | `fct_position_tresorerie_quotidienne`, `mart_exposition_change`, `mart_liquidite_placement`, `mart_prevision_tresorerie`, `mart_prevision_change`, `mart_backtest_journalier`, `mart_qualite_ancrage` |
| `dim_filiale[code_filiale]` | `fct_position_tresorerie_quotidienne`, `mart_liquidite_placement`, `mart_stress_test`, `mart_prevision_tresorerie`, `mart_backtest_journalier`, `mart_qualite_ancrage`, `mart_reserve_optimale`, `mart_controle_a_posteriori`, `mart_qualite_sources` |
| `dim_devise[code_devise]` | `dim_filiale`, `mart_exposition_change`, `mart_prevision_change` |
| `dim_scenario_stress[code_scenario]` | `mart_stress_test` |

Paramètres What-if : `Choc retraits %` (0 à 30, pas 1), `Choc change %` (−50 à 20, pas 1), `Multiplicateur sorties` (1 à 3, pas 0,1), `Choc taux (pb)` (0 à 300, pas 25).

Restent en amont, hors du rapport : `fct_flux_tresorerie_horaire`, `fct_taux_change`, `dim_type_transaction` et le catalogue `mart_qualite_defauts` (à consulter dans pgAdmin).

## 3. Les 5 pages

Une page par objectif du sujet, plus la qualité des données.

### Page 1 — Cockpit DAF (arbitrer)
- Segments : filiale, année.
- Cartes : position de trésorerie, ratio de liquidité, jours sous 100 %, refinancement levé, excédent placé, VaR de change.
- Refinancement levé et excédent placé par mois : on y voit 2023 (refinancement pendant la fuite des dépôts) et 2025 (placements).
- Tableau de liquidité par filiale.

### Page 2 — Prévisions (anticiper)
- Segment : filiale. Cartes : probabilité de passer sous 100 %, erreur de prévision (WAPE), janvier 2026 dans la fourchette.
- Position réalisée puis prévue (P5 / P50 / P95) ; encaissements et décaissements par mois.
- Réserve requise (P99) contre réserve actuelle ; contrôle sur les dépôts réels au 31/01/2026.

### Page 3 — Change & couverture (couvrir)
- Segment : devise. Cartes : exposition, VaR 95 % à 10 jours, coût annuel de couverture.
- Cours prévu (P5 / P50 / P95) et réalisé ; sans devise choisie, la courbe affiche l'USD.
- Tableau de décision par devise ; effet de change cumulé par devise.

### Page 4 — Simulateur de stress (résister)
- Segments : retraits, change, multiplicateur des sorties, taux.
- Cartes : position stressée, survie en jours (vide = sans limite), besoin de refinancement, coût annuel de ce besoin.
- Simulation par filiale, avec statut de résilience ; matrice des 7 scénarios historiques.

### Page 5 — Qualité des données (prouver)
- Segment : filiale. Cartes : lignes brutes reçues, taux de rejet, rejets inattendus, écart à l'encours réel.
- Défauts détectés et corrigés par l'ETL, par système source.
- Encours réel publié contre encours reconstitué : les deux courbes se superposent, c'est la preuve visuelle de l'ancrage sur le réel.

## 4. Sécurité (RLS)

Trois rôles sont définis : **Direction groupe** (tout voir), **Filiale France** (FR, EUR) et **Filiale Etats-Unis** (US, USD). Le filtre porte sur `dim_filiale` et `dim_devise`, et se propage aux faits par les relations. Ce sont des exemples pour le POC : en production, un rôle par filiale, alimenté par les groupes de l'annuaire.

Pour tester : *Modélisation → Afficher comme rôles*. Le rôle France doit afficher une position de 1,84 Md, 23 jours sous 100 % et une VaR vide (filiale en euros) ; le rôle États-Unis, 572 M, 44 jours et une VaR de 8,49 M.

## 5. Conseils pour la soutenance
- Démonstration en direct : régler les retraits sur 20 %, les sorties sur 2,5 et le taux sur 150 (scénario de panique), et montrer quelles filiales passent en « Critique ».
- Montrer la page Qualité : encours réel contre reconstitué, puis la page Prévisions : la fourchette contenait le réel de janvier 2026 pour 7 filiales sur 9.
- Afficher le lignage `dbt docs` pour démontrer la traçabilité (exigence Bâle III / BCBS 239).
