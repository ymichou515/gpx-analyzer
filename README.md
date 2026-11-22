# Analyse GPX — application GNOME

Application graphique **GTK4** (PyGObject) d'analyse de traces GPX de running, avec un
mode texte sans interface graphique. Conçue et testée sous Gentoo Linux / GNOME.

## Fonctionnalités

- Ouverture d'une ou plusieurs traces GPX (sélecteur de trace dans la barre de titre).
- **Résumé** : distance, durée totale / temps en mouvement, allure moyenne et meilleure
  allure, vitesse moyenne (max), dénivelé +/−, altitude min/max, calories estimées
  (poids ajustable).
- **Kilométriques** : temps, allure et D+ par kilomètre (dernier segment partiel inclus).
- **Profil** : profil d'altitude rempli + allure par kilomètre, dessinés avec Cairo.
- **Carte** : parcours projeté avec point de départ (vert) et d'arrivée (rouge).
- **Export CSV** : bouton « Exporter CSV… » dans la barre d'en-tête, ou CLI
  `gpx-analyzer --csv analyse.csv trace.gpx`. Le fichier s'ouvre directement dans
  LibreOffice Calc (séparateur « ; », virgule décimale, UTF-8 avec BOM).
- Mode CLI : `gpx-analyzer --texte sortie.gpx` affiche le même rapport dans le terminal
  (fonctionne aussi sans serveur graphique).

## Installation sous Gentoo

Dépendances système :

```sh
emerge --ask dev-python/pygobject gui-libs/gtk
```

Puis, depuis ce dépôt :

```sh
python -m pip install --user .
```

ou pour l'essayer sans installation :

```sh
python -m gpx_analyzer chemin/vers/trace.gpx
```

Lancez ensuite l'application depuis le menu GNOME (« Analyse GPX », une session
bureau est nécessaire) ou en ligne de commande :

```sh
gpx-analyzer                        # interface graphique
gpx-analyzer trace1.gpx trace2.gpx  # ouverture directe de fichiers
gpx-analyzer --texte trace1.gpx     # rapport texte dans le terminal
gpx-analyzer --texte trace.gpx --poids 75
gpx-analyzer --csv analyse.csv trace1.gpx trace2.gpx  # un CSV par trace
```

Raccourci de bureau (intégration GNOME) :

```sh
cp data/fr.gpxanalyzer.GpxAnalyzer.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications/
```

## Génération de traces de test

```sh
python scripts/generate_test_gpx.py examples/demo.gpx --km 10.2
```

## Tests

```sh
python -m unittest discover -s tests -t .
```

Les tests couvrent le parseur GPX, le calcul des métriques (distance, splits,
dénivelé, calories) et le formatage. Les modules GTK nécessitent PyGObject et ne
sont importés qu'au lancement de l'interface : le mode `--texte` fonctionne sans.

## Structure

```
gpx_analyzer/
  gpx_parser.py    lecture XML, haversine, distances cumulées, vitesses
  analysis.py      métriques, splits, calories, lissage, formatage, rapport
  charts.py        tracés Cairo (altitude, allure, carte)
  main_window.py   application GTK4 (fenêtre, pages, sélecteur de traces)
  __main__.py      point d'entrée (GUI ou mode texte)
scripts/generate_test_gpx.py   générateur de traces GPX réalistes
tests/                         tests unitaires
```
