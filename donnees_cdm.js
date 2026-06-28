// Genere par collecteur_cdm.py — ne pas editer a la main.
// Source : API-Football, Coupe du Monde 2022 (avec xG).
// Mise a jour : 28/06/2026 04:55
var LEAGUE_AVG = 8.8;
var TEAMS = {
 "Qatar": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [
   5
  ],
  "sot": [
   0
  ],
  "cd": [
   6
  ],
  "xgf": [
   null
  ],
  "xga": [
   null
  ],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Ecuador": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [
   6
  ],
  "sot": [
   3
  ],
  "cd": [
   5
  ],
  "xgf": [
   null
  ],
  "xga": [
   null
  ],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "England": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [
   13
  ],
  "sot": [
   7
  ],
  "cd": [
   8
  ],
  "xgf": [
   null
  ],
  "xga": [
   null
  ],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Iran": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [
   8
  ],
  "sot": [
   3
  ],
  "cd": [
   13
  ],
  "xgf": [
   null
  ],
  "xga": [
   null
  ],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Senegal": {
  "type": "nation",
  "cat": "nation_caf",
  "sf": [
   15
  ],
  "sot": [
   4
  ],
  "cd": [
   10
  ],
  "xgf": [
   null
  ],
  "xga": [
   null
  ],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Netherlands": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [
   10
  ],
  "sot": [
   3
  ],
  "cd": [
   15
  ],
  "xgf": [
   null
  ],
  "xga": [
   null
  ],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "USA": {
  "type": "nation",
  "cat": "nation_concacaf",
  "sf": [
   6
  ],
  "sot": [
   1
  ],
  "cd": [
   7
  ],
  "xgf": [
   null
  ],
  "xga": [
   null
  ],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Wales": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [
   7
  ],
  "sot": [
   3
  ],
  "cd": [
   6
  ],
  "xgf": [
   null
  ],
  "xga": [
   null
  ],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Argentina": {
  "type": "nation",
  "cat": "nation_conmebol",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Saudi Arabia": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Denmark": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Tunisia": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Mexico": {
  "type": "nation",
  "cat": "nation_concacaf",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Poland": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "France": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Australia": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Morocco": {
  "type": "nation",
  "cat": "nation_caf",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Croatia": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Germany": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Japan": {
  "type": "nation",
  "cat": "nation_afc",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Spain": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Costa Rica": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Belgium": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Canada": {
  "type": "nation",
  "cat": "nation_concacaf",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Switzerland": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Cameroon": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Uruguay": {
  "type": "nation",
  "cat": "nation_conmebol",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "South Korea": {
  "type": "nation",
  "cat": "nation_afc",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Portugal": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Ghana": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Brazil": {
  "type": "nation",
  "cat": "nation_conmebol",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 },
 "Serbia": {
  "type": "nation",
  "cat": "nation_uefa",
  "sf": [],
  "sot": [],
  "cd": [],
  "xgf": [],
  "xga": [],
  "pos": 50,
  "style": "-",
  "press": "-",
  "bloc": "-",
  "top": false
 }
};
var UPCOMING = [];
var HISTORY = [];
