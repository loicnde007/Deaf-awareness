# Plateforme LSF — Apprentissage de la Langue des Signes Française

Application web éducative destinée aux élèves déficients auditifs de l'École Saint Jean-Baptiste de Nkolbikon (Bertoua, Cameroun).

Développée dans le cadre d'un mémoire de DIPES II à l'École Normale Supérieure de Bertoua.

## Fonctionnalités
- 📚 Leçons interactives (LSF & Français)
- ✍️ Quiz d'évaluation avec verrouillage anti-reprise
- 📊 Analyse des résultats par enseignant
- 💬 Messagerie intégrée
- 🤟 Traducteur LSF

> **Note :** La reconnaissance de gestes en direct (MediaPipe) est disponible uniquement dans la version locale.

## Lancer l'application

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Technologies
- Python · Streamlit · SQLite · Pandas · Plotly · spaCy
