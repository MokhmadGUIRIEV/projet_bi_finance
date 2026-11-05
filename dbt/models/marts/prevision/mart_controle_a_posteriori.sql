{{ config(tags=['prevision']) }}
-- Contrôle hors échantillon sur du RÉEL : la prévision arrêtée au 31/12/2025 est confrontée aux encours
-- de dépôts de janvier 2026 publiés depuis par les banques centrales (etl/controle_a_posteriori.py).
-- Les encours publiés sont conservés dans data/sources/depots_reels_janvier_2026.csv.
select
    md5(code_filiale)          as id_controle,
    code_filiale,
    date_controle,
    depots_reels_devise,
    depots_p05_devise,
    depots_p50_devise,
    depots_p95_devise,
    erreur_p50_pct,
    dans_intervalle_90,
    case when dans_intervalle_90 then 'Oui' else 'Non' end as dans_la_fourchette,
    source
from {{ source('ml', 'controle_depots_reels') }}
