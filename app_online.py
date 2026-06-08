import streamlit as st
import json
import os
import math
import time
from collections import Counter
from datetime import datetime
import pandas as pd     
import plotly.express as px 
# import cv2  # désactivé - version en ligne
# import mediapipe as mp  # désactivé - version en ligne
import streamlit.components.v1 as components
import psycopg2
import psycopg2.extras
import spacy


# ════════════════════════════════════════
#   CONFIGURATION BASE DE DONNÉES
#   PostgreSQL Railway (production en ligne)
# ════════════════════════════════════════
DB_MODE = "postgresql"

DATABASE_URL = "postgresql://postgres:eoEQtfEYPFDXkGmGBSUEgHMtnUJXbGRE@acela.proxy.rlwy.net:57948/railway"

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

def get_cursor(conn, dictionary=False):
    """Retourne un curseur PostgreSQL."""
    if dictionary:
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor()

def db_execute(cursor, query, params=()):
    """Exécute une requête SQL PostgreSQL."""
    cursor.execute(query, params)

def db_read_sql(query, conn, params=None):
    """Lit un DataFrame PostgreSQL."""
    if params:
        return pd.read_sql(query, conn, params=params)
    return pd.read_sql(query, conn)

def row_to_dict(row):
    """Convertit un résultat PostgreSQL en dictionnaire."""
    if row is None:
        return None
    if hasattr(row, '_asdict'):
        return dict(row)
    if hasattr(row, 'keys'):
        return dict(row)
    return dict(row) if row else None

def rows_to_dict(rows):
    """Convertit une liste de résultats en liste de dictionnaires."""
    if not rows:
        return []
    return [row_to_dict(r) for r in rows]


def get_unread_messages_count():
    """Retourne le nombre de messages non lus."""
    try:
        conn = get_db_connection()
        cursor = get_cursor(conn)
        db_execute(cursor, "SELECT COUNT(*) FROM messages WHERE lu = FALSE")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except:
        return 0


def text_to_speech(text):
    """Fait parler le navigateur de l'utilisateur via JavaScript."""
    js_code = f"""
        <script>
        var msg = new SpeechSynthesisUtterance('{text}');
        msg.lang = 'fr-FR';
        window.speechSynthesis.speak(msg);
        </script>
    """
    components.html(js_code, height=0)





@st.cache_resource
def load_nlp_model():
    try:
        return spacy.load("fr_core_news_md")
    except:
        return spacy.load("fr_core_news_sm")

nlp = load_nlp_model()

def transformer_en_syntaxe_lsf(phrase):
    """
    Traduit une phrase française en structure LSF officielle.

    RÈGLES OFFICIELLES LSF :
    ─────────────────────────────────────────────────────────
    1. ORDRE CANONIQUE : TEMPS → SUJET → OBJET/LIEU → ADJ → VERBE → NÉGATION → ?
    2. ÊTRE supprimé quand lien sujet-attribut (nom, adj, profession)
       Ex: "Tu es médecin" → "toi médecin"
       Ex: "Il est grand"  → "lui grand"
    3. AVOIR supprimé quand auxiliaire ou expression idiomatique
       Ex: "J'ai cours"    → "moi cours"
       Ex: "J'ai faim"     → "moi faim"
       AVOIR gardé seulement si objet concret : "j'ai un livre" → "moi livre"
    4. Semi-auxiliaires (vouloir/pouvoir/devoir/aller+inf) → seul l'infinitif reste
       Ex: "Je vais manger" → "moi manger"
    5. Déterminants, prépositions, conjonctions → supprimés
    6. Pronoms → forme LSF : je→moi, tu→toi, il/elle→lui, nous/on→nous
    7. Mots interrogatifs → toujours en FIN de phrase
    8. Négation → "non" après le verbe
    ─────────────────────────────────────────────────────────
    """
    doc = nlp(phrase)

    # ── Dictionnaire des formes conjuguées → infinitif ──
    conjugues = {
        "suis":"être","es":"être","est":"être","sommes":"être","êtes":"être","sont":"être",
        "étais":"être","était":"être","étaient":"être","serai":"être","sera":"être","seront":"être",
        "ai":"avoir","as":"avoir","avons":"avoir","avez":"avoir","ont":"avoir","avais":"avoir",
        "avait":"avoir","avaient":"avoir","aurai":"avoir","aura":"avoir",
        "vais":"aller","vas":"aller","va":"aller","allons":"aller","allez":"aller","vont":"aller",
        "allais":"aller","allait":"aller","irai":"aller","ira":"aller",
        "fais":"faire","fait":"faire","faisons":"faire","faisais":"faire","ferai":"faire","fera":"faire",
        "veux":"vouloir","veut":"vouloir","voulons":"vouloir","voulez":"vouloir","veulent":"vouloir",
        "peux":"pouvoir","peut":"pouvoir","pouvons":"pouvoir","pouvez":"pouvoir","peuvent":"pouvoir",
        "dois":"devoir","doit":"devoir","devons":"devoir","devez":"devoir","doivent":"devoir",
        "sais":"savoir","sait":"savoir","savons":"savoir","savez":"savoir","savent":"savoir",
        "viens":"venir","vient":"venir","venons":"venir","venez":"venir","viennent":"venir",
        "prends":"prendre","prend":"prendre","prenons":"prendre",
        "mange":"manger","manges":"manger","mangeons":"manger","mangez":"manger",
        "pars":"partir","part":"partir","partons":"partir","partez":"partir","partent":"partir",
        "pars":"partir","partais":"partir",
        "aime":"aimer","aimes":"aimer","aimons":"aimer","aimez":"aimer","aiment":"aimer",
        "vois":"voir","voit":"voir","voyons":"voir","voyez":"voir","voient":"voir",
        "habite":"habiter","habites":"habiter","habitons":"habiter",
        "parle":"parler","parles":"parler","parlons":"parler",
        "joue":"jouer","joues":"jouer","jouons":"jouer",
        "cours":"courir","court":"courir",
        "appelle":"appeler","appelles":"appeler","s'appelle":"s'appeler",
        "comprends":"comprendre","comprend":"comprendre",
        "connais":"connaître","connaît":"connaître",
    }

    # ── Pronoms → forme LSF ──
    pronoms = {
        "je":"moi","j'":"moi","me":"moi","m'":"moi","moi":"moi",
        "tu":"toi","te":"toi","t'":"toi","toi":"toi",
        "il":"lui","elle":"lui","se":"lui","s'":"lui","lui":"lui","le":"lui","la":"lui",
        "nous":"nous","on":"nous",
        "vous":"vous",
        "ils":"eux","elles":"eux","eux":"eux","les":"eux",
    }

    # ── Possessifs → sujet LSF ──
    possessifs = {
        "mon":"moi","ma":"moi","mes":"moi",
        "ton":"toi","ta":"toi","tes":"toi",
        "son":"lui","sa":"lui","ses":"lui",
        "notre":"nous","nos":"nous",
        "votre":"vous","vos":"vous",
        "leur":"eux","leurs":"eux",
    }

    # ── Verbes semi-auxiliaires (on garde seulement l'infinitif qui suit) ──
    semi_aux = {"aller","vouloir","pouvoir","devoir","savoir","falloir"}

    # ── Mots de temps ──
    mots_temps = {
        "demain","hier","maintenant","aujourd'hui","bientôt","toujours","souvent",
        "parfois","avant","après","tôt","tard","déjà","encore","jamais",
        "lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche",
        "matin","soir","midi","nuit","semaine","mois","année","an",
    }

    # ── Mots interrogatifs ──
    mots_interro = {
        "comment","où","pourquoi","combien","quoi","qui","quand",
        "quel","quelle","quels","quelles","lequel","laquelle",
    }

    # ── Mots à ignorer (catégories grammaticales inutiles en LSF) ──
    pos_ignores = {"DET","ADP","CCONJ","SCONJ","PUNCT","SPACE","PART","AUX"}

    # ═══════════════════════════════
    # ANALYSE DE LA PHRASE
    # ═══════════════════════════════
    mots = [t.text.lower() for t in doc]

    # Détection possession (mon/ma/mes/ton...)
    est_possession = any(m in possessifs for m in mots)

    # Détection être attributif : être + NOM/ADJ juste après
    etre_attributif = False
    for i, tok in enumerate(doc):
        if conjugues.get(tok.text.lower()) == "être" or tok.lemma_.lower() == "être":
            for j in range(i+1, min(i+4, len(doc))):
                if doc[j].pos_ in ("NOUN","ADJ","PROPN"):
                    etre_attributif = True
                    break
                if doc[j].pos_ not in ("DET","ADV","PUNCT","SPACE"):
                    break

    # Détection avoir auxiliaire (pas lexical)
    # "avoir" est lexical seulement si suivi d'un objet concret (DET + NOUN)
    avoir_lexical = False
    for i, tok in enumerate(doc):
        if conjugues.get(tok.text.lower()) == "avoir":
            # Chercher DET+NOUN après → avoir lexical
            for j in range(i+1, min(i+4, len(doc))):
                if doc[j].pos_ == "DET":
                    for k in range(j+1, min(j+3, len(doc))):
                        if doc[k].pos_ == "NOUN":
                            avoir_lexical = True
                            break
                    break

    # Identifier verbe principal (lexical, pas semi-aux ni avoir/être aux)
    verbe_principal = None
    idx_verbe = -1
    # Passe 1 : chercher infinitif lexical (après semi-aux)
    for tok in doc:
        t = tok.text.lower()
        lemme = conjugues.get(t, tok.lemma_.lower())
        if tok.pos_ == "VERB" and lemme not in semi_aux | {"être","avoir"}:
            verbe_principal = lemme
            idx_verbe = tok.i
    # Passe 2 : si rien trouvé, prendre le verbe conjugué non auxiliaire
    if verbe_principal is None:
        for tok in doc:
            t = tok.text.lower()
            lemme = conjugues.get(t, tok.lemma_.lower())
            if tok.pos_ in ("VERB","AUX") and lemme not in semi_aux | {"être","avoir"}:
                verbe_principal = lemme
                idx_verbe = tok.i
                break

    # ═══════════════════════════════
    # CLASSIFICATION DES TOKENS
    # ═══════════════════════════════
    temps       = []
    sujets      = []
    noms_propres = []
    objets      = []
    adjectifs   = []
    verbes      = []
    negation    = []
    interro     = []

    for tok in doc:
        t  = tok.text.lower()
        l  = conjugues.get(t, tok.lemma_.lower())
        p  = tok.pos_

        # Négation
        if t in ("ne","n'","pas","jamais","rien","plus","personne","nullement"):
            if "non" not in negation:
                negation.append("non")
            continue

        # Mots interrogatifs → fin de phrase
        if t in mots_interro:
            if t not in interro:
                interro.append(t)
            continue

        # Pronoms sujets
        if t in pronoms:
            s = pronoms[t]
            if s not in sujets:
                sujets.append(s)
            continue

        # Possessifs → sujet implicite
        if t in possessifs:
            s = possessifs[t]
            if s not in sujets:
                sujets.append(s)
            continue

        # Catégories grammaticales ignorées
        if p in pos_ignores:
            continue

        # Noms propres (prénoms/noms de personnes)
        if p == "PROPN":
            if tok.text not in noms_propres:
                noms_propres.append(tok.text)
            continue

        # Mots de temps → en tête
        if t in mots_temps:
            if t not in temps:
                temps.append(t)
            continue

        # Verbe principal → infinitif
        if p == "VERB" and tok.i == idx_verbe:
            # Supprimer être attributif
            if l == "être" and etre_attributif:
                continue
            # Supprimer avoir auxiliaire (non lexical)
            if l == "avoir" and not avoir_lexical:
                continue
            # Supprimer semi-auxiliaires
            if l in semi_aux:
                continue
            if l not in verbes:
                verbes.append(l)
            continue

        # Tous les autres verbes → ignorés
        if p in ("VERB","AUX"):
            continue

        # Noms communs → objets
        if p == "NOUN":
            if t not in objets and t not in mots_temps:
                objets.append(t)
            continue

        # Adjectifs
        if p == "ADJ":
            if t not in adjectifs:
                adjectifs.append(t)
            continue

        # Adverbes (hors temps/interro)
        if p == "ADV" and t not in mots_temps and t not in mots_interro:
            if t not in adjectifs:
                adjectifs.append(t)
            continue

    # ═══════════════════════════════
    # RECONSTRUCTION SELON LES RÈGLES LSF
    # ═══════════════════════════════

    # CAS 1 : Possession "c'est mon/ton/son X" → OBJET + SUJET (sans être)
    if est_possession and not verbes:
        resultat = objets + adjectifs + sujets + negation + interro

    # CAS 2 : Être attributif → SUJET + ATTRIBUT (sans être)
    elif etre_attributif:
        resultat = temps + noms_propres + sujets + objets + adjectifs + negation + interro

    # CAS GÉNÉRAL : TEMPS → NOMS PROPRES → SUJET → OBJET → ADJ → VERBE → NÉG → ?
    else:
        resultat = temps + noms_propres + sujets + objets + adjectifs + verbes + negation + interro

    # Dédoublonnage en conservant l'ordre
    phrase_lsf = " ".join(dict.fromkeys(r for r in resultat if r))
    return phrase_lsf.strip()

# --- CONFIGURATION MEDIAPIPE désactivée (version en ligne) ---

# --- 0. CONFIGURATION ET INITIALISATION ---
st.set_page_config(layout="wide", page_title="Plateforme LSF - Mémoire Loïc")

# --- CONFIGURATION ET FICHIERS ---
LOG_FILE = "quiz_results_log.txt"
DB_FILE = "educational_data.json"

# --- 1. FONCTIONS DE PERSISTANCE (JSON) ---

def save_data(data):
    """Sauvegarde les leçons dans PostgreSQL Railway."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        for lecon_id, contenu in data.items():
            cursor.execute("""
                INSERT INTO lecons (id, contenu, date_modification)
                VALUES (%s, %s, NOW())
                ON CONFLICT (id) DO UPDATE
                SET contenu = EXCLUDED.contenu,
                    date_modification = NOW()
            """, (lecon_id, json.dumps(contenu, ensure_ascii=False)))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Erreur sauvegarde leçons : {e}")


def load_data():
    """Charge les leçons depuis PostgreSQL Railway."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, contenu FROM lecons ORDER BY id")
        rows = cursor.fetchall()
        conn.close()
        if rows:
            data = {}
            for row in rows:
                lecon_id = row[0]
                contenu = row[1] if isinstance(row[1], dict) else json.loads(row[1])
                data[lecon_id] = contenu
            return _nettoyer_quiz(data)
        else:
            return {}
    except Exception as e:
        st.error(f"Erreur chargement leçons : {e}")
        return {}



def load_analytics_css():
    """CSS dédié au pilotage pédagogique — appelé uniquement dans render_analytics()."""
    st.markdown("""
    <style>
    /* ── ANIMATIONS ── */
    @keyframes podium-rise {
        from { transform:scaleY(0); opacity:0; }
        to   { transform:scaleY(1); opacity:1; }
    }
    @keyframes float-up {
        0%,100% { transform:translateY(0); }
        50%     { transform:translateY(-7px); }
    }
    @keyframes crown-rock {
        0%,100% { transform:rotate(-12deg) scale(1); }
        50%     { transform:rotate(12deg) scale(1.15); }
    }
    @keyframes pulse-gold {
        0%  { box-shadow:0 0 0 0 rgba(245,158,11,.45); }
        70% { box-shadow:0 0 0 14px rgba(245,158,11,0); }
        100%{ box-shadow:0 0 0 0 rgba(245,158,11,0); }
    }
    @keyframes row-in {
        from { opacity:0; transform:translateX(-14px); }
        to   { opacity:1; transform:translateX(0); }
    }

    /* ── HEADER BANNER ── */
    .an-header {
        background:linear-gradient(135deg,#0F172A 0%,#1A56DB 55%,#7C3AED 100%);
        border-radius:22px; padding:34px 40px; margin-bottom:28px; margin-top:20px;
        position:relative; overflow:hidden;
    }
    .an-header::after {
        content:''; position:absolute; top:-60px; right:-60px;
        width:220px; height:220px; border-radius:50%;
        background:rgba(255,255,255,.04);
    }
    .an-header h2 {
        color:white !important; -webkit-text-fill-color:white !important;
        font-size:2rem !important; font-weight:800 !important;
        margin:0 0 4px 0 !important; letter-spacing:-.02em;
    }
    .an-header p { color:rgba(255,255,255,.72); margin:0; font-size:.94rem; }

    /* ── KPI CARDS ── */
    .kpi-grid {
        display:grid; grid-template-columns:repeat(4,1fr);
        gap:14px; margin-bottom:24px;
    }
    .kpi-card {
        background:#fff; border-radius:16px; padding:20px 18px 16px;
        border:1px solid #E2E8F0; box-shadow:0 2px 10px rgba(0,0,0,.05);
        text-align:center; position:relative; overflow:hidden;
        transition:transform .28s cubic-bezier(.34,1.56,.64,1), box-shadow .28s ease;
        animation:card-enter .5s ease both;
    }
    .kpi-card:hover { transform:translateY(-5px); box-shadow:0 14px 36px rgba(26,86,219,.14); }
    .kpi-card::after {
        content:''; position:absolute; bottom:0; left:0; right:0; height:3px;
    }
    .kpi-card.c1::after { background:linear-gradient(90deg,#1A56DB,#06B6D4); }
    .kpi-card.c2::after { background:linear-gradient(90deg,#10B981,#34D399); }
    .kpi-card.c3::after { background:linear-gradient(90deg,#7C3AED,#A78BFA); }
    .kpi-card.c4::after { background:linear-gradient(90deg,#F59E0B,#EF4444); }
    .kpi-icon { font-size:1.9rem; margin-bottom:6px; }
    .kpi-val  { font-size:2rem; font-weight:800; color:#0F172A;
                letter-spacing:-.03em; line-height:1; }
    .kpi-lbl  { font-size:.72rem; font-weight:700; color:#94A3B8;
                text-transform:uppercase; letter-spacing:.09em; margin-top:5px; }

    /* ── SECTION TITLES ── */
    .sec-title {
        font-family:'DM Sans',sans-serif;
        font-size:1.15rem; font-weight:800; color:#0F172A;
        margin:26px 0 14px; padding-bottom:9px;
        border-bottom:2px solid #F1F5F9;
        display:flex; align-items:center; gap:9px;
    }
    .sec-pill {
        background:linear-gradient(135deg,#1A56DB,#7C3AED);
        color:white; font-size:.65rem; font-weight:700;
        padding:2px 9px; border-radius:99px; letter-spacing:.07em;
    }

    /* ── PODIUM ── */
    .podium-stage {
        display:flex; align-items:flex-end; justify-content:center;
        gap:12px; padding:24px 0 0; margin-bottom:4px;
    }
    .pod-block  { display:flex; flex-direction:column; align-items:center; }
    .pod-avatar {
        border-radius:50%; display:flex; align-items:center; justify-content:center;
        font-size:1.55rem; margin-bottom:7px; width:60px; height:60px;
    }
    .pod-avatar.p1 {
        width:74px; height:74px; font-size:1.95rem;
        background:linear-gradient(135deg,#FCD34D,#F59E0B);
        box-shadow:0 6px 22px rgba(245,158,11,.55);
        animation:float-up 3s ease-in-out infinite, pulse-gold 2.2s ease-in-out infinite;
    }
    .pod-avatar.p2 { background:linear-gradient(135deg,#CBD5E1,#94A3B8); box-shadow:0 4px 14px rgba(148,163,184,.45); }
    .pod-avatar.p3 { background:linear-gradient(135deg,#E8A96A,#CD7F32); box-shadow:0 4px 14px rgba(205,127,50,.45); }
    .pod-avatar.p4 { background:linear-gradient(135deg,#A5B4FC,#6366F1); box-shadow:0 3px 12px rgba(99,102,241,.38); }
    .pod-avatar.p5 { background:linear-gradient(135deg,#5EEAD4,#14B8A6); box-shadow:0 3px 12px rgba(20,184,166,.38); }
    .pod-crown  { font-size:1.3rem; animation:crown-rock 3s ease-in-out infinite; margin-bottom:2px; }
    .pod-name   { font-weight:700; font-size:.78rem; color:#1E293B;
                  text-align:center; max-width:84px; word-break:break-word;
                  line-height:1.25; margin-bottom:3px; }
    .pod-pct    { font-weight:800; font-size:.88rem; margin-bottom:5px; }
    .pod-pct.p1 { color:#D97706; font-size:1rem; }
    .pod-pct.p2 { color:#64748B; }
    .pod-pct.p3 { color:#92400E; }
    .pod-pct.p4 { color:#4338CA; }
    .pod-pct.p5 { color:#0F766E; }
    .pod-bar {
        border-radius:8px 8px 0 0; width:76px;
        transform-origin:bottom;
        animation:podium-rise .75s cubic-bezier(.34,1.56,.64,1) both;
        display:flex; align-items:flex-end; justify-content:center;
        padding-bottom:6px;
        font-size:1rem; font-weight:900; color:rgba(255,255,255,.88);
    }
    .pod-bar.p1 { background:linear-gradient(180deg,#FDE68A,#F59E0B); height:115px; animation-delay:.05s; }
    .pod-bar.p2 { background:linear-gradient(180deg,#E2E8F0,#94A3B8); height:86px;  animation-delay:.15s; }
    .pod-bar.p3 { background:linear-gradient(180deg,#FBBF76,#CD7F32); height:66px;  animation-delay:.25s; }
    .pod-bar.p4 { background:linear-gradient(180deg,#C7D2FE,#6366F1); height:50px;  animation-delay:.35s; }
    .pod-bar.p5 { background:linear-gradient(180deg,#99F6E4,#14B8A6); height:38px;  animation-delay:.45s; }

    /* ── APPRECIATION ── */
    .apprec {
        border-radius:14px; padding:16px 20px;
        display:flex; align-items:center; gap:13px;
        margin:14px 0 6px; animation:card-enter .5s ease both;
    }
    .apprec.ok  { background:linear-gradient(135deg,#ECFDF5,#D1FAE5); border:1.5px solid #10B981; }
    .apprec.mid { background:linear-gradient(135deg,#FFFBEB,#FEF3C7); border:1.5px solid #F59E0B; }
    .apprec.bad { background:linear-gradient(135deg,#FEF2F2,#FEE2E2); border:1.5px solid #EF4444; }
    .apprec-ico { font-size:1.9rem; flex-shrink:0; }
    .apprec-ttl { font-weight:800; font-size:.97rem; margin-bottom:2px; }
    .apprec-sub { font-size:.83rem; color:#475569; }

    /* ── CLASSEMENT TABLE ── */
    .rank-table {
        background:#fff; border-radius:16px; border:1px solid #E2E8F0;
        overflow:hidden; box-shadow:0 2px 10px rgba(0,0,0,.05); margin-top:6px;
    }
    .rank-head {
        background:linear-gradient(135deg,#0F172A,#1A56DB);
        display:grid; grid-template-columns:46px 1fr 78px 72px 110px;
        gap:6px; padding:13px 22px;
        color:rgba(255,255,255,.82);
        font-size:.7rem; font-weight:700;
        text-transform:uppercase; letter-spacing:.09em;
    }
    .rank-row {
        display:grid; grid-template-columns:46px 1fr 78px 72px 110px;
        gap:6px; padding:12px 22px; align-items:center;
        border-bottom:1px solid #F1F5F9; transition:background .18s;
        animation:row-in .4s ease both;
    }
    .rank-row:last-child { border-bottom:none; }
    .rank-row:hover { background:#F8FAFC; }
    .rk-pos  { font-weight:800; font-size:.92rem; text-align:center; }
    .rk-name { font-weight:600; font-size:.86rem; color:#1E293B; }
    .rk-pct  { font-weight:700; font-size:.88rem; text-align:center; }
    .rk-cnt  { font-size:.8rem; color:#64748B; text-align:center; }
    .mini-bar  { height:5px; border-radius:99px; background:#F1F5F9; overflow:hidden; }
    .mini-fill { height:100%; border-radius:99px; }

    /* ── MESSAGERIE ── */
    .msg-hero {
        background:linear-gradient(135deg,#0F172A,#1A56DB,#06B6D4);
        background-size:200% 200%;
        animation:gradient-shift 7s ease infinite;
        border-radius:22px; padding:30px 36px;
        text-align:center; margin:32px 0 20px;
        position:relative; overflow:hidden;
    }
    .msg-hero::before {
        content:'✉️'; position:absolute; right:36px; top:50%;
        transform:translateY(-50%); font-size:4.5rem; opacity:.08;
    }
    .msg-hero h3 {
        color:white !important; -webkit-text-fill-color:white !important;
        font-size:1.6rem !important; font-weight:800 !important;
        margin:0 0 5px 0 !important;
    }
    .msg-hero p { color:rgba(255,255,255,.75); margin:0; font-size:.92rem; }
    .msg-card {
        background:#fff; border-radius:18px; border:1px solid #E2E8F0;
        padding:28px 30px; box-shadow:0 4px 18px rgba(26,86,219,.07);
    }
    .msg-lbl {
        font-size:.76rem; font-weight:700; color:#64748B;
        text-transform:uppercase; letter-spacing:.08em; margin-bottom:5px;
    }
    .msg-tip {
        background:linear-gradient(135deg,#EFF6FF,#F0FDF4);
        border:1px solid #BFDBFE; border-radius:11px;
        padding:11px 15px; font-size:.82rem; color:#1E40AF;
        margin-top:14px; display:flex; align-items:center; gap:8px;
    }
    </style>
    """, unsafe_allow_html=True)



def _nettoyer_quiz(data):
    """Nettoie les espaces parasites et complète les champs manquants."""
    for lid, lecon in data.items():
        # Matière par défaut si absente
        if "matiere" not in lecon or not lecon["matiere"]:
            lecon["matiere"] = "LSF"
        for q in lecon.get("quiz_questions", []):
            if "answer" in q:
                q["answer"] = q["answer"].strip()
            if "options" in q:
                q["options"] = [o.strip() for o in q["options"]]
    return data


# Initialisation sécurisée de l'état de session
if 'user_name' not in st.session_state:
    st.session_state.user_name = None
if 'user_surname' not in st.session_state:
    st.session_state.user_surname = None
if 'user_matricule' not in st.session_state:
    st.session_state.user_matricule = ""

if 'completed_quizzes' not in st.session_state:
    st.session_state.completed_quizzes = {} # On utilise un dictionnaire pour stocker les scores
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'user_grade' not in st.session_state:
    st.session_state.user_grade = ""
# Les autres (name, surname, phone) sont déjà dans votre code
if 'user_phone' not in st.session_state:
    st.session_state.user_phone = ""
if 'user_class' not in st.session_state:
    st.session_state.user_class = ""
if 'user_cycle' not in st.session_state:
    st.session_state.user_cycle = ""
if 'user_type_maladie' not in st.session_state:
    st.session_state.user_type_maladie = ""
if 'quiz_key' not in st.session_state:
    st.session_state.quiz_key = 0
if 'educational_content' not in st.session_state:
    st.session_state.educational_content = load_data()

# -- Initialisation des tables SQLite au demarrage --
if DB_MODE == "sqlite":
    try:
        _conn_init = get_db_connection()
        _cur_init  = _conn_init.cursor()
        _cur_init.executescript("""
            CREATE TABLE IF NOT EXISTS utilisateurs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                matricule TEXT UNIQUE NOT NULL,
                nom TEXT NOT NULL,
                prenom TEXT NOT NULL,
                telephone TEXT,
                classe TEXT,
                cycle TEXT,
                role TEXT DEFAULT 'Eleve',
                date_inscription TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                type_maladie TEXT DEFAULT 'Élève déficient auditif',
                age INTEGER
            );
            CREATE TABLE IF NOT EXISTS resultats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                matricule TEXT,
                nom_complet TEXT NOT NULL,
                lecon_id TEXT NOT NULL,
                score INTEGER NOT NULL,
                total_questions INTEGER NOT NULL,
                classe TEXT,
                cycle TEXT,
                annee_scolaire TEXT,
                date_examen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expediteur TEXT NOT NULL,
                destinataire TEXT NOT NULL,
                contenu TEXT NOT NULL,
                lu INTEGER DEFAULT 0,
                date_envoi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Migration : ajouter type_maladie si colonne absente
        try:
            _cur_init.execute("ALTER TABLE utilisateurs ADD COLUMN type_maladie TEXT DEFAULT 'Élève déficient auditif'")
            _conn_init.execute("UPDATE utilisateurs SET type_maladie='Élève déficient auditif' WHERE type_maladie IS NULL")
        except Exception:
            pass  # Colonne déjà existante
        try:
            _cur_init.execute('ALTER TABLE utilisateurs ADD COLUMN age INTEGER')
        except Exception:
            pass  # Colonne déjà existante

        # ══ MIGRATION : ajouter colonne matiere à resultats ══
        try:
            _cur_init.execute("ALTER TABLE resultats ADD COLUMN matiere TEXT DEFAULT ''")
        except Exception:
            pass  # Colonne déjà existante

        # ══ MIGRATION : corriger les anciens lecon_id vers les nouveaux formats ══
        # Table de correspondance : anciens IDs → (nouveau_id, matiere)
        _lecon_mapping = {
            "Leçon 1":           ("Leçon 1 - LSF",      "LSF"),
            "Lecon 1":           ("Leçon 1 - LSF",      "LSF"),
            "leçon 1":           ("Leçon 1 - LSF",      "LSF"),
            "Leçon 1 - LSF":     ("Leçon 1 - LSF",      "LSF"),
            "Leçon 2":           ("Leçon 1 - Français",  "Français"),
            "Lecon 2":           ("Leçon 1 - Français",  "Français"),
            "Leçon 1 - Français":("Leçon 1 - Français",  "Français"),
        }
        for _ancien, (_nouveau, _mat) in _lecon_mapping.items():
            try:
                _cur_init.execute(
                    "UPDATE resultats SET lecon_id = ?, matiere = ? WHERE lecon_id = ?",
                    (_nouveau, _mat, _ancien)
                )
            except Exception:
                pass

        # ══ REMPLIR matiere pour enregistrements existants sans matiere ══
        # Pour les lecon_id déjà au bon format, on déduit la matiere depuis l'ID
        try:
            _cur_init.execute("SELECT DISTINCT lecon_id FROM resultats WHERE matiere = '' OR matiere IS NULL")
            _rows_sans_mat = _cur_init.fetchall()
            for (_lid,) in _rows_sans_mat:
                _mat_deduite = ""
                if _lid and " - " in _lid:
                    _mat_deduite = _lid.split(" - ")[-1].strip()
                if _mat_deduite:
                    _cur_init.execute(
                        "UPDATE resultats SET matiere = ? WHERE lecon_id = ? AND (matiere = '' OR matiere IS NULL)",
                        (_mat_deduite, _lid)
                    )
        except Exception:
            pass

        _conn_init.commit()
        _conn_init.close()
    except Exception as _e_init:
        pass

# --- 1. FONCTIONS D'UTILITE (Correctifs Encodage) ---



def check_if_quiz_done_persistently(full_name, lesson_id):
    """Vérifie dans la base si l'élève a déjà un score pour ce quiz."""
    try:
        conn = get_db_connection()
        cursor = get_cursor(conn)
        query = "SELECT id FROM resultats WHERE nom_complet = %s AND lecon_id = %s"
        db_execute(cursor, query, (full_name, lesson_id))
        result = row_to_dict(cursor.fetchone())
        conn.close()
        return result is not None
    except:
        return False



def apply_custom_styles():
    """Design Système Magique — LSF Platform v3.0 ✨"""
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Serif+Display:ital@0;1&display=swap');

        /* ═══════════════════════════════════════
           ✨ KEYFRAME ANIMATIONS MAGIQUES
        ═══════════════════════════════════════ */
        @keyframes gradient-flow {
            0%   { background-position: 0% 50%; }
            50%  { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        @keyframes float-up {
            from { opacity: 0; transform: translateY(16px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes shimmer {
            0%   { background-position: -200% center; }
            100% { background-position: 200% center; }
        }
        @keyframes pulse-glow {
            0%, 100% { box-shadow: 0 0 0 0 rgba(26,86,219,0.4); }
            50%       { box-shadow: 0 0 0 8px rgba(26,86,219,0); }
        }
        @keyframes spin-slow {
            from { transform: rotate(0deg); }
            to   { transform: rotate(360deg); }
        }
        @keyframes logo-aura {
            0%   { box-shadow: 0 0 0 3px rgba(59,130,246,0.7),  0 0 32px rgba(59,130,246,0.4); }
            25%  { box-shadow: 0 0 0 3px rgba(16,185,129,0.7),  0 0 32px rgba(16,185,129,0.4); }
            50%  { box-shadow: 0 0 0 3px rgba(249,115,22,0.7),  0 0 32px rgba(249,115,22,0.4); }
            75%  { box-shadow: 0 0 0 3px rgba(168,85,247,0.7),  0 0 32px rgba(168,85,247,0.4); }
            100% { box-shadow: 0 0 0 3px rgba(59,130,246,0.7),  0 0 32px rgba(59,130,246,0.4); }
        }
        @keyframes logo-pulse {
            0%, 100% { transform: scale(1); }
            50%       { transform: scale(1.05); }
        }
        @keyframes sidebar-bar {
            0%   { background-position: 0% 50%; }
            50%  { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        @keyframes tab-selected-glow {
            0%, 100% { box-shadow: 0 2px 12px rgba(26,86,219,0.4); }
            50%       { box-shadow: 0 2px 20px rgba(26,86,219,0.7), 0 0 30px rgba(6,182,212,0.3); }
        }
        @keyframes metric-enter {
            from { opacity: 0; transform: translateY(10px) scale(0.97); }
            to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes border-dance {
            0%, 100% { border-color: rgba(26,86,219,0.4); }
            33%       { border-color: rgba(6,182,212,0.6); }
            66%       { border-color: rgba(124,58,237,0.5); }
        }

        /* ═══════════════════════════════════════
           VARIABLES DESIGN SYSTEM
        ═══════════════════════════════════════ */
        :root {
            --primary:       #1A56DB;
            --primary-light: #3B82F6;
            --primary-glow:  rgba(26,86,219,0.18);
            --accent:        #06B6D4;
            --accent-soft:   rgba(6,182,212,0.12);
            --purple:        #7C3AED;
            --success:       #10B981;
            --warning:       #F59E0B;
            --danger:        #EF4444;
            --sidebar-bg:    #060d1a;
            --sidebar-text:  #E2E8F0;
            --sidebar-muted: #64748B;
            --surface:       #FFFFFF;
            --surface-2:     #F0F4FF;
            --border:        #E2E8F0;
            --text-primary:  #0F172A;
            --text-secondary:#475569;
            --radius:        14px;
            --shadow-sm:     0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04);
            --shadow-md:     0 4px 20px rgba(26,86,219,0.12), 0 2px 6px rgba(0,0,0,0.06);
            --shadow-lg:     0 20px 50px rgba(26,86,219,0.15), 0 4px 10px rgba(0,0,0,0.07);
            --magic-gradient: linear-gradient(135deg, #1A56DB, #06B6D4, #7C3AED, #1A56DB);
        }

        /* ═══════════════════════════════════════
           BASE
        ═══════════════════════════════════════ */
        html, body, [class*="css"], [data-testid="stAppViewContainer"] {
            font-family: 'DM Sans', sans-serif !important;
            color: var(--text-primary);
        }

        [data-testid="stAppViewContainer"] > .main {
            background: var(--surface-2);
            background-image:
                radial-gradient(ellipse at 15% 5%, rgba(26,86,219,0.05) 0%, transparent 50%),
                radial-gradient(ellipse at 85% 95%, rgba(124,58,237,0.04) 0%, transparent 50%);
        }

        /* Animation d'entrée du contenu principal */
        .main .block-container > div > div {
            animation: float-up 0.5s ease both;
        }

        /* Réduire le padding en haut de la sidebar */
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 0.5rem !important;
        }

        /* Forcer le menu déroulant à s'ouvrir vers le BAS */
        [data-testid="stSidebar"] [data-baseweb="popover"] {
            top: 100% !important;
            bottom: auto !important;
        }
        [data-testid="stSidebar"] [data-baseweb="select"] [data-baseweb="popover"] ul {
            max-height: 300px !important;
            overflow-y: auto !important;
        }

        /* ═══════════════════════════════════════
           ✨ SIDEBAR MAGIQUE
        ═══════════════════════════════════════ */
        [data-testid="stSidebar"] {
            background: var(--sidebar-bg) !important;
            border-right: 1px solid rgba(255,255,255,0.06) !important;
            min-width: 290px !important;
        }

        /* Barre top animée arc-en-ciel */
        [data-testid="stSidebar"]::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 4px;
            background: linear-gradient(90deg, #1A56DB, #06B6D4, #7C3AED, #10B981, #1A56DB);
            background-size: 300% 100%;
            animation: sidebar-bar 5s ease infinite;
        }

        /* Logo ✨ */
        [data-testid="stSidebar"] [data-testid="stImage"] {
            display: flex !important;
            justify-content: center !important;
            margin: 28px 0 20px 0 !important;
        }
        [data-testid="stSidebar"] [data-testid="stImage"] img {
            width: 120px !important;
            border-radius: 18px !important;
            animation: logo-aura 4s ease-in-out infinite, logo-pulse 4s ease-in-out infinite !important;
        }

        /* Texte sidebar */
        [data-testid="stSidebar"] .stMarkdown p {
            color: var(--sidebar-text) !important;
            font-size: 0.95rem !important;
            font-weight: 500 !important;
            line-height: 1.5 !important;
        }
        [data-testid="stSidebar"] .stMarkdown h3 {
            color: #FFFFFF !important;
            font-size: 1rem !important;
            font-weight: 700 !important;
            margin: 0 !important;
        }
        [data-testid="stSidebar"] .stMarkdown strong {
            color: var(--accent) !important;
            font-weight: 700 !important;
            background: var(--accent-soft);
            padding: 1px 7px;
            border-radius: 6px;
        }
        [data-testid="stSidebar"] .stMarkdown em {
            color: #94A3B8 !important;
            font-style: normal;
        }

        /* Label navigation */
        [data-testid="stSidebar"] label {
            color: var(--sidebar-muted) !important;
            font-size: 0.72rem !important;
            font-weight: 700 !important;
            text-transform: uppercase !important;
            letter-spacing: 1.8px !important;
        }

        /* Selectbox navigation */
        [data-testid="stSidebar"] div[data-baseweb="select"] > div {
            background: rgba(255,255,255,0.07) !important;
            border: 1px solid rgba(255,255,255,0.12) !important;
            border-radius: 10px !important;
            transition: all 0.3s ease;
        }
        [data-testid="stSidebar"] div[data-baseweb="select"] > div:hover {
            border-color: rgba(6,182,212,0.5) !important;
            background: rgba(6,182,212,0.06) !important;
            box-shadow: 0 0 0 3px rgba(6,182,212,0.1) !important;
        }
        [data-testid="stSidebar"] div[data-baseweb="select"] span,
        [data-testid="stSidebar"] div[data-baseweb="select"] div,
        [data-testid="stSidebar"] div[data-baseweb="select"] p,
        [data-testid="stSidebar"] [data-baseweb="select"] [class*="ValueContainer"] *,
        [data-testid="stSidebar"] [data-baseweb="select"] [class*="singleValue"],
        [data-testid="stSidebar"] [data-baseweb="select"] [class*="placeholder"] {
            color: #FFFFFF !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
        }
        [data-testid="stSidebar"] div[data-baseweb="select"] svg {
            fill: rgba(255,255,255,0.7) !important;
        }

        /* Divider sidebar */
        [data-testid="stSidebar"] hr {
            border-color: rgba(255,255,255,0.07) !important;
            margin: 12px 0 !important;
        }

        /* Caption sidebar */
        [data-testid="stSidebar"] .stCaption {
            color: var(--sidebar-muted) !important;
            font-size: 0.82rem !important;
        }

        /* ═══════════════════════════════════════
           CONTENU PRINCIPAL
        ═══════════════════════════════════════ */
        .main .block-container {
            padding: 1rem 3rem 2.5rem 3rem !important;
            max-width: 1100px;
        }

        /* Supprimer l'espace blanc Streamlit au-dessus du contenu */
        [data-testid="stAppViewContainer"] > .main > div:first-child {
            padding-top: 0 !important;
        }
        div[data-testid="stDecoration"] {
            display: none !important;
        }
        #root > div:nth-child(1) > div > div > div > div > section > div {
            padding-top: 0rem !important;
        }

        /* ═══════════════════════════════════════
           ✨ BOUTONS MAGIQUES
        ═══════════════════════════════════════ */
        .stButton > button {
            font-family: 'DM Sans', sans-serif !important;
            font-weight: 600 !important;
            font-size: 0.9rem !important;
            border-radius: 10px !important;
            padding: 10px 22px !important;
            border: 1.5px solid var(--border) !important;
            background: var(--surface) !important;
            color: var(--text-primary) !important;
            box-shadow: var(--shadow-sm) !important;
            transition: all 0.28s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
            letter-spacing: 0.01em;
            position: relative;
            overflow: hidden;
        }
        .stButton > button::after {
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(120deg, transparent 0%, rgba(26,86,219,0.08) 50%, transparent 100%);
            background-size: 200% 100%;
            background-position: -200% center;
            transition: background-position 0.4s ease;
        }
        .stButton > button:hover::after {
            background-position: 200% center;
        }
        .stButton > button:hover {
            border-color: var(--primary-light) !important;
            color: var(--primary) !important;
            background: #f0f5ff !important;
            box-shadow: 0 0 0 3px rgba(26,86,219,0.12), 0 6px 20px rgba(26,86,219,0.15) !important;
            transform: translateY(-3px) scale(1.01) !important;
        }
        .stButton > button:active {
            transform: translateY(0px) scale(0.99) !important;
            transition-duration: 0.1s !important;
        }
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #1A56DB, #7C3AED) !important;
            background-size: 200% 200% !important;
            color: #FFFFFF !important;
            border: none !important;
            animation: gradient-flow 4s ease infinite !important;
        }
        .stButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, #1547C0, #6d28d9) !important;
            color: #FFFFFF !important;
            box-shadow: 0 0 0 3px rgba(26,86,219,0.2), 0 8px 24px rgba(26,86,219,0.4) !important;
            transform: translateY(-3px) scale(1.02) !important;
            animation: pulse-glow 1.5s ease infinite !important;
        }

        /* ═══════════════════════════════════════
           ✨ INPUTS MAGIQUES
        ═══════════════════════════════════════ */
        input[type="text"], input[type="password"], textarea,
        [data-baseweb="input"] input, [data-baseweb="textarea"] textarea {
            font-family: 'DM Sans', sans-serif !important;
            border-radius: 10px !important;
            border: 1.5px solid var(--border) !important;
            background: var(--surface) !important;
            font-size: 0.92rem !important;
            transition: all 0.25s ease !important;
        }
        input:focus, textarea:focus,
        [data-baseweb="input"]:focus-within input {
            border-color: var(--primary-light) !important;
            box-shadow: 0 0 0 3px rgba(26,86,219,0.12), 0 4px 14px rgba(26,86,219,0.1) !important;
            outline: none !important;
            transform: translateY(-1px);
        }

        /* Labels de formulaire */
        .stTextInput label, .stTextArea label, .stSelectbox label,
        .stRadio label, .stCheckbox label, .stMultiSelect label {
            font-weight: 600 !important;
            font-size: 0.88rem !important;
            color: var(--text-secondary) !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 4px !important;
        }

        /* Selectbox principale */
        div[data-baseweb="select"] > div {
            border-radius: 10px !important;
            border: 1.5px solid var(--border) !important;
            background: var(--surface) !important;
            font-size: 0.92rem !important;
            transition: all 0.2s ease !important;
        }
        div[data-baseweb="select"] > div:hover {
            border-color: var(--primary-light) !important;
            box-shadow: 0 0 0 3px var(--primary-glow) !important;
        }

        /* ═══════════════════════════════════════
           ✨ ONGLETS MAGIQUES
        ═══════════════════════════════════════ */
        .stTabs [data-baseweb="tab-list"] {
            background: var(--surface) !important;
            border-radius: 14px !important;
            padding: 5px !important;
            border: 1px solid var(--border) !important;
            gap: 2px !important;
            box-shadow: var(--shadow-sm) !important;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 10px !important;
            font-weight: 600 !important;
            font-size: 0.88rem !important;
            color: var(--text-secondary) !important;
            padding: 8px 18px !important;
            transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
        }
        .stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) {
            background: var(--primary-glow) !important;
            color: var(--primary) !important;
            transform: translateY(-1px);
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #1A56DB, #7C3AED) !important;
            color: #FFFFFF !important;
            animation: tab-selected-glow 2.5s ease-in-out infinite !important;
        }

        /* ═══════════════════════════════════════
           ✨ ALERTES MAGIQUES
        ═══════════════════════════════════════ */
        .stAlert {
            border-radius: var(--radius) !important;
            border: 1px solid var(--border) !important;
            border-left-width: 4px !important;
            box-shadow: var(--shadow-sm) !important;
            font-size: 0.92rem !important;
            animation: float-up 0.4s ease both !important;
        }
        [data-testid="stNotification"] {
            border-radius: var(--radius) !important;
        }

        /* ═══════════════════════════════════════
           ✨ MÉTRIQUES MAGIQUES (KPI Cards)
        ═══════════════════════════════════════ */
        [data-testid="stMetric"] {
            background: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: var(--radius) !important;
            padding: 20px 24px !important;
            box-shadow: var(--shadow-sm) !important;
            transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
            animation: metric-enter 0.5s ease both !important;
            position: relative;
            overflow: hidden;
        }
        [data-testid="stMetric"]::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 3px;
            background: var(--magic-gradient);
            background-size: 300% 100%;
            opacity: 0;
            transition: opacity 0.3s;
            animation: gradient-flow 4s ease infinite;
        }
        [data-testid="stMetric"]:hover {
            box-shadow: var(--shadow-md) !important;
            transform: translateY(-4px) !important;
            border-color: rgba(26,86,219,0.3) !important;
        }
        [data-testid="stMetric"]:hover::before {
            opacity: 1;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.78rem !important;
            font-weight: 700 !important;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--text-secondary) !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.9rem !important;
            font-weight: 700 !important;
            color: var(--text-primary) !important;
            letter-spacing: -0.02em;
        }

        /* ═══════════════════════════════════════
           DATAFRAME / TABLEAU
        ═══════════════════════════════════════ */
        [data-testid="stDataFrame"] {
            border-radius: var(--radius) !important;
            border: 1px solid var(--border) !important;
            overflow: hidden !important;
            box-shadow: var(--shadow-sm) !important;
            transition: box-shadow 0.3s, transform 0.3s !important;
        }
        [data-testid="stDataFrame"]:hover {
            box-shadow: var(--shadow-md) !important;
        }

        /* ═══════════════════════════════════════
           ✨ EXPANDER MAGIQUE
        ═══════════════════════════════════════ */
        .streamlit-expanderHeader {
            background: var(--surface) !important;
            border-radius: var(--radius) !important;
            border: 1px solid var(--border) !important;
            font-weight: 600 !important;
            font-size: 0.92rem !important;
            padding: 14px 18px !important;
            transition: all 0.25s ease !important;
        }
        .streamlit-expanderHeader:hover {
            background: #f0f5ff !important;
            border-color: rgba(26,86,219,0.3) !important;
            box-shadow: 0 2px 10px rgba(26,86,219,0.08) !important;
            transform: translateX(3px);
        }
        .streamlit-expanderContent {
            border: 1px solid var(--border) !important;
            border-top: none !important;
            border-radius: 0 0 var(--radius) var(--radius) !important;
            padding: 16px !important;
        }

        /* ═══════════════════════════════════════
           RADIO BUTTONS
        ═══════════════════════════════════════ */
        .stRadio [data-testid="stMarkdownContainer"] p {
            font-weight: 500 !important;
            font-size: 0.92rem !important;
        }
        .stRadio > div > div > label {
            transition: color 0.2s !important;
        }
        .stRadio > div > div > label:hover {
            color: var(--primary) !important;
        }

        /* ═══════════════════════════════════════
           DIVIDER MAGIQUE
        ═══════════════════════════════════════ */
        hr {
            border: none !important;
            height: 1px !important;
            background: linear-gradient(90deg, transparent, var(--border) 20%, var(--border) 80%, transparent) !important;
            margin: 24px 0 !important;
        }

        /* ═══════════════════════════════════════
           ✨ SCROLLBAR MAGIQUE
        ═══════════════════════════════════════ */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb {
            background: linear-gradient(180deg, #93C5FD, #A78BFA);
            border-radius: 99px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(180deg, #3B82F6, #7C3AED);
        }

        /* ═══════════════════════════════════════
           ✨ FORM SUBMIT BUTTON
        ═══════════════════════════════════════ */
        [data-testid="stFormSubmitButton"] > button {
            background: linear-gradient(135deg, #1A56DB, #06B6D4, #7C3AED) !important;
            background-size: 300% 300% !important;
            color: white !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 700 !important;
            padding: 12px 28px !important;
            font-size: 0.95rem !important;
            box-shadow: 0 4px 16px rgba(26,86,219,0.4) !important;
            transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
            animation: gradient-flow 4s ease infinite !important;
            letter-spacing: 0.02em;
        }
        [data-testid="stFormSubmitButton"] > button:hover {
            transform: translateY(-3px) scale(1.02) !important;
            box-shadow: 0 8px 28px rgba(26,86,219,0.5) !important;
        }

        </style>
    """, unsafe_allow_html=True)



def load_css():
    """Design Magique LSF Platform v3.0 ✨"""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700;800&family=DM+Serif+Display:ital@0;1&display=swap');

    /* ══ KEYFRAMES MAGIQUES ══ */
    @keyframes gradient-shift {
        0%   { background-position: 0% 50%; }
        50%  { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    @keyframes title-glow {
        0%, 100% { text-shadow: 0 0 0 rgba(26,86,219,0); }
        50%       { text-shadow: 0 4px 30px rgba(26,86,219,0.12); }
    }
    @keyframes bar-expand {
        from { width: 0; opacity: 0; }
        to   { width: 80px; opacity: 1; }
    }
    @keyframes card-enter {
        from { opacity: 0; transform: translateY(14px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes badge-pop {
        0%   { transform: scale(0.85); opacity: 0; }
        70%  { transform: scale(1.06); }
        100% { transform: scale(1); opacity: 1; }
    }
    @keyframes tab-glow {
        0%, 100% { box-shadow: 0 2px 12px rgba(26,86,219,0.4); }
        50%       { box-shadow: 0 2px 22px rgba(26,86,219,0.7), 0 0 30px rgba(6,182,212,0.25); }
    }

    /* ══ TITRES PRINCIPAUX MAGIQUES ══ */
    .main-title {
        text-align: center !important;
        font-family: 'DM Serif Display', serif !important;
        font-size: 2.8rem !important;
        font-weight: 400 !important;
        letter-spacing: -0.02em !important;
        background: linear-gradient(135deg, #0F172A 0%, #1A56DB 50%, #7C3AED 100%) !important;
        background-size: 200% 200% !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        margin-bottom: 8px !important;
        line-height: 1.15 !important;
        animation: gradient-shift 6s ease infinite, title-glow 4s ease-in-out infinite !important;
    }

    /* ══ ACCENT BAR ANIMÉE ══ */
    .title-accent {
        display: block;
        width: 0;
        height: 3px;
        background: linear-gradient(90deg, #1A56DB, #06B6D4, #7C3AED, #10B981);
        border-radius: 99px;
        margin: 0 auto 28px auto;
        background-size: 300% auto;
        animation: bar-expand 0.8s 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) both,
                   gradient-shift 4s 1s ease-in-out infinite;
    }

    /* ══ CARTES MAGIQUES ══ */
    .lsf-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 18px;
        padding: 28px 32px;
        margin-bottom: 20px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
        animation: card-enter 0.5s ease both;
        position: relative;
        overflow: hidden;
    }
    .lsf-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, #1A56DB, #06B6D4, #7C3AED);
        background-size: 200% auto;
        opacity: 0;
        transition: opacity 0.3s;
        animation: gradient-shift 4s ease infinite;
    }
    .lsf-card:hover {
        box-shadow: 0 12px 36px rgba(26,86,219,0.14), 0 2px 6px rgba(0,0,0,0.05);
        transform: translateY(-5px);
        border-color: rgba(26,86,219,0.2);
    }
    .lsf-card:hover::before {
        opacity: 1;
    }

    /* ══ BADGE RÔLE MAGIQUE ══ */
    .role-badge {
        display: inline-flex; align-items: center; gap: 6px;
        background: rgba(26,86,219,0.08);
        color: #1A56DB;
        border: 1px solid rgba(26,86,219,0.25);
        padding: 5px 14px;
        border-radius: 99px;
        font-size: 0.8rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.07em;
        animation: badge-pop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) both;
        transition: all 0.25s ease;
    }
    .role-badge:hover {
        background: rgba(26,86,219,0.14);
        box-shadow: 0 2px 10px rgba(26,86,219,0.2);
        transform: scale(1.04);
    }
    .role-badge.enseignant {
        background: rgba(16,185,129,0.08);
        color: #059669;
        border-color: rgba(16,185,129,0.25);
    }
    .role-badge.enseignant:hover {
        background: rgba(16,185,129,0.15);
        box-shadow: 0 2px 10px rgba(16,185,129,0.2);
    }

    /* ══ BOUTON FORM SUBMIT MAGIQUE ══ */
    [data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(135deg, #1A56DB, #06B6D4, #7C3AED) !important;
        background-size: 300% 300% !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        padding: 12px 28px !important;
        font-size: 0.95rem !important;
        box-shadow: 0 4px 16px rgba(26,86,219,0.4) !important;
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
        animation: gradient-shift 4s ease-in-out infinite !important;
        letter-spacing: 0.02em;
    }
    [data-testid="stFormSubmitButton"] > button:hover {
        transform: translateY(-3px) scale(1.02) !important;
        box-shadow: 0 10px 32px rgba(26,86,219,0.5) !important;
    }
    [data-testid="stFormSubmitButton"] > button:active {
        transform: translateY(0) scale(0.98) !important;
    }

    /* ══ MÉTRIQUES MAGIQUES ══ */
    [data-testid="stMetric"] {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 16px !important;
        padding: 20px 24px !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
        transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
        position: relative;
        overflow: hidden;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-5px) !important;
        box-shadow: 0 12px 30px rgba(26,86,219,0.13) !important;
        border-color: rgba(26,86,219,0.25) !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #64748B !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.85rem !important;
        font-weight: 700 !important;
        color: #0F172A !important;
        letter-spacing: -0.02em;
    }

    /* ══ ALERTES ANIMÉES ══ */
    .stAlert {
        border-radius: 12px !important;
        border: 1px solid #E2E8F0 !important;
        border-left-width: 4px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
        animation: card-enter 0.4s ease both !important;
    }

    /* ══ TITRES H1 H2 MAGIQUES ══ */
    h1, h2 {
        font-family: 'DM Sans', sans-serif !important;
        color: #0F172A !important;
        font-weight: 800 !important;
        letter-spacing: -0.03em !important;
    }
    h3, h4 {
        font-family: 'DM Sans', sans-serif !important;
        color: #1E293B !important;
        font-weight: 700 !important;
    }

    /* ══ DATAFRAME MAGIQUE ══ */
    [data-testid="stDataFrame"] {
        border-radius: 14px !important;
        border: 1px solid #E2E8F0 !important;
        overflow: hidden !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
        transition: all 0.3s ease !important;
    }
    [data-testid="stDataFrame"]:hover {
        box-shadow: 0 8px 24px rgba(26,86,219,0.1) !important;
        border-color: rgba(26,86,219,0.2) !important;
    }

    /* ══ EXPANDER MAGIQUE ══ */
    .streamlit-expanderHeader {
        background: #FFFFFF !important;
        border-radius: 12px !important;
        border: 1px solid #E2E8F0 !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
        transition: all 0.25s ease !important;
    }
    .streamlit-expanderHeader:hover {
        background: #f0f5ff !important;
        border-color: rgba(26,86,219,0.3) !important;
        transform: translateX(4px);
        box-shadow: 0 2px 10px rgba(26,86,219,0.08) !important;
    }

    /* ══ ONGLETS MAGIQUES ══ */
    .stTabs [data-baseweb="tab-list"] {
        background: #F8FAFC !important;
        border-radius: 14px !important;
        padding: 5px !important;
        border: 1px solid #E2E8F0 !important;
        gap: 2px !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        color: #475569 !important;
        padding: 8px 18px !important;
        transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
    }
    .stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) {
        background: rgba(26,86,219,0.07) !important;
        color: #1A56DB !important;
        transform: translateY(-1px);
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #1A56DB, #7C3AED) !important;
        background-size: 200% 200% !important;
        color: #FFFFFF !important;
        animation: tab-glow 2.5s ease-in-out infinite, gradient-shift 4s ease infinite !important;
    }

    </style>
    """, unsafe_allow_html=True)
    load_analytics_css()   # ← CSS analytics appliqué dans toutes les pages









def _home_inject_css():
    """Partie 1/4 — CSS premium de la page d'accueil (< 5 000 chars)."""
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;600;700;800&display=swap');
@keyframes hero-grad{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
@keyframes float-in{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
@keyframes bar-grow{from{width:0}to{width:72px}}
@keyframes pulse-ring{0%,100%{box-shadow:0 0 0 0 rgba(26,86,219,.35)}50%{box-shadow:0 0 0 10px rgba(26,86,219,0)}}
@keyframes spin-orb{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
@keyframes badge-pop{0%{transform:scale(.7);opacity:0}80%{transform:scale(1.08)}100%{transform:scale(1);opacity:1}}

/* Hero banner */
.da-hero{
  background:linear-gradient(135deg,#0a0f1e,#1A56DB,#7C3AED,#06B6D4);
  background-size:300% 300%;animation:hero-grad 8s ease infinite;
  border-radius:24px;padding:48px 40px 44px;text-align:center;
  margin-bottom:32px;position:relative;overflow:hidden;
}
.da-hero::before{content:'🤟';position:absolute;right:36px;top:50%;
  transform:translateY(-50%);font-size:6rem;opacity:.06;}
.da-hero h1{color:#fff!important;font-size:2.4rem!important;font-weight:800!important;
  margin:0 0 8px!important;letter-spacing:-.03em!important;
  animation:float-in .7s ease both;}
.da-hero p{color:rgba(255,255,255,.72);font-size:1.02rem;margin:0;
  animation:float-in .7s .12s ease both;}
.da-accent{display:block;width:0;height:3px;margin:14px auto 0;border-radius:99px;
  background:linear-gradient(90deg,#fff,rgba(255,255,255,.3));
  animation:bar-grow .9s .3s cubic-bezier(.34,1.56,.64,1) both;}

/* Stats row */
.da-stats{display:flex;gap:16px;margin-bottom:28px;flex-wrap:wrap;}
.da-stat{flex:1;min-width:110px;background:#fff;border:1px solid #E2E8F0;
  border-radius:16px;padding:18px 20px;text-align:center;
  box-shadow:0 2px 10px rgba(26,86,219,.06);
  animation:float-in .6s ease both;transition:all .3s ease;}
.da-stat:hover{transform:translateY(-4px);box-shadow:0 10px 28px rgba(26,86,219,.14);}
.da-stat-val{font-size:1.9rem;font-weight:800;color:#1A56DB;line-height:1;}
.da-stat-lbl{font-size:.72rem;font-weight:700;color:#64748B;
  text-transform:uppercase;letter-spacing:.08em;margin-top:4px;}

/* Auth card wrapper */
.da-card{background:#fff;border:1px solid #E2E8F0;border-radius:20px;
  padding:32px 36px;box-shadow:0 4px 24px rgba(26,86,219,.08);
  animation:float-in .5s ease both;position:relative;overflow:hidden;}
.da-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,#1A56DB,#06B6D4,#7C3AED);
  background-size:200%;animation:hero-grad 4s ease infinite;}
.da-card-title{font-size:1.22rem;font-weight:800;color:#0F172A;
  margin:0 0 6px;display:flex;align-items:center;gap:8px;}
.da-card-sub{font-size:.85rem;color:#64748B;margin:0 0 24px;}

/* Premium input style */
.da-field label{font-size:.78rem!important;font-weight:700!important;
  color:#475569!important;text-transform:uppercase!important;
  letter-spacing:.07em!important;}

/* Profile card (connecté) */
.da-profile{background:linear-gradient(135deg,#0F172A,#1A56DB);
  border-radius:20px;padding:28px 32px;color:#fff;
  display:flex;align-items:center;gap:20px;
  animation:float-in .5s ease both;margin-bottom:20px;}
.da-avatar{width:64px;height:64px;border-radius:50%;
  background:linear-gradient(135deg,#06B6D4,#7C3AED);
  display:flex;align-items:center;justify-content:center;
  font-size:1.8rem;flex-shrink:0;
  animation:pulse-ring 2.5s ease infinite;}
.da-profile-name{font-size:1.35rem;font-weight:800;margin:0 0 4px;}
.da-profile-sub{font-size:.88rem;color:rgba(255,255,255,.65);margin:0;}
.da-badge{display:inline-flex;align-items:center;gap:5px;
  background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);
  color:#fff;padding:4px 12px;border-radius:99px;
  font-size:.75rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.07em;margin-top:8px;
  animation:badge-pop .5s cubic-bezier(.34,1.56,.64,1) both;}

/* Notification badge */
.da-notif{display:inline-flex;align-items:center;gap:5px;
  background:#EF4444;color:#fff;border-radius:99px;
  padding:2px 9px;font-size:.72rem;font-weight:800;
  animation:badge-pop .4s ease both;margin-left:6px;}

/* Admin message card */
.da-msg{border-radius:14px;padding:16px 20px;margin-bottom:12px;
  transition:all .25s ease;}
.da-msg:hover{transform:translateX(4px);}
.da-msg-unread{background:#EFF6FF;border:1px solid #BFDBFE;}
.da-msg-read{background:#F8FAFC;border:1px solid #E2E8F0;}
.da-msg-header{display:flex;justify-content:space-between;
  align-items:center;margin-bottom:6px;}
.da-msg-from{font-weight:700;color:#0F172A;font-size:.93rem;}
.da-msg-meta{font-size:.75rem;color:#64748B;}
.da-msg-subj{font-weight:700;color:#1A56DB;margin:0 0 3px;font-size:.9rem;}
.da-msg-body{color:#475569;font-size:.88rem;margin:0;}
</style>
""", unsafe_allow_html=True)


def _home_render_hero():
    """Partie 2/4 — Hero banner premium avec effets JS avancés."""
    components.html("""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;700;800;900&family=Space+Grotesk:wght@700;800&display=swap" rel="stylesheet">
<style>
  *{margin:0;padding:0;box-sizing:border-box;}
  body{font-family:'DM Sans',sans-serif;background:transparent;overflow:hidden;}

  /* ── HERO CONTAINER ── */
  .hero{
    position:relative;border-radius:22px;
    padding:32px 36px 30px;text-align:center;
    overflow:hidden;min-height:180px;
    background:linear-gradient(135deg,#020817,#0f172a,#1A56DB,#7C3AED,#06B6D4);
    background-size:400% 400%;
    animation:gradShift 10s ease infinite;
  }

  /* ── CANVAS PARTICULES ── */
  #particleCanvas{
    position:absolute;top:0;left:0;width:100%;height:100%;
    pointer-events:none;z-index:0;
  }

  /* ── SCANLINE OVERLAY ── */
  .scanline{
    position:absolute;top:0;left:0;width:100%;height:100%;
    background:repeating-linear-gradient(
      0deg,
      transparent,transparent 2px,
      rgba(0,212,255,0.015) 2px,rgba(0,212,255,0.015) 4px
    );
    pointer-events:none;z-index:1;
  }

  /* ── CONTENU ── */
  .hero-content{position:relative;z-index:2;}

  /* ── BADGE TOP ── */
  .badge{
    display:inline-flex;align-items:center;gap:7px;
    background:rgba(255,255,255,.08);backdrop-filter:blur(12px);
    border:1px solid rgba(255,255,255,.18);
    border-radius:99px;padding:5px 14px;font-size:.72rem;
    color:rgba(255,255,255,.85);font-weight:700;letter-spacing:.1em;
    text-transform:uppercase;margin-bottom:16px;
    animation:fadeUp .6s ease both;
  }
  .badge-dot{
    width:7px;height:7px;border-radius:50%;
    background:#4ade80;
    box-shadow:0 0 8px #4ade80;
    animation:pulse 1.8s ease-in-out infinite;
  }

  /* ── TITRE PRINCIPAL ── */
  #mainTitle{
    font-family:'Space Grotesk',sans-serif;
    font-size:2.05rem;font-weight:800;
    color:#fff;line-height:1.15;
    margin-bottom:10px;
    letter-spacing:-.02em;
    min-height:2.5em;
  }
  .char{
    display:inline-block;
    opacity:0;
    transform:translateY(30px) rotateX(-90deg);
    animation:charDrop .5s cubic-bezier(.34,1.56,.64,1) both;
  }

  /* ── LIGNE DE SCAN LUMINEUSE ── */
  .light-scan{
    position:absolute;top:0;left:-100%;width:60%;height:100%;
    background:linear-gradient(90deg,transparent,rgba(255,255,255,.06),transparent);
    animation:scanMove 4s ease-in-out infinite;
    pointer-events:none;z-index:3;
  }

  /* ── SOUS-TITRE ── */
  .subtitle{
    color:rgba(255,255,255,.68);font-size:.92rem;
    margin-bottom:18px;animation:fadeUp .7s .6s ease both;opacity:0;
    animation-fill-mode:both;
  }

  /* ── BARRE ANIMÉE ── */
  .glow-bar{
    width:0;height:3px;margin:0 auto 20px;border-radius:99px;
    background:linear-gradient(90deg,#06B6D4,#1A56DB,#7C3AED,#EC4899);
    box-shadow:0 0 12px rgba(6,182,212,.6);
    animation:barGrow 1s .8s cubic-bezier(.34,1.56,.64,1) both;
  }



  /* ── COINS DÉCORATIFS ── */
  .corner{position:absolute;width:40px;height:40px;opacity:.35;}
  .corner-tl{top:14px;left:14px;border-top:2px solid #06B6D4;border-left:2px solid #06B6D4;border-radius:4px 0 0 0;}
  .corner-tr{top:14px;right:14px;border-top:2px solid #7C3AED;border-right:2px solid #7C3AED;border-radius:0 4px 0 0;}
  .corner-bl{bottom:14px;left:14px;border-bottom:2px solid #1A56DB;border-left:2px solid #1A56DB;border-radius:0 0 0 4px;}
  .corner-br{bottom:14px;right:14px;border-bottom:2px solid #EC4899;border-right:2px solid #EC4899;border-radius:0 0 4px 0;}

  /* ── ORBE DÉCORATIF ── */
  .orb{
    position:absolute;border-radius:50%;filter:blur(40px);pointer-events:none;
    animation:orbFloat 6s ease-in-out infinite;
  }
  .orb1{width:180px;height:180px;background:rgba(124,58,237,.25);top:-50px;right:-40px;animation-delay:0s;}
  .orb2{width:120px;height:120px;background:rgba(6,182,212,.2);bottom:-30px;left:-20px;animation-delay:-3s;}

  /* ── KEYFRAMES ── */
  @keyframes gradShift{
    0%{background-position:0% 50%}
    50%{background-position:100% 50%}
    100%{background-position:0% 50%}
  }
  @keyframes charDrop{
    to{opacity:1;transform:translateY(0) rotateX(0)}
  }
  @keyframes fadeUp{
    from{opacity:0;transform:translateY(16px)}
    to{opacity:1;transform:translateY(0)}
  }
  @keyframes barGrow{
    from{width:0}
    to{width:120px}
  }
  @keyframes scanMove{
    0%{left:-100%}70%,100%{left:150%}
  }
  @keyframes pulse{
    0%,100%{opacity:1;transform:scale(1)}
    50%{opacity:.5;transform:scale(1.5)}
  }
  @keyframes orbFloat{
    0%,100%{transform:translate(0,0)}
    50%{transform:translate(10px,-15px)}
  }
  @keyframes particleFade{
    0%{opacity:1}
    100%{opacity:0;transform:translateY(-30px)}
  }
</style>
</head>
<body>
<div class="hero">
  <!-- Canvas particules -->
  <canvas id="particleCanvas"></canvas>
  <!-- Scanlines -->
  <div class="scanline"></div>
  <!-- Lumière scannante -->
  <div class="light-scan"></div>
  <!-- Orbes décoratifs -->
  <div class="orb orb1"></div>
  <div class="orb orb2"></div>
  <!-- Coins UI -->
  <div class="corner corner-tl"></div>
  <div class="corner corner-tr"></div>
  <div class="corner corner-bl"></div>
  <div class="corner corner-br"></div>

  <div class="hero-content">
    <!-- Badge statut -->
    <div class="badge">
      <div class="badge-dot"></div>
      <span>Plateforme active</span>
    </div>

    <!-- Titre animé lettre par lettre -->
    <div id="mainTitle"></div>

    <!-- Sous-titre -->
    <p class="subtitle">Parce que chaque élève mérite d'apprendre dans sa langue. &nbsp;·&nbsp; Connectez-vous pour accéder à vos modules.</p>

    <!-- Barre lumineuse -->
    <div class="glow-bar"></div>


  </div>
</div>

<script>
// ── 1. ANIMATION TITRE LETTRE PAR LETTRE ──
(function(){
  const title = "🌟 Bienvenue sur Deaf Awareness";
  const el = document.getElementById('mainTitle');
  [...title].forEach((ch, i) => {
    const span = document.createElement('span');
    span.className = 'char';
    span.textContent = ch === ' ' ? '\u00A0' : ch;
    span.style.animationDelay = (0.08 + i * 0.045) + 's';
    // Couleur arc-en-ciel progressive sur "DEAF AWARENESS"
    if(i >= title.indexOf('DEAF')) {
      const pct = (i - title.indexOf('DEAF')) / 14;
      const colors = ['#60a5fa','#818cf8','#a78bfa','#c084fc','#e879f9','#f472b6'];
      const ci = Math.floor(pct * (colors.length-1));
      span.style.color = colors[Math.min(ci, colors.length-1)];
      span.style.textShadow = '0 0 20px ' + colors[Math.min(ci, colors.length-1)] + '66';
    }
    el.appendChild(span);
  });
})();


// ── 3. SYSTÈME DE PARTICULES CANVAS ──
(function(){
  const canvas = document.getElementById('particleCanvas');
  const ctx    = canvas.getContext('2d');
  let W, H, particles = [];

  function resize(){
    W = canvas.width  = canvas.offsetWidth;
    H = canvas.height = canvas.offsetHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  const COLORS = ['#60a5fa','#a78bfa','#06B6D4','#f472b6','#ffffff'];

  function mkParticle(){
    return {
      x: Math.random() * W,
      y: H + 10,
      vx: (Math.random() - .5) * .8,
      vy: -(Math.random() * 1.2 + 0.4),
      r: Math.random() * 2.2 + .6,
      alpha: Math.random() * .7 + .3,
      color: COLORS[Math.floor(Math.random() * COLORS.length)],
      life: 0,
      maxLife: Math.random() * 140 + 80,
      twinkle: Math.random() * Math.PI * 2
    };
  }

  for(let i=0;i<55;i++){
    const p = mkParticle();
    p.y = Math.random() * H; // position init répartie
    p.life = Math.random() * p.maxLife;
    particles.push(p);
  }

  function draw(){
    ctx.clearRect(0,0,W,H);
    const now = Date.now() * .001;

    // Lignes de connexion légères
    for(let i=0;i<particles.length;i++){
      for(let j=i+1;j<particles.length;j++){
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx*dx+dy*dy);
        if(dist < 70){
          ctx.beginPath();
          ctx.strokeStyle = 'rgba(255,255,255,' + (.08*(1-dist/70)) + ')';
          ctx.lineWidth = .4;
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.stroke();
        }
      }
    }

    particles.forEach((p,idx) => {
      p.x += p.vx;
      p.y += p.vy;
      p.life++;
      p.twinkle += .08;

      const lifeRatio = p.life / p.maxLife;
      const fadedAlpha = p.alpha * (lifeRatio < .2 ? lifeRatio/.2 : lifeRatio > .8 ? (1-lifeRatio)/.2 : 1);
      const twinkledAlpha = fadedAlpha * (.7 + .3 * Math.sin(p.twinkle));

      ctx.beginPath();
      const grad = ctx.createRadialGradient(p.x,p.y,0,p.x,p.y,p.r*2.5);
      grad.addColorStop(0, p.color);
      grad.addColorStop(1, 'transparent');
      ctx.fillStyle = grad;
      ctx.globalAlpha = twinkledAlpha;
      ctx.arc(p.x, p.y, p.r * 2.5, 0, Math.PI*2);
      ctx.fill();
      ctx.globalAlpha = 1;

      if(p.life >= p.maxLife || p.y < -10){
        particles[idx] = mkParticle();
      }
    });

    requestAnimationFrame(draw);
  }
  draw();
})();

// ── 4. HOVER INTERACTIF — PARALLAXE LÉGER ──
document.querySelector('.hero').addEventListener('mousemove', function(e){
  const rect = this.getBoundingClientRect();
  const cx = (e.clientX - rect.left) / rect.width  - .5;
  const cy = (e.clientY - rect.top)  / rect.height - .5;
  document.querySelector('.orb1').style.transform = `translate(${cx*20}px,${cy*20}px)`;
  document.querySelector('.orb2').style.transform = `translate(${-cx*15}px,${-cy*15}px)`;
});
document.querySelector('.hero').addEventListener('mouseleave', function(){
  document.querySelector('.orb1').style.transform = '';
  document.querySelector('.orb2').style.transform = '';
});
</script>
</body>
</html>
""", height=190)


def render_home():
    load_css()
    _home_inject_css()
    _home_render_hero()

    if st.session_state.user_name is None:
        # Ne pas interroger la DB ici — l'utilisateur n'est pas encore connecté
        label_gestion = "🗂️ Gestion"

        tab_login, tab_register, tab_admin = st.tabs([
            "🔐 Se Connecter",
            "📝 Inscription",
            label_gestion
        ])

        # ══════════════════════════════
        # ONGLET 1 — CONNEXION PREMIUM
        # ══════════════════════════════
        with tab_login:
            # Bloc décoratif HTML
            st.markdown("""
<div style="background:linear-gradient(135deg,#EFF6FF,#F5F3FF);border:1px solid #C7D2FE;
  border-radius:18px;padding:16px 22px;margin-bottom:12px;position:relative;overflow:hidden;">
  <div style="position:absolute;right:20px;top:50%;transform:translateY(-50%);
    font-size:3.5rem;opacity:.08;">🔐</div>
  <div style="font-size:1.15rem;font-weight:800;color:#1E293B;margin-bottom:4px;">
    Accéder à mon espace
  </div>
  <div style="font-size:.84rem;color:#64748B;">
    Entrez votre matricule pour vous connecter à la plateforme LSF.
  </div>
</div>
""", unsafe_allow_html=True)

            st.markdown("""<style>[data-testid=\"InputInstructions\"]{display:none!important;}</style>""", unsafe_allow_html=True)
            with st.form("login_form"):
                m_login = st.text_input("🪪 Matricule", type="password").strip().upper()
                pin_login = st.text_input("🔑 Code PIN (Enseignants uniquement)",
                    type="password")
                submit_login = st.form_submit_button("🚀 Se connecter",
                    use_container_width=True)

                if submit_login:
                    if m_login:
                        try:
                            conn = get_db_connection()
                            cursor = get_cursor(conn, dictionary=True)
                            db_execute(cursor,
                                "SELECT * FROM utilisateurs WHERE matricule = %s",
                                (m_login,))
                            user_data = row_to_dict(cursor.fetchone())

                            if user_data:
                                if user_data['role'] == "Enseignant":
                                    if pin_login != user_data.get('code_pin'):
                                        st.error("❌ Code PIN incorrect.")
                                        return
                                st.session_state.user_name      = user_data['prenom']
                                st.session_state.user_surname   = user_data['nom']
                                st.session_state.user_matricule = user_data['matricule']
                                st.session_state.user_role      = user_data['role']
                                st.session_state.user_class     = user_data['classe']
                                st.session_state.user_cycle     = user_data['cycle']
                                st.session_state.user_type_maladie = user_data.get('type_maladie', 'Élève déficient auditif')
                                st.session_state.user_grade     = user_data.get('grade','N/A')
                                st.session_state.user_phone     = user_data.get('telephone','')
                                # Réinitialiser la navigation pour que le menu
                                # se reconstruise avec les modules accessibles
                                st.session_state.nav_choice     = "Accueil"
                                conn.close()
                                st.success(f"✅ Bienvenue, {user_data['prenom']} !")
                                st.rerun()
                            else:
                                st.error("❌ Matricule inconnu. Contactez l'administration.")
                                conn.close()
                        except Exception as e:
                            st.error(f"Erreur de connexion : {e}")
                    else:
                        st.warning("⚠️ Veuillez saisir votre matricule.")



        # ══════════════════════════════
        # ONGLET 2 — INSCRIPTION PREMIUM
        # ══════════════════════════════
        with tab_register:
            st.markdown("""
<div style="background:linear-gradient(135deg,#FFF7ED,#FFFBEB);border:1px solid #FDE68A;
  border-radius:14px;padding:14px 18px;display:flex;align-items:center;
  gap:10px;margin-bottom:18px;">
  <span style="font-size:1.4rem;">🔒</span>
  <div>
    <div style="font-weight:700;color:#92400E;font-size:.92rem;">Section réservée</div>
    <div style="font-size:.8rem;color:#B45309;">
      Accès restreint à l'administration de l'établissement.
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

            ADMIN_CODE = "admin123"
            code_proviseur = st.text_input("🗝️ Code d'accès administratif",
                type="password", placeholder="Code proviseur...")

            if code_proviseur == ADMIN_CODE:
                st.markdown("""
<div style="background:linear-gradient(135deg,#ECFDF5,#F0FDF4);border:1px solid #6EE7B7;
  border-radius:14px;padding:14px 18px;display:flex;align-items:center;
  gap:10px;margin:14px 0;">
  <span style="font-size:1.4rem;">✅</span>
  <span style="font-weight:700;color:#065F46;font-size:.92rem;">
    Accès administratif accordé
  </span>
</div>
""", unsafe_allow_html=True)

                st.subheader("📝 Inscrire un nouveau membre")
                role_choice = st.radio("Type de compte :",
                    ["Élève", "Enseignant"], horizontal=True)

                with st.form("registration_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        nom      = st.text_input("Nom :")
                        prenom   = st.text_input("Prénom :")
                        tel      = st.text_input("Téléphone :")
                        mat_new  = st.text_input("Matricule :").strip().upper()
                    with col2:
                        if role_choice == "Enseignant":
                            grade_in   = st.text_input("Grade (ex: Docteur) :")
                            pin_in     = st.text_input("Code PIN :", type="password")
                            opts_cls   = ["SIL","CP","CE1","CE2","CM1","CM2",
                                          "6ème","5ème","4ème","3ème","L1","L2","L3"]
                            classes_sel  = st.multiselect("Classes accordées :", opts_cls)
                            classe_final = ", ".join(classes_sel)
                            cycle_final  = "Administration"
                            type_maladie_in = None
                            age_in = None
                        else:
                            classe_final   = st.text_input("Classe (ex: CM2) :").strip().upper()
                            cycle_final    = st.selectbox("Cycle :",
                                ["Primaire","Secondaire","Supérieur"])
                            type_maladie_in = st.selectbox("Type de déficience :", [
                                "Élève déficient auditif",
                                "Élève déficient visuel",
                                "Élève déficient moteur",
                                "Élève avec autisme",
                                "Autres"
                            ])
                            age_in = st.number_input("Âge :", min_value=3, max_value=30, step=1, value=10)
                            pin_in = None; grade_in = None

                    if st.form_submit_button("✨ Enregistrer le membre",
                            use_container_width=True):
                        if not nom or not prenom or not mat_new or not classe_final:
                            st.error("⚠️ Veuillez remplir tous les champs obligatoires.")
                        else:
                            try:
                                conn = get_db_connection()
                                cursor = get_cursor(conn)
                                sql = """INSERT INTO utilisateurs
                                  (matricule,nom,prenom,telephone,classe,cycle,role,code_pin,grade,type_maladie,age)
                                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
                                db_execute(cursor, sql,
                                    (mat_new, nom.upper(), prenom.capitalize(),
                                     tel, classe_final, cycle_final,
                                     role_choice, pin_in, grade_in,
                                     type_maladie_in or "Élève déficient auditif",
                                     age_in))
                                conn.commit()
                                st.success(f"✨ Compte {role_choice} créé — Matricule : {mat_new}")
                                conn.close()
                            except Exception:
                                st.error("❌ Matricule déjà utilisé ou base indisponible.")

                st.divider()
                st.subheader("🗑️ Supprimer un membre")
                try:
                    conn = get_db_connection()
                    cursor = get_cursor(conn, dictionary=True)
                    db_execute(cursor,
                        "SELECT matricule, nom, prenom, role FROM utilisateurs")
                    users_list = rows_to_dict(cursor.fetchall())
                    if users_list:
                        opts = {u['matricule']:
                            f"{u['matricule']} — {u['nom']} {u['prenom']} ({u['role']})"
                            for u in users_list}
                        user_to_del = st.selectbox(
                            "Sélectionnez le matricule à retirer :",
                            options=list(opts.keys()),
                            format_func=lambda x: opts[x])
                        confirm = st.checkbox("Je confirme vouloir supprimer ce compte.")
                        if st.button("Confirmer la suppression", type="primary"):
                            if confirm:
                                db_execute(cursor,
                                    "DELETE FROM utilisateurs WHERE matricule = %s",
                                    (user_to_del,))
                                db_execute(cursor,
                                    "DELETE FROM resultats WHERE matricule = %s",
                                    (user_to_del,))
                                conn.commit()
                                st.success(f"✅ Utilisateur {user_to_del} supprimé.")
                                st.rerun()
                            else:
                                st.warning("Veuillez cocher la case de confirmation.")
                    conn.close()
                except Exception as e:
                    st.error(f"Erreur liste membres : {e}")

            elif code_proviseur != "":
                st.error("❌ Code d'accès Proviseur incorrect.")

        # ══════════════════════════════
        # ONGLET 3 — GESTION PREMIUM
        # ══════════════════════════════
        with tab_admin:
            st.markdown("""
<div style="background:linear-gradient(135deg,#FFF1F2,#FEE2E2);border:1px solid #FECACA;
  border-radius:14px;padding:14px 18px;display:flex;align-items:center;
  gap:10px;margin-bottom:16px;">
  <span style="font-size:1.4rem;">🛡️</span>
  <div>
    <div style="font-weight:700;color:#991B1B;font-size:.92rem;">Accès Direction</div>
    <div style="font-size:.8rem;color:#B91C1C;">
      Zone sécurisée — gestion des membres et des messages.
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

            admin_view_code = st.text_input("🔑 Code Administrateur",
                type="password", key="view_admin_list",
                placeholder="Code administrateur...")

            if admin_view_code == "admin123":
                # ── Messages ──
                try:
                    conn = get_db_connection()
                    cursor = get_cursor(conn, dictionary=True)
                    db_execute(cursor,
                        "SELECT * FROM messages ORDER BY lu ASC, date_envoi DESC")
                    messages = rows_to_dict(cursor.fetchall())
                    conn.close()

                    nb_unread = sum(1 for m in messages if not m['lu'])
                    if nb_unread:
                        st.markdown(
                            f'<div style="margin-bottom:12px;">'
                            f'<span style="background:#EF4444;color:#fff;border-radius:99px;'
                            f'padding:4px 12px;font-size:.78rem;font-weight:800;">'
                            f'🔔 {nb_unread} message(s) non lu(s)</span></div>',
                            unsafe_allow_html=True)

                    if messages:
                        for msg in messages:
                            is_unread = not msg['lu']
                            bg  = "#EFF6FF" if is_unread else "#F8FAFC"
                            bdr = "#BFDBFE" if is_unread else "#E2E8F0"
                            lbl = "🔴 Non lu" if is_unread else "✅ Lu"
                            st.markdown(f"""
<div style="background:{bg};border:1px solid {bdr};border-radius:14px;
  padding:16px 20px;margin-bottom:10px;transition:all .25s ease;">
  <div style="display:flex;justify-content:space-between;
    align-items:center;margin-bottom:6px;">
    <span style="font-weight:700;color:#0F172A;font-size:.93rem;">
      👤 {msg['expediteur']} — {msg['classe']}
    </span>
    <span style="font-size:.74rem;color:#64748B;">
      {lbl} · {str(msg['date_envoi'])[:16]}
    </span>
  </div>
  <p style="margin:0 0 3px;font-weight:700;color:#1A56DB;font-size:.88rem;">
    📌 {msg['sujet']}
  </p>
  <p style="margin:0;color:#475569;font-size:.86rem;">{msg['contenu']}</p>
</div>
""", unsafe_allow_html=True)
                            cb1, cb2 = st.columns(2)
                            if is_unread:
                                with cb1:
                                    if st.button("✅ Marquer lu",
                                            key=f"lu_{msg['id']}",
                                            use_container_width=True):
                                        try:
                                            c2 = get_db_connection()
                                            cu2 = get_cursor(c2)
                                            db_execute(cu2,
                                                "UPDATE messages SET lu=TRUE WHERE id=%s",
                                                (msg['id'],))
                                            c2.commit(); c2.close()
                                            st.rerun()
                                        except Exception as e:
                                            st.error(e)
                            with cb2:
                                if st.button("🗑️ Supprimer",
                                        key=f"del_{msg['id']}",
                                        use_container_width=True):
                                    try:
                                        c3 = get_db_connection()
                                        cu3 = get_cursor(c3)
                                        db_execute(cu3,
                                            "DELETE FROM messages WHERE id=%s",
                                            (msg['id'],))
                                        c3.commit(); c3.close()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(e)
                    else:
                        st.info("Aucun message pour le moment.")
                except Exception as e:
                    st.error(f"Erreur messages : {e}")

                st.divider()

                # ── Membres ──
                try:
                    conn = get_db_connection()
                    st.markdown("""
<div style="font-size:1.05rem;font-weight:800;color:#0F172A;margin-bottom:10px;">
  📋 Liste des Élèves
</div>""", unsafe_allow_html=True)
                    df_eleves = db_read_sql(
                        "SELECT matricule,nom,prenom,telephone,classe,cycle,"
                        "date_inscription FROM utilisateurs WHERE role='Élève' "
                        "ORDER BY classe,nom", conn)
                    if not df_eleves.empty:
                        fc = st.selectbox("Filtrer par classe :",
                            ["Toutes"] + sorted(df_eleves['classe'].unique().tolist()))
                        if fc != "Toutes":
                            df_eleves = df_eleves[df_eleves['classe'] == fc]
                        st.dataframe(df_eleves, use_container_width=True)
                    st.markdown("""
<div style="font-size:1.05rem;font-weight:800;color:#0F172A;
  margin:18px 0 10px;">👨‍🏫 Liste des Enseignants</div>""",
                        unsafe_allow_html=True)
                    df_profs = db_read_sql(
                        "SELECT matricule,nom,prenom,telephone,grade,"
                        "code_pin,date_inscription FROM utilisateurs "
                        "WHERE role='Enseignant' ORDER BY nom", conn)
                    st.dataframe(df_profs, use_container_width=True)
                    conn.close()
                except Exception as e:
                    st.error(f"Erreur membres : {e}")

            elif admin_view_code != "":
                st.error("❌ Code d'accès administratif incorrect.")

    else:
        # ══════════════════════════════
        # PROFIL — UTILISATEUR CONNECTÉ
        # ══════════════════════════════
        nom_complet = f"{st.session_state.user_surname} {st.session_state.user_name}"
        role = st.session_state.user_role or ""
        classe = st.session_state.user_class or ""
        cycle  = st.session_state.get("user_cycle", "")
        grade  = st.session_state.get("user_grade", "")
        initiale = (st.session_state.user_name or "?")[0].upper()

        role_color = "#10B981" if role == "Enseignant" else "#1A56DB"
        role_icon  = "👨‍🏫" if role == "Enseignant" else "🎓"

        # Carte profil principale
        st.markdown(f"""
<div style="background:linear-gradient(135deg,#0F172A 0%,#1A56DB 60%,#7C3AED 100%);
  border-radius:22px;padding:28px 32px;display:flex;align-items:center;
  gap:22px;margin-bottom:22px;position:relative;overflow:hidden;">
  <div style="position:absolute;right:28px;top:50%;transform:translateY(-50%);
    font-size:5rem;opacity:.06;">🤟</div>
  <div style="width:66px;height:66px;border-radius:50%;
    background:linear-gradient(135deg,#06B6D4,#7C3AED);
    display:flex;align-items:center;justify-content:center;
    font-size:1.85rem;flex-shrink:0;font-weight:800;color:#fff;
    box-shadow:0 0 0 3px rgba(255,255,255,.25),0 0 18px rgba(6,182,212,.4);">
    {initiale}
  </div>
  <div>
    <div style="font-size:1.3rem;font-weight:800;color:#fff;margin-bottom:3px;">
      Bienvenue, {st.session_state.user_name} ! 👋
    </div>
    <div style="font-size:.86rem;color:rgba(255,255,255,.65);margin-bottom:6px;">
      {nom_complet}
    </div>
    <span style="display:inline-flex;align-items:center;gap:5px;
      background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);
      color:#fff;padding:4px 12px;border-radius:99px;
      font-size:.73rem;font-weight:700;text-transform:uppercase;
      letter-spacing:.07em;">
      {role_icon} {role}
    </span>
  </div>
</div>
""", unsafe_allow_html=True)

        # Info cards
        ci1, ci2, ci3 = st.columns(3)
        with ci1:
            st.markdown(f"""
<div style="background:#fff;border:1px solid #E2E8F0;border-radius:16px;
  padding:18px 20px;text-align:center;box-shadow:0 2px 10px rgba(26,86,219,.06);">
  <div style="font-size:1.6rem;margin-bottom:4px;">🏫</div>
  <div style="font-size:.7rem;font-weight:700;color:#64748B;
    text-transform:uppercase;letter-spacing:.07em;">Classe(s)</div>
  <div style="font-size:1.05rem;font-weight:800;color:#0F172A;margin-top:4px;">
    {classe or '—'}
  </div>
</div>""", unsafe_allow_html=True)
        with ci2:
            if role == "Enseignant":
                phone = st.session_state.get("user_phone", "") or "—"
                st.markdown(f"""
<div style="background:#fff;border:1px solid #E2E8F0;border-radius:16px;
  padding:18px 20px;text-align:center;box-shadow:0 2px 10px rgba(26,86,219,.06);">
  <div style="font-size:1.6rem;margin-bottom:4px;">📞</div>
  <div style="font-size:.7rem;font-weight:700;color:#64748B;
    text-transform:uppercase;letter-spacing:.07em;">Téléphone</div>
  <div style="font-size:1.05rem;font-weight:800;color:#0F172A;margin-top:4px;">
    {phone}
  </div>
</div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
<div style="background:#fff;border:1px solid #E2E8F0;border-radius:16px;
  padding:18px 20px;text-align:center;box-shadow:0 2px 10px rgba(26,86,219,.06);">
  <div style="font-size:1.6rem;margin-bottom:4px;">🏥</div>
  <div style="font-size:.7rem;font-weight:700;color:#64748B;
    text-transform:uppercase;letter-spacing:.07em;">Type de déficience</div>
  <div style="font-size:1.05rem;font-weight:800;color:#0F172A;margin-top:4px;">
    {st.session_state.get('user_type_maladie', 'Élève déficient auditif') or '—'}
  </div>
</div>""", unsafe_allow_html=True)
        with ci3:
            st.markdown(f"""
<div style="background:#fff;border:1px solid #E2E8F0;border-radius:16px;
  padding:18px 20px;text-align:center;box-shadow:0 2px 10px rgba(26,86,219,.06);">
  <div style="font-size:1.6rem;margin-bottom:4px;">{role_icon}</div>
  <div style="font-size:.7rem;font-weight:700;color:#64748B;
    text-transform:uppercase;letter-spacing:.07em;">Statut</div>
  <div style="font-size:1.05rem;font-weight:800;margin-top:4px;"
       style="color:{role_color};">
    {grade if grade and grade != 'N/A' else role}
  </div>
</div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        # Bouton déconnexion stylé
        col_dc, _ = st.columns([1, 3])
        with col_dc:
            if st.button("🚪 Se déconnecter", use_container_width=True):
                st.session_state.clear()
                st.rerun()


# --- 2. FONCTIONS DE RENDU ---






# ══════════════════════════════════════════════════════════════════
#   MOTEUR DE RECONNAISSANCE LSF — désactivé (version en ligne)
# ══════════════════════════════════════════════════════════════════

def recognize_sign_language():
    """Reconnaissance LSF désactivée sur la version en ligne (MediaPipe non disponible)."""
    import streamlit as st
    st.markdown("""
    <div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:12px;
                padding:24px;text-align:center;color:#92400E;">
        <h3>🤟 Reconnaissance en Direct</h3>
        <p>Cette fonctionnalité nécessite la version locale de l'application.<br>
        Elle utilise MediaPipe et votre caméra, ce qui n'est pas disponible
        sur la version hébergée en ligne.</p>
        <p><strong>Téléchargez la version locale pour accéder à cette fonctionnalité.</strong></p>
    </div>
    """, unsafe_allow_html=True)





def render_student_self_analysis(full_name, lesson_id):
    load_css()
    """Affiche l'analyse personnelle de l'élève pour une leçon spécifique."""
    try:
        conn = get_db_connection()
        query = "SELECT score, total_questions, date_examen FROM resultats WHERE nom_complet = %s AND lecon_id = %s"
        df_res = db_read_sql(query, conn, params=(full_name, lesson_id))
        conn.close()

        if not df_res.empty:
            st.markdown("---")
            st.subheader("📊 Ton Analyse Personnelle")
            
            score = df_res['score'].iloc[0]
            total = df_res['total_questions'].iloc[0]
            percentage = (score / total) * 100
            date = df_res['date_examen'].iloc[0]

            col1, col2, col3 = st.columns(3)
            col1.metric("Note", f"{score}/{total}")
            col2.metric("Réussite", f"{percentage:.1f}%")
            col3.write(f"📅 Validé le : {date}")

            # Petit graphique de jauge
            fig = px.pie(values=[score, total-score], names=['Correct', 'Incorrect'], 
                         color_discrete_sequence=['#00CC96', '#EF553B'], hole=0.5,
                         title="Répartition de tes réponses")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucune donnée d'analyse disponible pour le moment.")
    except Exception as e:
        st.error(f"Erreur lors de la récupération de l'analyse : {e}")



def render_admin_panel():
    st.markdown("""
    <div class="an-header">
        <h2>🔐 Panneau d'Administration Global</h2>
        <p>Gestion des utilisateurs · Suivi des activités · Accès restreint</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs([" 👥 Gestion des Utilisateurs", " 📊 Suivi des Activités"])

    # --- ONGLET 1 : GESTION DES UTILISATEURS ---
    with tab1:
        st.subheader("Liste des inscrits")
        try:
            conn = get_db_connection()
            query_users = "SELECT matricule, nom, prenom, telephone, classe, cycle, role, date_inscription FROM utilisateurs ORDER BY date_inscription DESC"
            df_users = db_read_sql(query_users, conn)
            
            if not df_users.empty:
                # --- SYSTÈME DE FILTRES ---
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    filtre_role = st.selectbox(" 🎯 Filtrer par Rôle :", ["Tous", "Élève", "Enseignant"], key="admin_role")
                with col_f2:
                    liste_classes = ["Toutes"] + sorted(df_users['classe'].unique().tolist())
                    filtre_classe = st.selectbox(" 🏫 Filtrer par Classe :", liste_classes, key="admin_classe")
          
                df_final = df_users.copy()
                if filtre_role != "Tous":
                    df_final = df_final[df_final['role'] == filtre_role]
                if filtre_classe != "Toutes":
                    df_final = df_final[df_final['classe'] == filtre_classe]
                
                # Affichage du tableau de bord
                st.dataframe(df_final, use_container_width=True)
                st.write(f"**Affichage : {len(df_final)} profil(s)**")

                # --- ZONE DE SUPPRESSION ---
                st.divider()
                st.subheader("🗑️ Gestion des comptes")
                col_del, col_space = st.columns([2, 1])
                with col_del:
                    user_to_delete = st.selectbox("Sélectionnez un matricule à supprimer :", df_final['matricule'].tolist())
                    confirm_del = st.checkbox("Confirmer la suppression définitive de ce compte")
                    
                    if st.button("Supprimer l'utilisateur", type="primary"):
                        if confirm_del:
                            cursor = get_cursor(conn)
                            db_execute(cursor, "DELETE FROM utilisateurs WHERE matricule = %s", (user_to_delete,))
                            db_execute(cursor, "DELETE FROM resultats WHERE matricule = %s", (user_to_delete,))
                            conn.commit()
                            st.success(f"✅ Le compte {user_to_delete} a été supprimé avec succès.")
                            st.rerun()
                        else:
                            st.warning("⚠️ Veuillez cocher la case de confirmation.")
            else:
                st.info("Aucun utilisateur enregistré dans la base de données.")
            conn.close()
        except Exception as e:
            st.error(f"Erreur de chargement des utilisateurs : {e}")

    # --- ONGLET 2 : SUIVI DES ACTIVITÉS ---
    with tab2:
        st.subheader("État d'avancement et Notes par Classe")
        try:
            conn = get_db_connection()
            # Jointure via le matricule pour une précision maximale
            query_res = """
                SELECT r.matricule, r.nom_complet, u.classe, r.lecon_id, r.score, r.total_questions, r.date_examen 
                FROM resultats r
                JOIN utilisateurs u ON r.matricule = u.matricule
                ORDER BY r.date_examen DESC
            """
            df_results = db_read_sql(query_res, conn)
            
            if not df_results.empty:
                # Filtre par classe pour l'analyse
                classes_existantes = ["Toutes"] + sorted(df_results['classe'].unique().tolist())
                filtre_classe_res = st.selectbox(" 📂 Voir les résultats de la classe :", classes_existantes)
                
                df_res_filtre = df_results.copy()
                if filtre_classe_res != "Toutes":
                    df_res_filtre = df_res_filtre[df_res_filtre['classe'] == filtre_classe_res]
                
                # Calcul des statistiques de performance
                if not df_res_filtre.empty:
                    avg_score = (df_res_filtre['score'].sum() / df_res_filtre['total_questions'].sum()) * 100
                else:
                    avg_score = 0
                
                c1, c2 = st.columns(2)
                c1.metric(f"Taux de Réussite ({filtre_classe_res})", f"{avg_score:.1f}%")
                c2.metric("Quiz terminés", len(df_res_filtre))
                
                st.dataframe(df_res_filtre, use_container_width=True)
            else:
                st.warning("Aucun score n'a encore été enregistré.")
            conn.close()
        except Exception as e:
            st.error(f"Note : Affichage des résultats bruts (Problème de correspondance entre tables).")
            try:
                conn = get_db_connection()
                df_brut = db_read_sql("SELECT * FROM resultats", conn)
                st.dataframe(df_brut)
                conn.close()
            except:
                st.error("Impossible de charger les données brutes.")






def render_dynamic_lesson(lesson_id):
    load_css()
    content = st.session_state.educational_content[lesson_id]
    st.markdown(f"""
    <div class="an-header">
        <h2>📖 {lesson_id} : {content['titre']}</h2>
        <p>Leçon de Langue des Signes Française · Contenu pédagogique interactif</p>
    </div>
    """, unsafe_allow_html=True)
    col1, col2 = st.columns([2, 1])
    with col1:
        if os.path.exists(content["video"]): st.video(content["video"])
        else: st.warning("Vidéo non disponible localement.")
    with col2:
        st.subheader("Vocabulaires spécifiques")
        st.write(content["mots_cles"])
    st.divider()
    st.write(content["transcription"])

def render_dynamic_quiz(lesson_id):
    load_css()
    
    if st.session_state.user_name is None:
        st.error("🔒 Veuillez vous identifier sur la page Accueil.")
        return
    
    content = st.session_state.educational_content[lesson_id]
    full_name = f"{st.session_state.user_name} {st.session_state.user_surname}"
    
    st.markdown(f"""
    <div class="an-header">
        <h2>✍️ Quiz : {content['titre']}</h2>
        <p>Évaluation de vos connaissances · Répondez à toutes les questions pour valider</p>
    </div>
    """, unsafe_allow_html=True)

    # --- 1. VÉRIFICATION DU VERROUILLAGE (MySQL + Session) ---
    # On vérifie si l'élève a déjà une note enregistrée pour ce quiz
    already_done = check_if_quiz_done_persistently(full_name, lesson_id) or (f"_quiz_done_local_{lesson_id}" in st.session_state)

    if already_done:
        st.warning("✅ Vous avez déjà validé ce quiz.")


        # ── Gestion de l'affichage analyse via session_state ──
        with st.expander("📊 Voir mon analyse de résultats", expanded=False):
            render_student_self_analysis(full_name, lesson_id)

        # --- CORRECTION AVEC IMAGE + RÉPONSE ---
        if content.get("hide_revision", False):
            st.info("🔒 La correction de ce quiz est temporairement masquée par votre enseignant. Elle sera disponible une fois la séance terminée.")
        else:
            with st.expander("🔍 Consulter la correction (Mode Révision)", expanded=True):
                for i, q in enumerate(content["quiz_questions"]):
                    st.markdown(f"""
<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(124,58,237,0.22);
border-radius:12px;padding:14px 16px;margin-bottom:12px;">
    <div style="font-size:0.85rem;font-weight:700;color:#E2E8F0;margin-bottom:10px;">
        Question {i+1} : {q['question']}
    </div>
</div>""", unsafe_allow_html=True)
                    if "image" in q and os.path.exists(q["image"]):
                        st.image(q["image"], width=220)
                    st.success(f"💡 Réponse exacte : **{q['answer']}**")
                    st.divider()
        st.divider()
        if st.button("← Retour", key="btn_retour_quiz"):
            st.session_state["nav_choice"] = "✍️ Quiz"
            st.session_state.pop(f"_quiz_done_local_{lesson_id}", None)
            st.rerun()
        return # On arrête l'exécution ici pour bloquer le formulaire

    # --- 2. AFFICHAGE DU FORMULAIRE (Si le quiz n'est pas encore fait) ---
    with st.form(key=f"quiz_form_{lesson_id}"):
        user_answers = {}
        for i, q in enumerate(content["quiz_questions"]):
            st.write(f"**Question {i+1} : {q['question']}**")
            if "image" in q and os.path.exists(q["image"]):
                st.image(q["image"], width=200)
            
            user_answers[i] = st.radio(
                f"Options pour Q{i+1}:", 
                q["options"], 
                index=None, 
                key=f"q_{lesson_id}_{i}"
            )
        
        submit_button = st.form_submit_button("🚀 Valider et enregistrer mon score")

    # --- 3. TRAITEMENT DU SCORE ET ENREGISTREMENT ---
    if submit_button:
        if None in user_answers.values():
            st.warning("⚠️ Veuillez répondre à toutes les questions avant de valider.")
        else:
            score = 0
            questions_ratees = []
            for i, q in enumerate(content["quiz_questions"]):
                if str(user_answers[i]).strip().lower() == str(q["answer"]).strip().lower():
                    score += 1
                else:
                    questions_ratees.append({
                        "num": i + 1,
                        "question": q["question"],
                        "ta_reponse": user_answers[i],
                        "bonne_reponse": q["answer"]
                    })

            total = len(content["quiz_questions"])

            # Enregistrement permanent
            log_quiz_result(full_name, lesson_id, score, total)
            st.session_state.completed_quizzes[lesson_id] = score


            # Poser les flags et rerun → already_done=True → page correction
            st.session_state[f"_quiz_done_local_{lesson_id}"] = score
            st.session_state.pop(f"_quiz_result_{lesson_id}", None)
            st.rerun()








def log_quiz_result(full_name, lesson_id, score, total):
    """Enregistre le résultat d'un quiz dans la base de données."""
    try:
        conn = get_db_connection()
        if conn is None:
            return
            
        cursor = get_cursor(conn)
        
        matricule = st.session_state.get('user_matricule', 'INCONNU')
        classe = st.session_state.get('user_class', 'N/A')
        cycle = st.session_state.get('user_cycle', 'N/A')
        annee = "2025-2026"

        # Déduire la matière depuis le contenu ou le lesson_id
        matiere = ""
        content = st.session_state.get("educational_content", {}).get(lesson_id, {})
        if content.get("matiere"):
            matiere = content["matiere"]
        elif " - " in lesson_id:
            matiere = lesson_id.split(" - ")[-1].strip()
        
        sql = """INSERT INTO resultats (matricule, nom_complet, lecon_id, matiere, score, total_questions, classe, cycle, annee_scolaire) 
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        
        values = (matricule, full_name, lesson_id, matiere, score, total, classe, cycle, annee)
        
        db_execute(cursor, sql, values)
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as err:
        st.error(f"Erreur lors de l'enregistrement du score : {err}")





def render_analytics():
    load_css()

    # ══ HEADER ══
    st.markdown("""
    <div class="an-header">
        <h2>📊 Pilotage Pédagogique</h2>
        <p>Tableau de bord analytique · Performances · Classement · Messagerie</p>
    </div>
    """, unsafe_allow_html=True)

    # ══ CHARGEMENT DONNÉES ══
    try:
        conn = get_db_connection()
        df = db_read_sql("SELECT * FROM resultats ORDER BY date_examen DESC", conn)
        conn.close()
    except Exception as e:
        st.error(f"Erreur de connexion SQL : {e}")
        return

    if df.empty:
        st.info("ℹ️ En attente des premières évaluations.")
        return

    df['Réussite (%)'] = (df['score'] / df['total_questions']) * 100

    classes_autorisees = [c.strip() for c in st.session_state.get('user_class', "").split(',')]
    if st.session_state.user_role == "Enseignant":
        df_enseignant = df[df['classe'].isin(classes_autorisees)].copy()
    else:
        df_enseignant = df.copy()

    if df_enseignant.empty:
        st.warning("Aucun résultat enregistré pour vos classes.")
        return

    # ── Sélecteur classe ──
    st.markdown('<div class="sec-title">🏫 Choisir une classe</div>', unsafe_allow_html=True)
    target_class = st.selectbox("", sorted(df_enseignant['classe'].unique()), label_visibility="collapsed")
    df_c = df_enseignant[df_enseignant['classe'] == target_class].copy()

    # ── KPI ──
    moy_globale    = df_c['Réussite (%)'].mean()
    nb_eleves      = df_c['nom_complet'].nunique()
    nb_evaluations = len(df_c)
    taux_reussite  = (df_c['Réussite (%)'] >= 60).mean() * 100

    st.markdown(f"""
    <div class="kpi-grid">
        <div class="kpi-card c1">
            <div class="kpi-icon">🎯</div>
            <div class="kpi-val">{moy_globale:.1f}%</div>
            <div class="kpi-lbl">Moyenne générale</div>
        </div>
        <div class="kpi-card c2">
            <div class="kpi-icon">👥</div>
            <div class="kpi-val">{nb_eleves}</div>
            <div class="kpi-lbl">Élèves actifs</div>
        </div>
        <div class="kpi-card c3">
            <div class="kpi-icon">📝</div>
            <div class="kpi-val">{nb_evaluations}</div>
            <div class="kpi-lbl">Évaluations</div>
        </div>
        <div class="kpi-card c4">
            <div class="kpi-icon">✅</div>
            <div class="kpi-val">{taux_reussite:.0f}%</div>
            <div class="kpi-lbl">Taux de réussite</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ══ DIAGRAMMES ══
    st.markdown(
        '<div class="sec-title">📈 Analyse des performances '
        '<span class="sec-pill">GRAPHIQUES</span></div>',
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)

    with col1:
        stats_lecon = (df_c.groupby('lecon_id')['Réussite (%)']
                       .mean().reset_index()
                       .sort_values('Réussite (%)', ascending=True))
        fig_bar = px.bar(
            stats_lecon, x='Réussite (%)', y='lecon_id', orientation='h',
            title="📚 Moyenne par Module",
            color='Réussite (%)',
            color_continuous_scale=[[0,'#EF4444'],[0.5,'#F59E0B'],[1,'#10B981']],
            range_x=[0, 108],
            text=stats_lecon['Réussite (%)'].apply(lambda v: f"{v:.0f}%")
        )
        fig_bar.update_traces(textposition='outside', marker_line_width=0)
        fig_bar.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            font_family='DM Sans', title_font_size=13,
            coloraxis_showscale=False,
            xaxis=dict(showgrid=True, gridcolor='#F1F5F9', zeroline=False),
            yaxis=dict(showgrid=False),
            margin=dict(l=8, r=8, t=38, b=8), height=300
        )
        st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

    with col2:
        df_c['Niveau'] = pd.cut(
            df_c['Réussite (%)'],
            bins=[0, 49.99, 74.99, 100],
            labels=['Critique', 'Moyen', 'Acquis']
        )
        fig_pie = px.pie(
            df_c, names='Niveau',
            title="🎊 Performance de la classe",
            color='Niveau',
            color_discrete_map={'Critique':'#EF4444', 'Moyen':'#F59E0B', 'Acquis':'#10B981'},
            hole=0.42
        )
        fig_pie.update_traces(
            textposition='inside', textinfo='percent+label',
            marker=dict(line=dict(color='white', width=3)),
            pull=[0.04, 0.04, 0.04]
        )
        fig_pie.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            font_family='DM Sans', title_font_size=13,
            showlegend=True,
            legend=dict(orientation='h', yanchor='bottom', y=-0.2, xanchor='center', x=0.5),
            margin=dict(l=8, r=8, t=38, b=40), height=340
        )
        st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})

    # Courbe temporelle
    try:
        df_t = df_c.copy()
        df_t['date_examen'] = pd.to_datetime(df_t['date_examen'])
        df_tg = df_t.groupby('date_examen')['Réussite (%)'].mean().reset_index()
        if len(df_tg) > 1:
            fig_line = px.line(
                df_tg, x='date_examen', y='Réussite (%)',
                title="📅 Évolution de la moyenne",
                markers=True
            )
            fig_line.update_traces(
                line=dict(color='#1A56DB', width=2.5),
                marker=dict(color='#7C3AED', size=7, line=dict(color='white', width=2))
            )
            fig_line.add_hrect(y0=75, y1=105, fillcolor='rgba(16,185,129,.07)',  line_width=0)
            fig_line.add_hrect(y0=50, y1=75,  fillcolor='rgba(245,158,11,.07)', line_width=0)
            fig_line.add_hrect(y0=0,  y1=50,  fillcolor='rgba(239,68,68,.07)',  line_width=0)
            fig_line.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                font_family='DM Sans', title_font_size=13,
                xaxis=dict(showgrid=False, zeroline=False),
                yaxis=dict(showgrid=True, gridcolor='#F1F5F9', range=[0,105]),
                margin=dict(l=8, r=8, t=38, b=8), height=250
            )
            st.plotly_chart(fig_line, use_container_width=True, config={'displayModeBar': False})
    except Exception:
        pass

    # ── Appréciation ──
    if moy_globale >= 75:
        st.markdown("""
        <div class="apprec ok">
            <div class="apprec-ico">🏅</div>
            <div>
                <div class="apprec-ttl" style="color:#065F46;">Excellence pédagogique</div>
                <div class="apprec-sub">Les notions LSF sont maîtrisées. Classe en très bonne progression.</div>
            </div>
        </div>""", unsafe_allow_html=True)
    elif moy_globale >= 50:
        st.markdown("""
        <div class="apprec mid">
            <div class="apprec-ico">⚡</div>
            <div>
                <div class="apprec-ttl" style="color:#92400E;">Résultats moyens</div>
                <div class="apprec-sub">Des progrès sont visibles. Renforcer la pratique gestuelle et les modules faibles.</div>
            </div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="apprec bad">
            <div class="apprec-ico">🚨</div>
            <div>
                <div class="apprec-ttl" style="color:#991B1B;">Alerte pédagogique</div>
                <div class="apprec-sub">Niveau global fragile. Une remédiation urgente est recommandée.</div>
            </div>
        </div>""", unsafe_allow_html=True)

    # ══ PODIUM TOP 5 ══
    st.markdown(
        '<div class="sec-title">🏆 Podium de la classe '
        '<span class="sec-pill">TOP 5</span></div>',
        unsafe_allow_html=True
    )

    classement = (df_c.assign(nom_complet=df_c['nom_complet'].astype(str).str.strip())
                  .groupby('nom_complet')
                  .agg(moyenne=('Réussite (%)', 'mean'), nb_eval=('Réussite (%)', 'count'))
                  .sort_values('moyenne', ascending=False)
                  .reset_index())

    top5   = classement.head(5).reset_index(drop=True)
    n      = len(top5)
    pcls   = ['p1','p2','p3','p4','p5']
    emojis = ['🥇','🥈','🥉','4️⃣','5️⃣']
    labels = ['1er','2ème','3ème','4ème','5ème']

    if n == 0:
        st.info("Aucun résultat disponible pour le podium.")
    else:
        # Ordre visuel : 2e | 1er | 3e | 4e | 5e (seulement si assez d'élèves)
        if n >= 2:
            mapping = {0:1, 1:0, 2:2, 3:3, 4:4}
        else:
            mapping = {0:0}
        visual_order = [mapping[p] for p in range(n) if mapping.get(p, p) < n]

        parts = []
        for idx in visual_order:
            row   = top5.iloc[idx]
            pc    = pcls[idx]
            score = row['moyenne']
            nom   = row['nom_complet'].split()[0] if row['nom_complet'] else '—'
            crown = "<div class='pod-crown'>👑</div>" if idx == 0 else ''
            block = (
                f"<div class='pod-block'>"
                f"{crown}"
                f"<div class='pod-avatar {pc}'>{emojis[idx]}</div>"
                f"<div class='pod-name'>{nom}</div>"
                f"<div class='pod-pct {pc}'>{score:.1f}%</div>"
                f"<div class='pod-bar {pc}'>{labels[idx]}</div>"
                f"</div>"
            )
            parts.append(block)

        html_podium = "<div class='podium-stage'>" + "".join(parts) + "</div>"
        st.markdown(html_podium, unsafe_allow_html=True)

    # ══ CLASSEMENT GLOBAL ══
    st.markdown(
        '<div class="sec-title">📋 Classement complet de tous les élèves</div>',
        unsafe_allow_html=True
    )

    medals = {0:'🥇', 1:'🥈', 2:'🥉'}

    # ── En-tête du tableau ──
    st.markdown("""
    <div class="rank-table">
        <div class="rank-head">
            <div>RANG</div>
            <div>ÉLÈVE</div>
            <div style="text-align:center">MOY.</div>
            <div style="text-align:center">ÉVALS</div>
            <div>BARRE</div>
        </div>""", unsafe_allow_html=True)

    # ── Lignes du tableau (une par st.markdown pour éviter les bugs d'échappement) ──
    for i, row in classement.iterrows():
        rang  = medals.get(i, f"#{i+1}")
        score = row['moyenne']
        color = "#10B981" if score >= 75 else ("#F59E0B" if score >= 50 else "#EF4444")
        width = int(score)
        delay = min(i * 0.04, 1.2)
        st.markdown(f"""
        <div class="rank-row" style="animation-delay:{delay:.2f}s">
            <div class="rk-pos"  style="color:{color}">{rang}</div>
            <div class="rk-name">{row['nom_complet']}</div>
            <div class="rk-pct"  style="color:{color}">{score:.1f}%</div>
            <div class="rk-cnt">{int(row['nb_eval'])}</div>
            <div class="mini-bar">
                <div class="mini-fill" style="width:{width}%;background:{color}"></div>
            </div>
        </div>""", unsafe_allow_html=True)

    # ── Fermeture du tableau ──
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ══ DIAGNOSTIC INDIVIDUEL ══
    st.markdown('<div class="sec-title">👤 Diagnostic individuel</div>', unsafe_allow_html=True)
    eleve_sel = st.selectbox("Sélectionner un élève :", sorted(df_c['nom_complet'].unique()))
    if eleve_sel:
        df_e = df_c[df_c['nom_complet'] == eleve_sel].copy()

        # ── Récupérer le type de déficience depuis la table utilisateurs ──
        type_deficient = "—"
        try:
            conn_diag = get_db_connection()
            cursor_diag = get_cursor(conn_diag)
            db_execute(cursor_diag,
                "SELECT type_maladie FROM utilisateurs WHERE (nom || ' ' || prenom) = %s OR (prenom || ' ' || nom) = %s",
                (eleve_sel.strip(), eleve_sel.strip()))
            row_diag = row_to_dict(cursor_diag.fetchone())
            if row_diag and row_diag.get("type_maladie"):
                type_deficient = row_diag["type_maladie"]
            conn_diag.close()
        except Exception:
            pass

        # ── Bandeau type de déficience ──
        st.markdown(f"""
        <div style="background:#FFFFFF;border:1px solid #D1D5DB;
                    border-radius:10px;padding:10px 16px;margin-bottom:12px;
                    font-size:0.88rem;color:#111827;">
            🏥 <strong>Type de déficience :</strong>&nbsp; {type_deficient}
        </div>
        """, unsafe_allow_html=True)

        # Ajouter la colonne matière si absente : la déduire du lecon_id
        if 'matiere' not in df_e.columns:
            df_e['matiere'] = df_e['lecon_id'].apply(
                lambda x: x.split(" - ")[-1].strip() if " - " in str(x) else "—"
            )

        # Afficher les colonnes disponibles (matiere en priorité)
        cols_affich = ['date_examen', 'matiere', 'lecon_id', 'score', 'total_questions', 'Réussite (%)']
        cols_dispo = [c for c in cols_affich if c in df_e.columns]
        st.dataframe(df_e[cols_dispo], hide_index=True, use_container_width=True)

        lacunes = df_e[df_e['Réussite (%)'] < 60]
        if not lacunes.empty:
            for _, r in lacunes.iterrows():
                mat_val = r.get('matiere', '')
                mat_str = f" ({mat_val})" if mat_val and mat_val not in ('', '—') else ""
                st.error(f"⚠️ Difficulté sur **{r['lecon_id']}**{mat_str} — Score : {r['Réussite (%)']:.0f}%")
        else:
            st.success("✅ Aucune difficulté majeure détectée pour cet élève.")

    # ══ MESSAGERIE ENSEIGNANT → DIRECTION ══
    st.markdown("""
    <div class="msg-hero">
        <h3>✉️ Messagerie Enseignant</h3>
        <p>Signalez un problème ou transmettez une information à la direction</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="msg-card">', unsafe_allow_html=True)

    with st.form("form_message_enseignant", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="msg-lbl">👤 Votre identité</div>', unsafe_allow_html=True)
            expediteur = st.text_input(
                "Expéditeur",
                value=f"{st.session_state.get('user_name','')} {st.session_state.get('user_surname','')}",
                label_visibility="collapsed"
            )
        with c2:
            st.markdown('<div class="msg-lbl">🏫 Classe concernée</div>', unsafe_allow_html=True)
            classe = st.text_input(
                "Classe",
                value=st.session_state.get('user_class',''),
                label_visibility="collapsed"
            )

        st.markdown('<div class="msg-lbl" style="margin-top:12px">📌 Sujet</div>', unsafe_allow_html=True)
        sujet = st.selectbox("Sujet", [
            "🔴 Problème de comportement",
            "📘 Difficulté d'apprentissage",
            "📅 Absence répétée",
            "📉 Résultats alarmants",
            "💬 Autre"
        ], label_visibility="collapsed")

        st.markdown('<div class="msg-lbl" style="margin-top:12px">📝 Détails</div>', unsafe_allow_html=True)
        contenu = st.text_area(
            "Contenu", height=130,
            placeholder="Décrivez la situation : nom de l'élève, faits observés, date...",
            label_visibility="collapsed"
        )

        st.markdown("""
        <div class="msg-tip">
            💡 Votre message sera transmis à la direction et marqué
            <strong>non lu</strong> jusqu'à sa prise en charge.
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        envoyer = st.form_submit_button("📨 Envoyer à la direction", use_container_width=True)

        if envoyer:
            if contenu.strip():
                try:
                    conn = get_db_connection()
                    cursor = get_cursor(conn)
                    db_execute(cursor,
                        "INSERT INTO messages (expediteur, classe, sujet, contenu) VALUES (%s, %s, %s, %s)",
                        (expediteur, classe, sujet.split(" ", 1)[-1], contenu)
                    )
                    conn.commit()
                    conn.close()
                    st.success("✅ Message transmis à la direction avec succès !")
                except Exception as e:
                    st.error(f"Erreur lors de l'envoi : {e}")
            else:
                st.warning("⚠️ Veuillez rédiger un message avant d'envoyer.")

    st.markdown('</div>', unsafe_allow_html=True)





def render_director_space():
    load_css()
    st.markdown("""
    <div class="an-header">
        <h2>🔑 Espace Enseignant</h2>
        <p>Gestion des modules</p>
    </div>
    """, unsafe_allow_html=True)

    # Vérification du mot de passe pour l'accès
    password = st.text_input("Code secret d'accès :", type="password")
    
    if password == "1234":
        st.success("Accès autorisé aux outils d'administration.")
        
        # --- SECTION 0 : MODE ÉVALUATION ---
        st.markdown("### 🎯 Mode Évaluation (Activation du Quiz)")
        with st.expander("Activer / Désactiver le Quiz par leçon", expanded=True):
            u_nom_eval = st.session_state.get('user_name')
            lecons_eval = [l_id for l_id, info in st.session_state.educational_content.items()
                           if info.get("auteur") == u_nom_eval]
            if lecons_eval:
                st.info("ℹ️ Le quiz est **masqué par défaut**. Activez le mode évaluation pour le rendre visible aux élèves.")
                changed = False
                for l_id in lecons_eval:
                    info = st.session_state.educational_content[l_id]
                    current = info.get("eval_mode", False)
                    label = f"📖 **{l_id}** — {info.get('titre', '')} · {info.get('matiere', '')} · Classe : {info.get('classe', '')}"
                    new_val = st.toggle(label, value=current, key=f"eval_toggle_{l_id}")
                    if new_val != current:
                        st.session_state.educational_content[l_id]["eval_mode"] = new_val
                        changed = True
                if changed:
                    save_data(st.session_state.educational_content)
                    st.toast("✅ Mode évaluation mis à jour !")
                    st.rerun()
            else:
                st.info("Aucune leçon publiée par vous pour le moment.")

        st.divider()

        # --- SECTION 0b : MASQUER LE MODE RÉVISION ---
        st.markdown("### 🙈 Mode Révision (Affichage de la correction après quiz)")
        with st.expander("Masquer / Afficher la correction pour les élèves", expanded=False):
            u_nom_rev = st.session_state.get('user_name')
            lecons_rev = [l_id for l_id, info in st.session_state.educational_content.items()
                          if info.get("auteur") == u_nom_rev]
            if lecons_rev:
                st.info("ℹ️ Quand activé (🔴), les élèves qui ont fini le quiz **ne voient pas** la correction — utile pendant une séance où d'autres élèves composent encore.")
                changed_rev = False
                for l_id in lecons_rev:
                    info = st.session_state.educational_content[l_id]
                    current_rev = info.get("hide_revision", False)
                    label_rev = f"🙈 **{l_id}** — {info.get('titre', '')} · {info.get('matiere', '')} · Classe : {info.get('classe', '')}  ({'Correction masquée 🔴' if current_rev else 'Correction visible 🟢'})"
                    new_rev = st.toggle(label_rev, value=current_rev, key=f"rev_toggle_{l_id}")
                    if new_rev != current_rev:
                        st.session_state.educational_content[l_id]["hide_revision"] = new_rev
                        changed_rev = True
                if changed_rev:
                    save_data(st.session_state.educational_content)
                    st.toast("✅ Mode révision mis à jour !")
                    st.rerun()
            else:
                st.info("Aucune leçon publiée par vous pour le moment.")

        st.divider()

        # --- SECTION 1 : SUPPRESSION DE MODULE ---
        st.markdown("### 🗑️ Gestion du contenu existant")
        with st.expander("Cliquez pour voir les leçons à supprimer", expanded=False):
            u_nom = st.session_state.get('user_name')
            lecons = [id for id, info in st.session_state.educational_content.items() 
                 if info.get('auteur') == u_nom]

            if lecons:
                # Grouper par matière pour le selectbox
                _matieres_supp = {}
                for lid in lecons:
                    mat = st.session_state.educational_content[lid].get("matiere", "Sans matière")
                    _matieres_supp.setdefault(mat, []).append(lid)
                _mat_supp = st.selectbox("Matière :", list(_matieres_supp.keys()), key="sel_mat_supp")
                _lecons_supp = _matieres_supp.get(_mat_supp, [])
                col_sel, col_btn = st.columns([3, 1])
                with col_sel:
                    a_suppr = st.selectbox("Sélectionnez la leçon à retirer :", _lecons_supp)
                with col_btn:
                    st.write(" ") # Alignement
                    if st.button("Supprimer", type="primary"):
                        if a_suppr in st.session_state.educational_content:
                            del st.session_state.educational_content[a_suppr]
                            save_data(st.session_state.educational_content)
                            st.toast(f"✅ Leçon '{a_suppr}' supprimée avec succès !")
                            st.rerun()
            else:
                st.info("Aucun contenu disponible pour la suppression.")

        st.divider()

        # --- SECTION 2 : MODIFICATION DE MODULE ---
        st.markdown("### ✏️ Modifier une leçon existante")
        with st.expander("Cliquez pour modifier une leçon", expanded=False):
            u_nom = st.session_state.get('user_name')
            lecons_modif = [id for id, info in st.session_state.educational_content.items()
                            if info.get('auteur') == u_nom]

            if lecons_modif:
                _matieres_mod = {}
                for lid in lecons_modif:
                    mat = st.session_state.educational_content[lid].get("matiere", "Sans matière")
                    _matieres_mod.setdefault(mat, []).append(lid)
                _mat_mod = st.selectbox("Matière :", list(_matieres_mod.keys()), key="sel_mat_mod")
                _lecons_mod = _matieres_mod.get(_mat_mod, [])
                lecon_a_modif = st.selectbox("Sélectionnez la leçon à modifier :", _lecons_mod, key="select_modif")

                if lecon_a_modif:
                    contenu = st.session_state.educational_content[lecon_a_modif]

                    with st.form("modifier_lecon_form", clear_on_submit=False):
                        col1, col2 = st.columns(2)
                        with col1:
                            new_titre = st.text_input("Titre du cours :", value=contenu.get("titre", ""))
                            new_classe = st.text_input("Classe ciblée :", value=contenu.get("classe", ""))
                            new_video = st.text_input("Lien de la vidéo :", value=contenu.get("video", ""))
                            new_matiere = st.text_input("Matière :", value=contenu.get("matiere", "Français"), placeholder="ex: Français, LSF...").strip()
                        with col2:
                            new_mots = st.text_input("Mots clés :", value=contenu.get("mots_cles", ""))

                        new_trans = st.text_area("Contenu textuel / Transcription :", value=contenu.get("transcription", ""), height=150)

                        st.markdown("---")
                        st.write("**Modifier le Quiz associé**")
                        st.info("Format : Question | Option1, Option2 | Réponse Correcte | image/signe.jpg")

                        # Reconstituer le texte du quiz existant
                        questions_existantes = contenu.get("quiz_questions", [])
                        quiz_text_existant = ""
                        for q in questions_existantes:
                            opts = ", ".join(q.get("options", []))
                            ans = q.get("answer", "")
                            img = q.get("image", "")
                            ligne = f"{q['question']} | {opts} | {ans}"
                            if img:
                                ligne += f" | {img}"
                            quiz_text_existant += ligne + "\n"

                        new_quiz_text = st.text_area("Questions du quiz :", value=quiz_text_existant.strip(), height=150)

                        submitted_modif = st.form_submit_button("💾 Enregistrer les modifications")

                        if submitted_modif:
                            try:
                                questions_list = []
                                lines = new_quiz_text.strip().split('\n')
                                for i, line in enumerate(lines):
                                    parts = line.split('|')
                                    if len(parts) >= 3:
                                        q_data = {
                                            "id": i + 1,
                                            "question": parts[0].strip(),
                                            "options": [o.strip() for o in parts[1].split(',')],
                                            "answer": parts[2].strip()
                                        }
                                        if len(parts) == 4:
                                            q_data["image"] = parts[3].strip()
                                        questions_list.append(q_data)

                                if questions_list:
                                    st.session_state.educational_content[lecon_a_modif] = {
                                        "titre": new_titre,
                                        "classe": new_classe.strip().upper(),
                                        "matiere": new_matiere,
                                        "video": new_video,
                                        "mots_cles": new_mots,
                                        "transcription": new_trans,
                                        "auteur": contenu.get("auteur"),
                                        "date_publication": contenu.get("date_publication"),
                                        "eval_mode": contenu.get("eval_mode", False),
                                        "hide_revision": contenu.get("hide_revision", False),
                                        "quiz_questions": questions_list
                                    }
                                    save_data(st.session_state.educational_content)
                                    st.toast(f"✅ Leçon '{lecon_a_modif}' modifiée avec succès !")
                                    st.rerun()
                                else:
                                    st.error("❌ Format de quiz invalide. Vérifiez vos questions.")
                            except Exception as e:
                                st.error(f"❌ Erreur : {e}")
            else:
                st.info("Aucune leçon disponible pour la modification.")

        st.divider()

        # --- SECTION 3 : AJOUT DE NOUVEAU MODULE ---
        st.subheader("➕ Publier un nouveau module")
        
        with st.form("new_content_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                l_matiere = st.text_input("Matière :", placeholder="ex: LSF, Français, Mathématiques...").strip()
                # Calcul automatique du numéro de leçon par matière
                _u_nom_create = st.session_state.get("user_name")
                if l_matiere:
                    _lecons_matiere = [
                        lid for lid, info in st.session_state.educational_content.items()
                        if info.get("auteur") == _u_nom_create and info.get("matiere", "").strip().lower() == l_matiere.lower()
                    ]
                    _next_num = len(_lecons_matiere) + 1
                    l_id = f"Leçon {_next_num} - {l_matiere}"
                    st.info(f"📌 ID généré : **{l_id}**")
                else:
                    l_id = ""
                    st.caption("Saisissez la matière pour générer l'ID automatiquement.")
                l_titre  = st.text_input("Titre du cours (ex: Les Animaux 🐘) :")
                l_classe = st.text_input("Classe ciblée (ex: CM2-A, SIL, 3ème) :")
            
            with col2:
                l_video = st.text_input("Lien de la vidéo :", value="defaut.mp4")
                l_mots = st.text_input("Mots clés (ex: Animal, Chien, Chat) :")
            
            l_trans = st.text_area("Contenu textuel / Transcription de la leçon :")
            
            st.markdown("---")
            st.write("**Configuration du Quiz associé**")
            st.info("Format : Question | Option1, Option2 | Réponse Correcte | image/signe.jpg")
            multi_q_text = st.text_area("Entrez les questions (une par ligne) :", height=150)

            submitted = st.form_submit_button("🚀 Publier le module")

            if submitted:
                if l_id and l_titre and l_classe and multi_q_text:
                    try:
                        questions_list = []
                        lines = multi_q_text.strip().split('\n')
                        for i, line in enumerate(lines):
                            parts = line.split('|')
                            if len(parts) >= 3:
                                q_data = {
                                    "id": i + 1,
                                    "question": parts[0].strip(),
                                    "options": [o.strip() for o in parts[1].split(',')],
                                    "answer": parts[2].strip()
                                }
                                if len(parts) == 4:
                                    q_data["image"] = parts[3].strip()
                                questions_list.append(q_data)

                        if questions_list:
                            st.session_state.educational_content[l_id] = {
                                "titre": l_titre,
                                "classe": l_classe.strip().upper(),
                                "matiere": l_matiere or "Français",
                                "video": l_video,
                                "mots_cles": l_mots,
                                "transcription": l_trans,
                                "auteur": st.session_state.get('user_name'), 
                                "date_publication": str(datetime.now()),
                                "eval_mode": False,
                                "quiz_questions": questions_list     
                            }
                            save_data(st.session_state.educational_content)
                            st.session_state.pop("_preview_matiere", None)
                            st.toast(f"✅ Module '{l_id}' publié pour les {l_classe.upper()} !")
                            st.rerun()
                        else:
                            st.error("Format de quiz invalide.")
                    except Exception as e:
                        st.error(f"Erreur lors de la création : {e}")
                else:
                    st.warning("⚠️ Veuillez remplir tous les champs obligatoires (ID, Titre, Classe, Quiz).")
    elif password != "":
        st.error("Code secret incorrect.")



def render_translator():
    load_css()
    st.markdown("""
    <div class="an-header">
        <h2>🤟 Traducteur LSF Intelligent</h2>
        <p>Traduction Français → LSF · Analyse morphosyntaxique · Dictionnaire intégré</p>
    </div>
    """, unsafe_allow_html=True)

    # 1. DICTIONNAIRE DE PHRASES FIXES (Prioritaire sur l'IA)
    grammaire_lsf = {
        "quel est ton travail": "travail a-toi quoi",
        "comment tu t'appelles": "nom toi quoi",
        "je t'aime": "je-t-aime",
        "est-ce que ca va": "ca-va",
        "s'il vous plaît": "s-il-vous-plait",
        "excusez moi": "excuser-moi",
        "de rien": "de-rien",
        "bon appétit": "bon-appetit",
        "au revoir": "au-revoir",
        "week end": "week-end",
        "bonjour à tous": "bonjour-a-tous",
    }

    # 2. ZONE DE SAISIE
    text_input = st.text_input("Phrase à traduire :", placeholder="Ex: Je mange une pomme demain").lower().strip()

    if text_input:
        # ÉTAPE DE TRADUCTION
        if text_input in grammaire_lsf:
            phrase_lsf = grammaire_lsf[text_input]
            methode = "Dictionnaire (Règle fixe)"
        else:
            # Appel de l'Intelligence Embarquée
            phrase_lsf = transformer_en_syntaxe_lsf(text_input)
            methode = "IA Embarquée (Analyse Morphosyntaxique)"
        
        st.write(f"⚙️ Méthode : {methode}")
        st.success(f"Structure LSF : **{phrase_lsf}**")

        # Découpage final pour chercher les images
        words = phrase_lsf.split()
        
        # 3. DÉTECTION DES NOMS PROPRES dans la phrase originale
        doc_original = nlp(text_input)
        # ── Détection des prénoms/noms de personnes ──
        # Un mot est un prénom si :
        # 1. spaCy le reconnaît comme entité PER
        # 2. OU token PROPN avec majuscule initiale dans la phrase originale
        # 3. OU suit un mot de salutation (Bonjour, Bienvenue, Salut...)
        salutations = {"bienvenue","bonjour","salut","bonsoir","allô","voici","voilà","appelle","appelles","s'appelle"}
        noms_personnes = set()

        # Entités NER
        for ent in doc_original.ents:
            if ent.label_ == "PER":
                noms_personnes.add(ent.text.lower())

        # PROPN avec majuscule
        for tok in doc_original:
            if tok.pos_ == "PROPN" and tok.text[0].isupper():
                noms_personnes.add(tok.text.lower())

        # Mot qui suit une salutation ou "s'appelle"
        for i, tok in enumerate(doc_original):
            if tok.text.lower() in salutations and i + 1 < len(doc_original):
                suivant = doc_original[i + 1]
                if suivant.pos_ in ("PROPN","NOUN") or suivant.text[0].isupper():
                    noms_personnes.add(suivant.text.lower())

        # Construction de la liste d'affichage
        display_items = []
        for word in words:
            fichiers_possibles = [
                (f"{word}.mp4", "video"),
                (f"{word}.mp4", "video"),
                (f"{word}.jpg", "image"),
                (f"{word}.png", "image"),
                (f"{word}.jpeg", "image")
            ]
            trouve = False
            for chemin, type_f in fichiers_possibles:
                if os.path.exists(chemin):
                    display_items.append(("mot", word, chemin, type_f))
                    trouve = True
                    break
            if not trouve:
                # Dactylologie UNIQUEMENT pour les prénoms/noms de personnes
                if word.lower() in noms_personnes:
                    lettres_trouvees = []
                    for lettre in word.lower():
                        chemin_lettre = None
                        for ext in ["jpg", "png", "jpeg"]:
                            chemin_test = f"{lettre}.{ext}"
                            if os.path.exists(chemin_test):
                                chemin_lettre = chemin_test
                                break
                        lettres_trouvees.append((lettre, chemin_lettre))
                    display_items.append(("dactylo", word, lettres_trouvees))
                else:
                    display_items.append(("absent", word, None, None))

        # Calcul du nombre total de colonnes
        nb_cols = 0
        for item in display_items:
            if item[0] == "mot":
                nb_cols += 1
            elif item[0] == "dactylo":
                nb_cols += len(item[2])
            else:  # absent
                nb_cols += 1
        nb_cols += 1  # ressort final

        if nb_cols > 1:
            all_cols = st.columns([1] * (nb_cols - 1) + [3], gap="small")
            col_idx = 0
            for item in display_items:
                if item[0] == "mot":
                    _, word, chemin, type_f = item
                    with all_cols[col_idx]:
                        if type_f == "video":
                            st.video(chemin)
                        else:
                            st.image(chemin, width=100)
                        st.caption(word)
                    col_idx += 1
                elif item[0] == "dactylo":
                    _, word, lettres_trouvees = item
                    for lettre, chemin_lettre in lettres_trouvees:
                        with all_cols[col_idx]:
                            if chemin_lettre:
                                st.image(chemin_lettre, width=70)
                            else:
                                st.markdown(f"**{lettre.upper()}**")
                            st.caption(lettre.upper())
                        col_idx += 1
                else:  # absent
                    _, word, _, _ = item
                    with all_cols[col_idx]:
                        st.warning(f"'{word}'")
                        st.caption("Absent")
                    col_idx += 1

    # NOTE POUR LE MÉMOIRE
    st.divider()
    st.markdown("""
    > **Argumentation scientifique :** Le système couple une approche déterministe (dictionnaire) 
    > à une approche probabiliste (NLP via spaCy). Cela permet de traiter la lemmatisation 
    > et la réorganisation syntaxique nécessaire au passage du français à la LSF.
    """)







# --- 3. BARRE LATÉRALE ET NAVIGATION ---


def get_lsf_images_html(texte):
    """Convertit un texte en structure LSF puis génère le HTML des images."""
    import base64
    try:
        structure_lsf = transformer_en_syntaxe_lsf(texte)
    except:
        structure_lsf = texte
    mots = structure_lsf.split()
    html = ""
    for mot in mots:
        for ext in ["jpg", "png", "jpeg"]:
            chemin = f"{mot.lower()}.{ext}"
            if os.path.exists(chemin):
                with open(chemin, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                html += f'''<div style="display:inline-block;text-align:center;margin:4px;">
                    <img src="data:image/{ext};base64,{b64}"
                         style="height:70px;border-radius:8px;border:1px solid #E2E8F0;"/>
                    <div style="font-size:0.7rem;color:#64748B;margin-top:2px;">{mot}</div>
                </div>'''
                break
    return html, structure_lsf


def render_communication():
    """Section communication entre élèves : Chat, Forum, Messagerie privée."""
    load_css()
    st.markdown("""
    <div class="an-header">
        <h2>💬 Espace Communication</h2>
        <p>Chat en direct · Forum · Messagerie privée · Échanges entre élèves</p>
    </div>
    """, unsafe_allow_html=True)

    user_name     = st.session_state.get('user_name', '')
    user_surname  = st.session_state.get('user_surname', '')
    user_class    = st.session_state.get('user_class', '')
    user_role     = st.session_state.get('user_role', '')
    full_name     = f"{user_surname} {user_name}".strip()
    is_teacher    = user_role == "Enseignant"

    # ── Créer les tables si elles n'existent pas ──
    try:
        conn = get_db_connection()
        cursor = get_cursor(conn)
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                auteur TEXT NOT NULL,
                classe TEXT NOT NULL,
                contenu TEXT NOT NULL,
                date_envoi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                epingle INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS forum_sujets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                auteur TEXT NOT NULL,
                classe TEXT NOT NULL,
                titre TEXT NOT NULL,
                contenu TEXT NOT NULL,
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                epingle INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS forum_reponses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sujet_id INTEGER NOT NULL,
                auteur TEXT NOT NULL,
                contenu TEXT NOT NULL,
                date_envoi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS mp_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expediteur TEXT NOT NULL,
                destinataire TEXT NOT NULL,
                classe TEXT NOT NULL,
                contenu TEXT NOT NULL,
                lu INTEGER DEFAULT 0,
                date_envoi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """ if DB_MODE == "sqlite" else "")

        if DB_MODE == "mysql":
            for sql in [
                """CREATE TABLE IF NOT EXISTS chat_messages (
                    id INT AUTO_INCREMENT PRIMARY KEY, auteur VARCHAR(100),
                    classe VARCHAR(50), contenu TEXT,
                    date_envoi TIMESTAMP DEFAULT CURRENT_TIMESTAMP, epingle TINYINT DEFAULT 0)""",
                """CREATE TABLE IF NOT EXISTS forum_sujets (
                    id INT AUTO_INCREMENT PRIMARY KEY, auteur VARCHAR(100),
                    classe VARCHAR(50), titre VARCHAR(200), contenu TEXT,
                    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP, epingle TINYINT DEFAULT 0)""",
                """CREATE TABLE IF NOT EXISTS forum_reponses (
                    id INT AUTO_INCREMENT PRIMARY KEY, sujet_id INT, auteur VARCHAR(100),
                    contenu TEXT, date_envoi TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
                """CREATE TABLE IF NOT EXISTS mp_messages (
                    id INT AUTO_INCREMENT PRIMARY KEY, expediteur VARCHAR(100),
                    destinataire VARCHAR(100), classe VARCHAR(50), contenu TEXT,
                    lu TINYINT DEFAULT 0, date_envoi TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
            ]:
                cursor.execute(sql)
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Erreur initialisation tables : {e}")
        return

    # ── Onglets ──
    tab_chat, tab_forum, tab_mp = st.tabs(["💬 Chat en direct", "📋 Forum", "✉️ Messagerie privée"])

    # ════════════════════════════════════════════
    # ONGLET 1 : CHAT EN DIRECT
    # ════════════════════════════════════════════
    with tab_chat:
        st.markdown(f"**Classe : {user_class}**")

        # Affichage des messages
        try:
            conn = get_db_connection()
            cursor = get_cursor(conn, dictionary=True)
            db_execute(cursor, """
                SELECT * FROM chat_messages
                WHERE classe = %s
                ORDER BY epingle DESC, date_envoi ASC
            """, (user_class,))
            msgs = rows_to_dict(cursor.fetchall())
            conn.close()
        except:
            msgs = []

        chat_container = st.container()
        with chat_container:
            if not msgs:
                st.info("Aucun message pour l'instant. Sois le premier à écrire !")
            for msg in msgs:
                is_me = msg['auteur'] == full_name
                can_act = is_me or is_teacher
                epingle = msg.get('epingle', 0)

                bg    = "#EFF6FF" if is_me else "#F8FAFC"
                align = "flex-end" if is_me else "flex-start"
                bord  = "#BFDBFE" if is_me else "#E2E8F0"
                pin_badge = "📌 " if epingle else ""

                signes_html, _ = get_lsf_images_html(msg['contenu'])

                # Clé session pour afficher/masquer le menu de ce message
                menu_key = f"show_menu_chat_{msg['id']}"
                edit_key = f"edit_chat_{msg['id']}"
                if menu_key not in st.session_state:
                    st.session_state[menu_key] = False
                if edit_key not in st.session_state:
                    st.session_state[edit_key] = False

                # Bulle du message
                col_msg, col_btn = (st.columns([10, 1]) if is_me
                                    else st.columns([1, 10]))
                with (col_msg if is_me else col_btn):
                    st.markdown(f"""
                        <div style="display:flex;justify-content:{align};margin-bottom:4px;">
                            <div style="max-width:100%;background:{bg};border:1px solid {bord};
                                        border-radius:14px;padding:10px 16px;">
                                <div style="font-size:0.75rem;color:#64748B;margin-bottom:4px;">
                                    {pin_badge}<b>{msg['auteur']}</b> · {str(msg['date_envoi'])[:16]}
                                </div>
                                <div style="font-size:0.95rem;color:#0F172A;">{msg['contenu']}</div>
                                {"<div style='margin-top:8px;padding-top:8px;border-top:1px solid #E2E8F0;'>"+signes_html+"</div>" if signes_html else ""}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                # Bouton ⋮ pour ouvrir le menu contextuel
                with (col_btn if is_me else col_msg):
                    if can_act:
                        if st.button("⋮", key=f"menu_btn_chat_{msg['id']}",
                                     help="Options du message"):
                            st.session_state[menu_key] = not st.session_state[menu_key]
                            st.session_state[edit_key] = False

                # Menu contextuel (style WhatsApp)
                if can_act and st.session_state[menu_key]:
                    with st.container():
                        st.markdown(f"""
                            <div style="background:#fff;border:1px solid #E2E8F0;border-radius:12px;
                                        padding:6px;margin:0 0 8px {'0' if not is_me else 'auto'};
                                        max-width:220px;box-shadow:0 4px 16px rgba(0,0,0,0.10);">
                            </div>
                        """, unsafe_allow_html=True)
                        mc1, mc2, mc3 = st.columns(3)
                        with mc1:
                            label_pin = "📌\nDésép." if epingle else "📌\nÉpingler"
                            if st.button(label_pin, key=f"pin2_chat_{msg['id']}",
                                         use_container_width=True):
                                try:
                                    conn = get_db_connection()
                                    cursor = get_cursor(conn)
                                    db_execute(cursor,
                                        "UPDATE chat_messages SET epingle = %s WHERE id = %s",
                                        (0 if epingle else 1, msg['id']))
                                    conn.commit(); conn.close()
                                    st.session_state[menu_key] = False
                                    st.rerun()
                                except Exception as e:
                                    st.error(e)
                        with mc2:
                            if is_me and st.button("✏️\nModifier",
                                                   key=f"edit_btn_chat_{msg['id']}",
                                                   use_container_width=True):
                                st.session_state[edit_key] = True
                                st.session_state[menu_key] = False
                        with mc3:
                            if st.button("🗑️\nSuppr.", key=f"del2_chat_{msg['id']}",
                                         use_container_width=True):
                                try:
                                    conn = get_db_connection()
                                    cursor = get_cursor(conn)
                                    db_execute(cursor,
                                        "DELETE FROM chat_messages WHERE id = %s", (msg['id'],))
                                    conn.commit(); conn.close()
                                    st.session_state[menu_key] = False
                                    st.rerun()
                                except Exception as e:
                                    st.error(e)

                # Zone de modification inline
                if is_me and st.session_state[edit_key]:
                    with st.form(f"edit_form_chat_{msg['id']}", clear_on_submit=True):
                        new_text = st.text_input("Modifier le message :",
                                                  value=msg['contenu'])
                        c_save, c_cancel = st.columns(2)
                        with c_save:
                            if st.form_submit_button("💾 Enregistrer"):
                                if new_text.strip():
                                    try:
                                        conn = get_db_connection()
                                        cursor = get_cursor(conn)
                                        db_execute(cursor,
                                            "UPDATE chat_messages SET contenu = %s WHERE id = %s",
                                            (new_text.strip(), msg['id']))
                                        conn.commit(); conn.close()
                                        st.session_state[edit_key] = False
                                        st.rerun()
                                    except Exception as e:
                                        st.error(e)
                        with c_cancel:
                            if st.form_submit_button("✖ Annuler"):
                                st.session_state[edit_key] = False
                                st.rerun()

        # Formulaire d'envoi
        st.divider()
        with st.form("chat_form", clear_on_submit=True):
            nouveau_msg = st.text_input("Écris ton message...", placeholder="Bonjour tout le monde !")
            envoyer = st.form_submit_button("Envoyer ✉️")
            if envoyer and nouveau_msg.strip():
                try:
                    conn = get_db_connection()
                    cursor = get_cursor(conn)
                    db_execute(cursor,
                        "INSERT INTO chat_messages (auteur, classe, contenu) VALUES (%s, %s, %s)",
                        (full_name, user_class, nouveau_msg.strip()))
                    conn.commit(); conn.close(); st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")

    # ════════════════════════════════════════════
    # ONGLET 2 : FORUM
    # ════════════════════════════════════════════
    with tab_forum:
        # Nouveau sujet
        with st.expander("➕ Créer un nouveau sujet"):
            with st.form("forum_form", clear_on_submit=True):
                titre = st.text_input("Titre du sujet :")
                contenu_forum = st.text_area("Description :", height=80)
                video_lsf = st.file_uploader("📹 Vidéo en LSF (optionnel) :", type=["mp4", "mov", "avi"])
                traduction_manuelle = st.text_input("✍️ Ta traduction en français (si vidéo) :", placeholder="Ex: Bonjour je m'appelle Pascal")
                if st.form_submit_button("Publier le sujet"):
                    if titre.strip() and contenu_forum.strip():
                        video_path = ""
                        if video_lsf:
                            import uuid
                            video_path = f"forum_{uuid.uuid4().hex[:8]}.mp4"
                            os.makedirs("videos", exist_ok=True)
                            with open(video_path, "wb") as vf:
                                vf.write(video_lsf.read())
                        contenu_final = contenu_forum.strip()
                        if video_path:
                            contenu_final += f"||VIDEO:{video_path}"
                        if traduction_manuelle.strip():
                            contenu_final += f"||TRAD:{traduction_manuelle.strip()}"
                        try:
                            conn = get_db_connection()
                            cursor = get_cursor(conn)
                            db_execute(cursor,
                                "INSERT INTO forum_sujets (auteur, classe, titre, contenu) VALUES (%s, %s, %s, %s)",
                                (full_name, user_class, titre.strip(), contenu_final))
                            conn.commit(); conn.close(); st.rerun()
                        except Exception as e:
                            st.error(e)
                    else:
                        st.warning("Remplis le titre et la description.")

        # Liste des sujets
        try:
            conn = get_db_connection()
            cursor = get_cursor(conn, dictionary=True)
            db_execute(cursor,
                "SELECT * FROM forum_sujets WHERE classe = %s ORDER BY epingle DESC, date_creation DESC",
                (user_class,))
            sujets = rows_to_dict(cursor.fetchall())
            conn.close()
        except:
            sujets = []

        if not sujets:
            st.info("Aucun sujet pour l'instant.")
        for sujet in sujets:
            epingle = sujet.get('epingle', 0)
            pin_icon = "📌 " if epingle else ""

            # Parser contenu : texte || vidéo || traduction
            contenu_raw = sujet['contenu']
            contenu_texte = contenu_raw
            video_path_sujet = ""
            trad_video = ""
            if "||VIDEO:" in contenu_raw:
                parts = contenu_raw.split("||VIDEO:")
                contenu_texte = parts[0]
                reste = parts[1]
                if "||TRAD:" in reste:
                    video_path_sujet, trad_video = reste.split("||TRAD:", 1)
                else:
                    video_path_sujet = reste

            with st.expander(f"{pin_icon}{sujet['titre']} — par {sujet['auteur']} · {str(sujet['date_creation'])[:16]}"):
                st.markdown(f"_{contenu_texte}_")

                # Vidéo LSF
                if video_path_sujet and os.path.exists(video_path_sujet):
                    st.video(video_path_sujet)

                # Traduction (ajoutée par l'élève ou l'enseignant)
                if trad_video:
                    st.markdown(f"""
                        <div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:10px;
                                    padding:10px 16px;margin-top:6px;">
                            <span style="font-size:0.78rem;color:#15803D;font-weight:700;">
                                🤟 Traduction :
                            </span>
                            <span style="color:#166534;font-size:0.95rem;"> {trad_video}</span>
                        </div>
                    """, unsafe_allow_html=True)
                elif video_path_sujet:
                    st.caption("⏳ Aucune traduction pour l'instant.")

                # Enseignant : ajouter ou modifier la traduction (son nom n'apparaît pas)
                if is_teacher and video_path_sujet:
                    with st.form(f"trad_form_{sujet['id']}", clear_on_submit=True):
                        label = "✏️ Modifier la traduction :" if trad_video else "✏️ Ajouter la traduction :"
                        nouvelle_trad = st.text_input(label, value=trad_video)
                        if st.form_submit_button("💾 Enregistrer la traduction"):
                            if nouvelle_trad.strip():
                                try:
                                    # Reconstruire le contenu avec la nouvelle traduction
                                    nouveau_contenu = contenu_texte
                                    if video_path_sujet:
                                        nouveau_contenu += f"||VIDEO:{video_path_sujet}||TRAD:{nouvelle_trad.strip()}"
                                    conn = get_db_connection()
                                    cursor = get_cursor(conn)
                                    db_execute(cursor,
                                        "UPDATE forum_sujets SET contenu = %s WHERE id = %s",
                                        (nouveau_contenu, sujet['id']))
                                    conn.commit(); conn.close()
                                    st.success("✅ Traduction enregistrée !")
                                    st.rerun()
                                except Exception as e:
                                    st.error(e)

                # Modération enseignant
                if is_teacher:
                    c1, c2 = st.columns(2)
                    with c1:
                        label_p = "📌 Désépingler" if epingle else "📌 Épingler"
                        if st.button(label_p, key=f"pin_forum_{sujet['id']}"):
                            try:
                                conn = get_db_connection()
                                cursor = get_cursor(conn)
                                db_execute(cursor, "UPDATE forum_sujets SET epingle = %s WHERE id = %s",
                                           (0 if epingle else 1, sujet['id']))
                                conn.commit(); conn.close(); st.rerun()
                            except Exception as e:
                                st.error(e)
                    with c2:
                        if st.button("🗑️ Supprimer sujet", key=f"del_forum_{sujet['id']}"):
                            try:
                                conn = get_db_connection()
                                cursor = get_cursor(conn)
                                db_execute(cursor, "DELETE FROM forum_sujets WHERE id = %s", (sujet['id'],))
                                db_execute(cursor, "DELETE FROM forum_reponses WHERE sujet_id = %s", (sujet['id'],))
                                conn.commit(); conn.close(); st.rerun()
                            except Exception as e:
                                st.error(e)

                st.markdown("**Réponses :**")
                # Réponses existantes
                try:
                    conn = get_db_connection()
                    cursor = get_cursor(conn, dictionary=True)
                    db_execute(cursor,
                        "SELECT * FROM forum_reponses WHERE sujet_id = %s ORDER BY date_envoi ASC",
                        (sujet['id'],))
                    reponses = rows_to_dict(cursor.fetchall())
                    conn.close()
                except:
                    reponses = []

                for rep in reponses:
                    is_me_rep = rep['auteur'] == full_name
                    bg_rep = "#EFF6FF" if is_me_rep else "#F8FAFC"
                    st.markdown(f"""
                        <div style="background:{bg_rep};border:1px solid #E2E8F0;
                                    border-radius:10px;padding:8px 14px;margin-bottom:6px;">
                            <b style="font-size:0.8rem;color:#64748B;">{rep['auteur']} · {str(rep['date_envoi'])[:16]}</b><br>
                            <span style="color:#0F172A;">{rep['contenu']}</span>
                        </div>
                    """, unsafe_allow_html=True)
                    if is_teacher:
                        if st.button("🗑️", key=f"del_rep_{rep['id']}"):
                            try:
                                conn = get_db_connection()
                                cursor = get_cursor(conn)
                                db_execute(cursor, "DELETE FROM forum_reponses WHERE id = %s", (rep['id'],))
                                conn.commit(); conn.close(); st.rerun()
                            except Exception as e:
                                st.error(e)

                # Formulaire réponse
                with st.form(f"rep_form_{sujet['id']}", clear_on_submit=True):
                    rep_txt = st.text_input("Ta réponse :", key=f"rep_input_{sujet['id']}")
                    if st.form_submit_button("Répondre"):
                        if rep_txt.strip():
                            try:
                                conn = get_db_connection()
                                cursor = get_cursor(conn)
                                db_execute(cursor,
                                    "INSERT INTO forum_reponses (sujet_id, auteur, contenu) VALUES (%s, %s, %s)",
                                    (sujet['id'], full_name, rep_txt.strip()))
                                conn.commit(); conn.close(); st.rerun()
                            except Exception as e:
                                st.error(e)

    # ════════════════════════════════════════════
    # ONGLET 3 : MESSAGERIE PRIVÉE
    # ════════════════════════════════════════════
    with tab_mp:
        # Récupérer les élèves de la même classe
        try:
            conn = get_db_connection()
            cursor = get_cursor(conn, dictionary=True)
            db_execute(cursor,
                "SELECT nom, prenom FROM utilisateurs WHERE classe = %s AND matricule != %s",
                (user_class, st.session_state.get('user_matricule', '')))
            camarades_raw = rows_to_dict(cursor.fetchall())
            conn.close()
            camarades = [f"{c['nom']} {c['prenom']}" for c in camarades_raw]
        except:
            camarades = []

        if not camarades:
            st.info("Aucun camarade dans ta classe pour l'instant.")
        else:
            destinataire = st.selectbox("Envoyer un message à :", camarades)

            # Conversation
            try:
                conn = get_db_connection()
                cursor = get_cursor(conn, dictionary=True)
                db_execute(cursor, """
                    SELECT * FROM mp_messages
                    WHERE (expediteur = %s AND destinataire = %s)
                       OR (expediteur = %s AND destinataire = %s)
                    ORDER BY date_envoi ASC
                """, (full_name, destinataire, destinataire, full_name))
                conv = rows_to_dict(cursor.fetchall())
                # Marquer comme lus
                db_execute(cursor, """
                    UPDATE mp_messages SET lu = 1
                    WHERE destinataire = %s AND expediteur = %s AND lu = 0
                """, (full_name, destinataire))
                conn.commit(); conn.close()
            except:
                conv = []

            # Afficher la conversation
            if not conv:
                st.info(f"Commence une conversation avec {destinataire} !")
            for mp in conv:
                is_me_mp = mp['expediteur'] == full_name
                bg_mp    = "#EFF6FF" if is_me_mp else "#F8FAFC"
                align_mp = "flex-end" if is_me_mp else "flex-start"
                bord_mp  = "#BFDBFE" if is_me_mp else "#E2E8F0"

                signes_mp, _ = get_lsf_images_html(mp['contenu'])

                mp_menu_key = f"show_menu_mp_{mp['id']}"
                mp_edit_key = f"edit_mp_{mp['id']}"
                if mp_menu_key not in st.session_state:
                    st.session_state[mp_menu_key] = False
                if mp_edit_key not in st.session_state:
                    st.session_state[mp_edit_key] = False

                col_mp, col_mp_btn = (st.columns([10, 1]) if is_me_mp
                                      else st.columns([1, 10]))
                with (col_mp if is_me_mp else col_mp_btn):
                    st.markdown(f"""
                        <div style="display:flex;justify-content:{align_mp};margin-bottom:4px;">
                            <div style="max-width:100%;background:{bg_mp};border:1px solid {bord_mp};
                                        border-radius:14px;padding:10px 16px;">
                                <div style="font-size:0.75rem;color:#64748B;margin-bottom:3px;">
                                    <b>{mp['expediteur']}</b> · {str(mp['date_envoi'])[:16]}
                                </div>
                                <div style="font-size:0.95rem;color:#0F172A;">{mp['contenu']}</div>
                                {"<div style='margin-top:8px;padding-top:8px;border-top:1px solid #E2E8F0;'>"+signes_mp+"</div>" if signes_mp else ""}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                with (col_mp_btn if is_me_mp else col_mp):
                    if is_me_mp:
                        if st.button("⋮", key=f"menu_btn_mp_{mp['id']}",
                                     help="Options"):
                            st.session_state[mp_menu_key] = not st.session_state[mp_menu_key]
                            st.session_state[mp_edit_key] = False

                # Menu contextuel MP
                if is_me_mp and st.session_state[mp_menu_key]:
                    mc1, mc2, mc3 = st.columns(3)
                    with mc1:
                        if st.button("📌\nÉpingler", key=f"pin_mp_{mp['id']}",
                                     use_container_width=True):
                            st.info("Épinglage non disponible en MP.")
                            st.session_state[mp_menu_key] = False
                    with mc2:
                        if st.button("✏️\nModifier", key=f"edit_btn_mp_{mp['id']}",
                                     use_container_width=True):
                            st.session_state[mp_edit_key] = True
                            st.session_state[mp_menu_key] = False
                    with mc3:
                        if st.button("🗑️\nSuppr.", key=f"del_mp_{mp['id']}",
                                     use_container_width=True):
                            try:
                                conn = get_db_connection()
                                cursor = get_cursor(conn)
                                db_execute(cursor,
                                    "DELETE FROM mp_messages WHERE id = %s", (mp['id'],))
                                conn.commit(); conn.close()
                                st.session_state[mp_menu_key] = False
                                st.rerun()
                            except Exception as e:
                                st.error(e)

                # Modification inline MP
                if is_me_mp and st.session_state[mp_edit_key]:
                    with st.form(f"edit_form_mp_{mp['id']}", clear_on_submit=True):
                        new_mp = st.text_input("Modifier :", value=mp['contenu'])
                        cs, cc = st.columns(2)
                        with cs:
                            if st.form_submit_button("💾 Enregistrer"):
                                if new_mp.strip():
                                    try:
                                        conn = get_db_connection()
                                        cursor = get_cursor(conn)
                                        db_execute(cursor,
                                            "UPDATE mp_messages SET contenu = %s WHERE id = %s",
                                            (new_mp.strip(), mp['id']))
                                        conn.commit(); conn.close()
                                        st.session_state[mp_edit_key] = False
                                        st.rerun()
                                    except Exception as e:
                                        st.error(e)
                        with cc:
                            if st.form_submit_button("✖ Annuler"):
                                st.session_state[mp_edit_key] = False
                                st.rerun()

            # Formulaire envoi MP
            st.divider()
            with st.form("mp_form", clear_on_submit=True):
                mp_txt = st.text_input("Ton message :", placeholder=f"Message à {destinataire}...")
                if st.form_submit_button("Envoyer ✉️"):
                    if mp_txt.strip():
                        try:
                            conn = get_db_connection()
                            cursor = get_cursor(conn)
                            db_execute(cursor,
                                "INSERT INTO mp_messages (expediteur, destinataire, classe, contenu) VALUES (%s, %s, %s, %s)",
                                (full_name, destinataire, user_class, mp_txt.strip()))
                            conn.commit(); conn.close(); st.rerun()
                        except Exception as e:
                            st.error(f"Erreur : {e}")

            # Compteur messages non lus
            try:
                conn = get_db_connection()
                cursor = get_cursor(conn)
                db_execute(cursor,
                    "SELECT COUNT(*) FROM mp_messages WHERE destinataire = %s AND lu = 0",
                    (full_name,))
                nb_non_lus_mp = cursor.fetchone()[0]
                conn.close()
                if nb_non_lus_mp > 0:
                    st.info(f"📬 Tu as **{nb_non_lus_mp}** message(s) non lu(s) au total.")
            except:
                pass
apply_custom_styles()

with st.sidebar:
    st.markdown("""
        <div style="padding:12px 0 4px 8px;">
            <span style="font-family:'DM Sans',sans-serif;font-size:0.85rem;
                         letter-spacing:0.18em;text-transform:uppercase;
                         background:linear-gradient(135deg,#00d4ff,#1A56DB,#7C3AED);
                         -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                         background-clip:text;font-weight:800;">
                DEAF AWARENESS
            </span>
        </div>
    """, unsafe_allow_html=True)
    if os.path.exists("logo_lsf.png"):
        st.image("logo_lsf.png", width=120)
    else:
        st.markdown("<h3 style='color:white;'>🏫 LSF PLATEFORME</h3>", unsafe_allow_html=True)
    st.divider()

# Initialisation du menu par défaut
menu = ["Accueil"]

u_role      = st.session_state.get("user_role")
u_class     = st.session_state.get("user_class")
u_matricule = st.session_state.get("user_matricule")

if u_matricule:
    u_nom = st.session_state.get("user_name", "")

    lecons_cours = []
    lecons_quiz  = []
    for l_id, info in st.session_state.educational_content.items():
        auteur_lecon = info.get("auteur", "")
        classe_lecon = info.get("classe", "")
        if u_role == "Enseignant" and auteur_lecon == u_nom:
            lecons_cours.append(l_id)
            lecons_quiz.append(l_id)
        elif u_role == "Élève" and classe_lecon == u_class:
            if info.get("eval_mode", False):
                lecons_quiz.append(l_id)
            else:
                lecons_cours.append(l_id)

    st.session_state["_lecons_cours"] = lecons_cours
    st.session_state["_lecons_quiz"]  = lecons_quiz

    eval_active = u_role == "Élève" and any(
        info.get("eval_mode", False) and info.get("classe", "") == u_class
        for info in st.session_state.educational_content.values()
    )

    if lecons_cours:
        menu.append("📚 Cours")
    if lecons_quiz:
        menu.append("✍️ Quiz")

    if not eval_active:
        menu.append("Reconnaissance en Direct 🤚")
        menu.append("Traducteur LSF 🤟")
        menu.append("💬 Communication")
    if u_role == "Enseignant":
        menu.append("Espace Enseignant")
        menu.append("Analyse des Résultats 📊")

    # ── Mode examen : forcer la navigation directe vers le quiz ──
    # Ne pas forcer si l'élève vient juste de se connecter (nav_choice = "Accueil")
    # ou s'il est en train de se déconnecter.
    _just_logged_in = st.session_state.get("nav_choice") == "Accueil"
    if eval_active and lecons_quiz and not _just_logged_in:
        if len(lecons_quiz) == 1:
            st.session_state["_quiz_actif"] = lecons_quiz[0]
            if st.session_state.get("nav_choice") not in ("__quiz__",):
                if "_last_sidebar_key" not in st.session_state:
                    st.session_state["_last_sidebar_key"] = "Accueil"
                st.session_state["nav_choice"] = "__quiz__"
        else:
            if st.session_state.get("nav_choice") not in ("__quiz__", "✍️ Quiz"):
                st.session_state["nav_choice"] = "✍️ Quiz"

# ── Navigation st.radio stylisée Premium ──

_user_name  = st.session_state.get("user_name", "Visiteur")
_user_class = st.session_state.get("user_class", "") or ""
_is_logged  = bool(st.session_state.get("user_matricule"))

# ── Comptage messages non lus (reset si on est sur Communication) ──
_unread_count = 0
if _is_logged:
    _prev_choice = st.session_state.get("nav_choice", "Accueil")
    if _prev_choice == "💬 Communication":
        # On vient d'entrer dans Communication → badge à 0
        _unread_count = 0
        if "comm_badge_cleared" not in st.session_state:
            st.session_state.comm_badge_cleared = True
    else:
        st.session_state.pop("comm_badge_cleared", None)
        _unread_count = get_unread_messages_count()

# Initialisation — ne pas ecraser les pages internes
_pages_internes_init = ("__quiz__", "__lecon__")
if "nav_choice" not in st.session_state:
    st.session_state.nav_choice = menu[0] if menu else "Accueil"
elif st.session_state.nav_choice not in menu and st.session_state.nav_choice not in _pages_internes_init:
    st.session_state.nav_choice = menu[0] if menu else "Accueil"

# ── Labels affichés (emoji nettoyé pour éviter doublons) ──
_icons = {
    "Accueil": "🏠",
    "Reconnaissance en Direct 🤚": "🤚",
    "Traducteur LSF 🤟": "🤟",
    "💬 Communication": "💬",
    "Espace Enseignant": "🎓",
    "Analyse des Résultats 📊": "📊",
}
_menu_labels = []
for _item in menu:
    if _item.startswith("📖"):
        _menu_labels.append("📖 " + _item[2:].strip())
    elif _item.startswith("✍️"):
        _menu_labels.append("✍️ " + _item[2:].strip())
    else:
        _ico = _icons.get(_item, "")
        if _ico and _item.startswith(_ico):
            _menu_labels.append(_ico + " " + _item[len(_ico):].strip())
        else:
            _menu_labels.append(_item)

# Index actif
_active_idx = 0
if st.session_state.nav_choice in menu:
    _active_idx = menu.index(st.session_state.nav_choice)

# ── Index de l'item Communication dans le menu ──
_comm_label_idx = next((i for i, lbl in enumerate(_menu_labels) if "Communication" in lbl), -1)

st.markdown("""
<style>
/* ══════════════════════════════════════════
   SIDEBAR GLOBAL — texte blanc partout
══════════════════════════════════════════ */
section[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div {
    color: #FFFFFF !important;
}

/* ══════════════════════════════════════════
   RADIO — cache titre
══════════════════════════════════════════ */
section[data-testid="stSidebar"] div[data-testid="stRadio"] > label:first-child {
    display: none !important;
}

/* ── Conteneur vertical ── */
section[data-testid="stSidebar"] div[data-testid="stRadio"] > div {
    display: flex;
    flex-direction: column;
    gap: 3px;
}

/* ── Chaque item nav ── */
section[data-testid="stSidebar"] div[data-testid="stRadio"] label {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    width: 100% !important;
    padding: 10px 13px !important;
    border-radius: 11px !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    background: rgba(255,255,255,0.04) !important;
    color: #FFFFFF !important;
    font-size: 0.83rem !important;
    font-weight: 500 !important;
    cursor: pointer !important;
    transition: background 0.22s ease, border-color 0.22s ease,
                box-shadow 0.22s ease, transform 0.15s ease !important;
    margin-bottom: 0 !important;
    position: relative !important;
    overflow: hidden !important;
    letter-spacing: 0.01em !important;
}

/* Shimmer au hover via pseudo-element */
section[data-testid="stSidebar"] div[data-testid="stRadio"] label::after {
    content: "" !important;
    position: absolute !important;
    top: 0; left: -75% !important;
    width: 50% !important; height: 100% !important;
    background: linear-gradient(120deg,
        transparent 0%, rgba(255,255,255,0.12) 50%, transparent 100%) !important;
    transform: skewX(-20deg) !important;
    opacity: 0 !important;
    transition: opacity 0.2s !important;
    pointer-events: none !important;
}

section[data-testid="stSidebar"] div[data-testid="stRadio"] label:hover::after {
    opacity: 1 !important;
    left: 125% !important;
    transition: left 0.55s ease, opacity 0.2s !important;
}

section[data-testid="stSidebar"] div[data-testid="stRadio"] label:hover {
    background: rgba(26,86,219,0.22) !important;
    border-color: rgba(26,86,219,0.55) !important;
    color: #FFFFFF !important;
    transform: translateX(3px) !important;
    box-shadow: 0 2px 12px rgba(26,86,219,0.20) !important;
}

/* ── Item actif — dégradé bleu→violet ── */
section[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) {
    background: linear-gradient(135deg, #1A56DB 0%, #7C3AED 100%) !important;
    border-color: transparent !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 20px rgba(124,58,237,0.45),
                inset 0 1px 0 rgba(255,255,255,0.15) !important;
    transform: translateX(0px) !important;
    letter-spacing: 0.02em !important;
}

/* Point lumineux pulsant sur l'item actif */
section[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked)::before {
    content: "" !important;
    position: absolute !important;
    right: 10px !important;
    top: 50% !important;
    transform: translateY(-50%) !important;
    width: 7px !important; height: 7px !important;
    border-radius: 50% !important;
    background: rgba(255,255,255,0.9) !important;
    box-shadow: 0 0 8px 3px rgba(255,255,255,0.5) !important;
    animation: nav-pulse 2s ease-in-out infinite !important;
}

@keyframes nav-pulse {
    0%, 100% { opacity: 0.9; box-shadow: 0 0 8px 3px rgba(255,255,255,0.5); }
    50%       { opacity: 0.4; box-shadow: 0 0 4px 1px rgba(255,255,255,0.2); }
}

/* ── Cache TOUS les cercles radio natifs ── */
section[data-testid="stSidebar"] div[data-testid="stRadio"] input[type="radio"] {
    display: none !important;
}
section[data-testid="stSidebar"] div[data-testid="stRadio"] label > div:first-child {
    display: none !important;
}
section[data-testid="stSidebar"] div[data-testid="stRadio"] label > p {
    margin: 0 !important;
}
section[data-testid="stSidebar"] div[data-testid="stRadio"] div[data-testid="stMarkdownContainer"] ~ div,
section[data-testid="stSidebar"] div[data-testid="stRadio"] span[data-baseweb="radio"] > div:first-child {
    display: none !important;
}

/* ══════════════════════════════════════════
   BADGE notification (span injecté par JS)
══════════════════════════════════════════ */
.nav-badge {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-width: 19px !important;
    height: 19px !important;
    padding: 0 5px !important;
    border-radius: 99px !important;
    background: linear-gradient(135deg, #FF4B6E, #FF8C42) !important;
    color: #fff !important;
    font-size: 0.68rem !important;
    font-weight: 800 !important;
    margin-left: auto !important;
    margin-right: 18px !important;
    box-shadow: 0 2px 8px rgba(255,75,110,0.55) !important;
    animation: badge-pop 0.35s cubic-bezier(0.34,1.56,0.64,1) both,
               badge-glow 2.2s ease-in-out 0.4s infinite !important;
    position: relative !important;
    z-index: 10 !important;
}

@keyframes badge-pop {
    0%   { transform: scale(0); opacity: 0; }
    100% { transform: scale(1); opacity: 1; }
}

@keyframes badge-glow {
    0%, 100% { box-shadow: 0 2px 8px rgba(255,75,110,0.55); }
    50%       { box-shadow: 0 2px 16px rgba(255,75,110,0.9), 0 0 0 4px rgba(255,75,110,0.15); }
}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    # ── Carte profil ──
    if _is_logged:
        st.markdown(f"""
<div style="background:linear-gradient(135deg,rgba(0,212,255,0.10),rgba(124,58,237,0.12));
border:1px solid rgba(124,58,237,0.28);border-radius:14px;padding:12px 14px;margin-bottom:14px;">
  <div style="font-size:0.83rem;font-weight:800;background:linear-gradient(135deg,#00d4ff,#7C3AED);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">
    👤 {_user_name}</div>
  <div style="font-size:0.70rem;color:#94A3B8 !important;margin-top:4px;">🏫 {_user_class or 'Classe non définie'}</div>
</div>""", unsafe_allow_html=True)

    else:
        st.markdown("""
<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(148,163,184,0.2);
border-radius:14px;padding:12px 14px;margin-bottom:14px;">
  <div style="font-size:0.82rem;color:#FFFFFF !important;font-weight:600;">👤 Visiteur</div>
  <div style="font-size:0.70rem;color:#94A3B8 !important;margin-top:4px;">Veuillez vous connecter</div>
</div>""", unsafe_allow_html=True)

    components.html("""
<style>
  #live-clock-widget {
    background: linear-gradient(135deg, rgba(0,212,255,0.07), rgba(124,58,237,0.09));
    border: 1px solid rgba(124,58,237,0.22);
    border-radius: 12px;
    padding: 9px 14px;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: 'DM Sans', 'Segoe UI', sans-serif;
  }
  #live-clock-icon {
    font-size: 1.1rem;
    flex-shrink: 0;
  }
  #live-clock-time {
    font-size: 1.05rem;
    font-weight: 800;
    background: linear-gradient(135deg, #00d4ff, #7C3AED);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: 0.05em;
    line-height: 1.1;
  }
  #live-clock-date {
    font-size: 0.68rem;
    color: #94A3B8;
    margin-top: 2px;
    letter-spacing: 0.02em;
    text-transform: capitalize;
  }
  .clock-sep {
    animation: blink-sep 1s step-start infinite;
    display: inline-block;
  }
  @keyframes blink-sep {
    0%, 49% { opacity: 1; }
    50%, 100% { opacity: 0; }
  }
</style>
<div id="live-clock-widget">
  <span id="live-clock-icon">🕐</span>
  <div>
    <div id="live-clock-time">--<span class="clock-sep">:</span>--</div>
    <div id="live-clock-date">chargement…</div>
  </div>
</div>
<script>
(function() {
  var JOURS = ['Dimanche','Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi'];
  var MOIS  = ['janvier','février','mars','avril','mai','juin',
               'juillet','août','septembre','octobre','novembre','décembre'];
  var ICONS = ['🕐','🕑','🕒','🕓','🕔','🕕','🕖','🕗','🕘','🕙','🕚','🕛'];

  function pad(n) { return String(n).padStart(2, '0'); }

  function tick() {
    var now = new Date();
    var h = now.getHours(), m = now.getMinutes(), s = now.getSeconds();

    document.getElementById('live-clock-icon').textContent = ICONS[h % 12];

    document.getElementById('live-clock-time').innerHTML =
      pad(h) + '<span class="clock-sep">:</span>' + pad(m) +
      '<span style="font-size:0.7em;opacity:0.55;margin-left:2px;">:' + pad(s) + '</span>';

    document.getElementById('live-clock-date').textContent =
      JOURS[now.getDay()] + ' ' + now.getDate() + ' ' + MOIS[now.getMonth()] + ' ' + now.getFullYear();
  }

  tick();
  setInterval(tick, 1000);
})();
</script>
""", height=75)

    st.markdown('<p style="font-size:0.65rem;letter-spacing:0.18em;text-transform:uppercase;color:#94A3B8 !important;font-weight:700;margin:4px 2px 8px 2px;">Navigation</p>', unsafe_allow_html=True)

    _selected_label = st.radio(
        "Navigation",
        options=_menu_labels,
        index=_active_idx,
        label_visibility="collapsed",
        key="nav_radio"
    )

    # ── Injection JS badge + animations premium ──
    if _comm_label_idx >= 0:
        components.html(f"""
<script>
(function injectNavBadge() {{
    const BADGE_COUNT = {_unread_count};
    const COMM_IDX   = {_comm_label_idx};

    function tryInject() {{
        // Cible les labels du radio dans la sidebar
        const sidebar = document.querySelector('section[data-testid="stSidebar"]');
        if (!sidebar) return setTimeout(tryInject, 120);

        const labels = sidebar.querySelectorAll('div[data-testid="stRadio"] label');
        if (!labels || labels.length <= COMM_IDX) return setTimeout(tryInject, 120);

        const target = labels[COMM_IDX];

        // Supprimer badge existant si déjà injecté
        const old = target.querySelector('.nav-badge');
        if (old) old.remove();

        // Injecter seulement si count > 0
        if (BADGE_COUNT > 0) {{
            const badge = document.createElement('span');
            badge.className = 'nav-badge';
            badge.textContent = BADGE_COUNT > 99 ? '99+' : String(BADGE_COUNT);
            target.appendChild(badge);
        }}

        // ── Effet entrée premium sur tous les items (stagger) ──
        const allLabels = sidebar.querySelectorAll('div[data-testid="stRadio"] label');
        allLabels.forEach((lbl, i) => {{
            lbl.style.opacity = '0';
            lbl.style.transform = 'translateX(-14px)';
            lbl.style.transition = 'opacity 0.28s ease, transform 0.28s ease';
            setTimeout(() => {{
                lbl.style.opacity = '1';
                lbl.style.transform = 'translateX(0)';
            }}, 60 + i * 55);
        }});

        // ── Supprime le badge au clic sur Communication ──
        target.addEventListener('click', function() {{
            const b = this.querySelector('.nav-badge');
            if (b) {{
                b.style.transition = 'transform 0.2s ease, opacity 0.2s ease';
                b.style.transform = 'scale(0)';
                b.style.opacity = '0';
                setTimeout(() => b.remove(), 220);
            }}
        }}, {{ once: true }});
    }}

    // Lancer après hydratation Streamlit
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', tryInject);
    }} else {{
        setTimeout(tryInject, 200);
    }}
}})();
</script>
""", height=0)

    # Récupérer la clé réelle depuis le label sélectionné
    _sel_idx = _menu_labels.index(_selected_label) if _selected_label in _menu_labels else 0
    _selected_key = menu[_sel_idx]
    _pages_internes = ("__quiz__", "__lecon__")
    _current_nav = st.session_state.get("nav_choice")

    if _current_nav in _pages_internes:
        # Sur page interne : détecter un vrai clic sidebar en comparant
        # la valeur précédente du radio avec la nouvelle.
        # Si le radio a changé → l'utilisateur a volontairement cliqué ailleurs.
        _prev_radio = st.session_state.get("_prev_nav_radio")
        _radio_changed = (_prev_radio is not None and _selected_label != _prev_radio)
        if _radio_changed:
            st.session_state.nav_choice = _selected_key
    else:
        st.session_state.nav_choice = _selected_key

    # Mémoriser la valeur actuelle du radio pour le prochain rerun
    st.session_state["_prev_nav_radio"] = _selected_label
    st.session_state["_last_sidebar_key"] = _selected_key

# ── Détection des flags boutons (AVANT le routage) ──
# Les flags sont posés par les boutons dans les hubs et pages internes.
# On les intercepte ici, APRÈS le radio sidebar, pour éviter tout écrasement.

# Flag retour vers hub quiz (depuis page analyse)
if st.session_state.pop("_btn_retour_quiz", False):
    st.session_state["nav_choice"] = "✍️ Quiz"

# Flags cartes cours / quiz
_lecons_all = list(st.session_state.get("_lecons_cours", [])) + list(st.session_state.get("_lecons_quiz", []))
for _lid in _lecons_all:
    if st.session_state.pop(f"_btn_cours_{_lid}", False):
        st.session_state["_last_sidebar_key"] = st.session_state.get("nav_choice", menu[0] if menu else "Accueil")
        st.session_state["_lecon_active"] = _lid
        st.session_state["nav_choice"]    = "__lecon__"
        break
    if st.session_state.pop(f"_btn_quiz_{_lid}", False):
        st.session_state["_last_sidebar_key"] = st.session_state.get("nav_choice", menu[0] if menu else "Accueil")
        st.session_state["_prev_nav_radio"] = None  # reset pour détecter vrais clics
        st.session_state["_quiz_actif"] = _lid
        st.session_state["nav_choice"]  = "__quiz__"
        break

choice = st.session_state.nav_choice





# ══════════════════════════════════════════════════════════════════
#   HUB COURS — Hero + cartes cliquables
# ══════════════════════════════════════════════════════════════════
def render_cours_hub():
    load_css()

    lecons = st.session_state.get("_lecons_cours", [])

    st.markdown("""
    <div class="an-header">
        <h2>📚 Mes Cours</h2>
        <p>Sélectionne un cours pour démarrer la leçon · Contenu pédagogique LSF interactif</p>
    </div>
    """, unsafe_allow_html=True)

    if not lecons:
        st.info("Aucun cours disponible pour le moment.")
        return

    contenu = st.session_state.educational_content
    _emojis_mat = {"LSF":"🤟","Français":"📖","Mathématiques":"🔢","Sciences":"🔬","Histoire-Géographie":"🌍","Anglais":"🇬🇧","Éducation civique":"⚖️","Autre":"📚"}

    # Grouper les leçons par matière (ordre d'apparition)
    groupes = {}
    for l_id in lecons:
        mat = contenu.get(l_id, {}).get("matiere", "Français")
        groupes.setdefault(mat, []).append(l_id)

    cols_par_ligne = 3

    for matiere, ids in groupes.items():
        emoji = _emojis_mat.get(matiere, "📚")

        # En-tête de la carte matière
        st.markdown(f"""
<div style="
    background: linear-gradient(135deg, rgba(124,58,237,0.12), rgba(26,86,219,0.08));
    border: 1.5px solid rgba(124,58,237,0.35);
    border-radius: 18px;
    padding: 18px 22px 8px 22px;
    margin: 18px 0 10px 0;
">
    <div style="font-size:1.25rem;font-weight:900;
                background:linear-gradient(135deg,#7C3AED,#1A56DB);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                background-clip:text;margin-bottom:4px;">
        {emoji} Matière : {matiere}
    </div>
    <div style="font-size:0.78rem;color:#94A3B8;margin-bottom:12px;">
        {len(ids)} leçon{'s' if len(ids) > 1 else ''} disponible{'s' if len(ids) > 1 else ''}
    </div>
""", unsafe_allow_html=True)

        # Cartes leçons dans la carte matière
        lignes = [ids[i:i+cols_par_ligne] for i in range(0, len(ids), cols_par_ligne)]
        for ligne in lignes:
            cols = st.columns(cols_par_ligne)
            for col, l_id in zip(cols, ligne):
                info  = contenu.get(l_id, {})
                titre = info.get("titre", l_id)
                with col:
                    st.markdown(f"""
<div style="
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(124,58,237,0.22);
    border-radius: 14px;
    padding: 16px 14px 12px 14px;
    margin-bottom: 10px;
    min-height: 110px;
    display: flex; flex-direction: column; gap: 6px;
">
    <div style="font-size:0.68rem;letter-spacing:0.12em;text-transform:uppercase;
                color:#64748B;font-weight:700;">{l_id}</div>
    <div style="font-size:0.98rem;font-weight:800;
                background:linear-gradient(135deg,#00d4ff,#7C3AED);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                background-clip:text;line-height:1.3;">{titre}</div>
</div>""", unsafe_allow_html=True)
                    if st.button("▶ Ouvrir", key=f"open_cours_{l_id}"):
                        st.session_state[f"_btn_cours_{l_id}"] = True
                        st.rerun()

        # Fermer la carte matière
        st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#   HUB QUIZ — Hero + cartes cliquables
# ══════════════════════════════════════════════════════════════════
def render_quiz_hub():
    load_css()

    lecons = st.session_state.get("_lecons_quiz", [])

    st.markdown("""
    <div class="an-header">
        <h2>✍️ Mes Quiz</h2>
        <p>Sélectionne un quiz pour évaluer tes connaissances · Résultats enregistrés automatiquement</p>
    </div>
    """, unsafe_allow_html=True)

    if not lecons:
        st.info("Aucun quiz disponible pour le moment.")
        return

    contenu   = st.session_state.educational_content
    complets  = st.session_state.get("completed_quizzes", {})
    full_name = f"{st.session_state.get('user_name','')} {st.session_state.get('user_surname','')}".strip()

    cols_par_ligne = 3
    lignes = [lecons[i:i+cols_par_ligne] for i in range(0, len(lecons), cols_par_ligne)]

    for ligne in lignes:
        cols = st.columns(cols_par_ligne)
        for col, l_id in zip(cols, ligne):
            info      = contenu.get(l_id, {})
            titre     = info.get("titre", l_id)
            classe    = info.get("classe", "")
            matiere   = info.get("matiere", "Français")
            _emojis_mat = {"LSF":"🤟","Français":"📖","Mathématiques":"🔢","Sciences":"🔬","Histoire-Géographie":"🌍","Anglais":"🇬🇧","Éducation civique":"⚖️","Autre":"📚"}
            _emoji_mat  = _emojis_mat.get(matiere, "📚")
            nb_q      = len(info.get("quiz_questions", []))
            deja_fait = l_id in complets or check_if_quiz_done_persistently(full_name, l_id)

            if deja_fait:
                score     = complets.get(l_id, "—")
                badge_txt = f"✅ {score}/{nb_q}" if isinstance(score, int) else "✅ Fait"
                badge_col = "rgba(5,150,105,0.18)"
                badge_brd = "rgba(5,150,105,0.40)"
                badge_clr = "#34d399"
            else:
                badge_txt = "🔓 À faire"
                badge_col = "rgba(26,86,219,0.10)"
                badge_brd = "rgba(124,58,237,0.28)"
                badge_clr = "#818CF8"

            with col:
                st.markdown(f"""
<div style="
    background: linear-gradient(135deg, rgba(26,86,219,0.13), rgba(124,58,237,0.10));
    border: 1px solid rgba(124,58,237,0.28);
    border-radius: 16px;
    padding: 20px 18px 14px 18px;
    margin-bottom: 14px;
    min-height: 150px;
    display: flex; flex-direction: column; gap: 8px;
">
    <div style="font-size:0.72rem;letter-spacing:0.12em;text-transform:uppercase;
                color:#64748B;font-weight:700;">{l_id}</div>
    <div style="font-size:0.75rem;font-weight:700;color:#7C3AED;margin-top:2px;">
        {_emoji_mat} {matiere}
    </div>
    <div style="font-size:1.05rem;font-weight:800;
                background:linear-gradient(135deg,#00d4ff,#7C3AED);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                background-clip:text;line-height:1.3;">{titre}</div>
    <div style="font-size:0.75rem;color:#94A3B8;margin-top:2px;">
        🏫 {classe} &nbsp;·&nbsp; ❓ {nb_q} questions
    </div>
    <div style="margin-top:6px;">
        <span style="
            background:{badge_col};border:1px solid {badge_brd};
            color:{badge_clr};border-radius:99px;
            padding:3px 10px;font-size:0.72rem;font-weight:700;">
            {badge_txt}
        </span>
    </div>
</div>""", unsafe_allow_html=True)
                btn_label = "🔍 Voir ma correction" if deja_fait else "▶ Commencer"
                if st.button(btn_label, key=f"open_quiz_{l_id}"):
                    st.session_state[f"_btn_quiz_{l_id}"] = True
                    st.rerun()


# --- 4. ROUTAGE (Affichage des pages) ---
if choice == "Accueil":
    render_home()

# ── Hubs (une entrée sidebar → page de cartes) ──
elif choice == "📚 Cours":
    render_cours_hub()
elif choice == "✍️ Quiz":
    render_quiz_hub()

# ── Pages leçon/quiz individuelles (déclenchées par clic sur une carte) ──
elif choice == "__lecon__":
    l_id = st.session_state.get("_lecon_active")
    if l_id and l_id in st.session_state.educational_content:
        render_dynamic_lesson(l_id)
        st.divider()
        if st.button("← Retour"):
            st.session_state["nav_choice"] = "📚 Cours"
            st.rerun()
    else:
        st.session_state["nav_choice"] = "📚 Cours"
        st.rerun()

elif choice == "__quiz__":
    l_id = st.session_state.get("_quiz_actif")
    if l_id and l_id in st.session_state.educational_content:
        # En mode examen, pas de bouton retour (l'élève ne peut pas s'échapper)
        _info_quiz   = st.session_state.educational_content[l_id]
        _en_examen   = _info_quiz.get("eval_mode", False)
        _u_role_quiz = st.session_state.get("user_role", "")
        render_dynamic_quiz(l_id)
        if not _en_examen or _u_role_quiz == "Enseignant":
            st.divider()
            if st.button("← Retour"):
                st.session_state["nav_choice"] = "✍️ Quiz"
                st.rerun()
    else:
        st.session_state["nav_choice"] = "✍️ Quiz"
        st.rerun()

# ── Autres pages ──
elif choice == "Reconnaissance en Direct 🤚":
    recognize_sign_language()
elif choice == "Espace Enseignant":
    st.session_state.active_tab = "Espace Enseignant"
    render_director_space()
elif choice == "Analyse des Résultats 📊":
    render_analytics()
elif choice == "Traducteur LSF 🤟":
    render_translator()
elif choice == "💬 Communication":
    render_communication()



