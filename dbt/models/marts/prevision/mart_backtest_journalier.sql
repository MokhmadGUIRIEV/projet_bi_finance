{{ config(tags=['prevision']) }}
-- Détail jour par jour du backtest (graphique « réel vs prévu » dans Power BI).
-- Les montants en euros servent à calculer l'erreur du groupe : additionner des devises locales
-- donnerait trop de poids aux francs CFA (1 EUR = 655,957 XOF ou XAF).
select
    md5(concat_ws('|', b.code_filiale, b.serie, b.modele, b.origine, b.date_jour)) as id_backtest,
    b.origine,
    b.code_filiale,
    b.serie,
    b.modele,
    b.est_champion,
    b.date_jour,
    b.reel  as reel_devise,
    b.prevu as prevu_devise,
    b.reel  / t.taux_eur as reel_eur,
    b.prevu / t.taux_eur as prevu_eur
from {{ source('ml', 'backtest_prevision') }} b
join {{ ref('dim_filiale') }} f on f.code_filiale = b.code_filiale
join {{ ref('fct_taux_change') }} t on t.code_devise = f.code_devise and t.date_cours = cast(b.date_jour as date)
