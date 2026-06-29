# Récapitulatif COMPLET — Site de prédiction de tirs (football) + cotes bookmakers

Document de passation à jour. Donne tout le contexte pour qu'une autre personne ou IA reprenne le projet.

**Dossier de travail local :** `C:\Users\nelso\Projects\objet`

## 1. But du projet
Un site web qui, pour chaque équipe de foot : montre son historique détaillé (tirs, tirs cadrés, possession…), prédit le nombre de tirs / tirs cadrés des prochains matchs, et **compare cette prédiction aux vraies cotes des bookmakers** pour conseiller un pari OVER ou UNDER.

## 2. Hébergement et accès
- **Dépôt GitHub (code + données) :** https://github.com/nelsonfut9-bot/objet  (PUBLIC pour l'instant)
- **Site en ligne :** https://nelsonfut9-bot.github.io/objet/app_cdm.html
- **Hébergement :** GitHub Pages (gratuit, site statique).
- **Collecte automatique :** GitHub Actions (cron), tourne sans le PC de l'utilisateur.
- Pour mettre à jour : déposer les fichiers via GitHub → bouton « Add file » → « Upload files » (glisser-déposer), puis « Commit changes ».

## 3. Source de données : API-Football (api-sports.io), abonnement Ultra
- Clé stockée en **secret GitHub** `API_FOOTBALL_KEY` (jamais en clair).
- En-tête : `x-apisports-key`. Base : `https://v3.football.api-sports.io`.

## 4. Fichiers du dépôt
| Fichier | Rôle |
|---|---|
| **app_cdm.html** | Site (interface ES5). Lit `donnees_cdm.js`. |
| **collecte_auto.py** | Robot : stats + cotes à venir + historique cotes. Modes `--odds-only`, `--odds-history`. |
| **donnees_cdm.js** | Données générées : `LEAGUE_AVG`, `COMPS`, `TEAMS`, `ODDS`, `ODDS_HIST`. |
| **odds.json** | Cotes des matchs à venir. |
| **odds_history.json** | Cotes des matchs déjà joués (backtest vs book). |
| **probe_odds.py** | Sonde cotes (catalogue + scan 10 jours + dump fixture précis). |
| **.github/workflows/collecte.yml** | Collecte complète (00:10 + 06:00 UTC). |
| **.github/workflows/odds_refresh.yml** | Cotes à venir toutes les heures. |
| **.github/workflows/odds_history.yml** | Backfill cotes passées (03:30 UTC). |
| **.github/workflows/probe.yml** | Sonde manuelle (option `fixture_id`). |

## 5. CE QUI MARCHE
- Fiches d'équipe, recherche, filtres, backtest honnête (sans lookahead).
- Analyse match (2 équipes), heure française, cotes bookmakers sur matchs à venir.
- **Conseil OVER/UNDER** : comparaison estimation vs ligne du book.
- **Backtest vs bookmaker** (onglet Suivi → source « Vs bookmaker ») : compare la prédiction à la vraie ligne book enregistrée avant le match.
- Détail match : affiche cotes book historiques si disponibles (`ODDS_HIST`).
- Chaque match d'équipe porte un `fid` (ID fixture) pour lier stats et cotes.

## 6. LIMITE sur les cotes par équipe
- API-Football fournit surtout le **total du match** (`Total Shots`, `Total ShotOnGoal`).
- Les marchés **par équipe** existent dans le catalogue mais ne sont pas toujours relayés par l'API pour chaque fixture.
- **Vérifier :** GitHub Actions → « Sonde cotes » → Run workflow → renseigner un `fixture_id` d'un gros match à venir → consulter `odds_probe.json` → champ `par_equipe_present`.

## 7. CE QUI RESTE À FAIRE
1. **Déposer sur GitHub** les fichiers modifiés de `C:\Users\nelso\Projects\objet` (upload manuel si pas de git local).
2. **Lancer** le workflow « Historique cotes backtest » pour remplir `odds_history.json` progressivement.
3. **Lancer** la sonde sur un fixture Mondial 2026 proche pour confirmer si les cotes par équipe arrivent.
4. **Confidentialité** (plus tard) : dépôt privé + Cloudflare Pages avec mot de passe.

## 8. Modèle de prédiction
- Forme récente (0.6×5 derniers + 0.4×10 derniers tirs), ajustée par défense adverse, domicile (+12%), compétition.
- Loi normale → probabilités ; conseil pari = estimation vs ligne book.

## 9. Pas de risque IP/bookmaker
Les cotes sont récupérées par GitHub (serveurs GitHub), pas par le navigateur de l'utilisateur.

## 10. Mise à jour du 29/06/2026
- Projet copié et continué dans `Projects\objet`.
- Ajout cron horaire cotes, backfill historique, backtest vs bookmaker, sonde fixture précise.
