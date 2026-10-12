# -*- coding: utf-8 -*-
"""
Rendu HTML commun des emails Nestgreen (récap quotidien / hebdo / mensuel et
alerte des 500 reprises) -> même mise en page partout.

HTML d'email : tables + styles inline (le flex/grid du dashboard web n'est pas
supporté par les clients mail).

Lisibilité mobile (retour du 12/10/2026) :
- un montant ne se coupe jamais sur 2 lignes (espaces insécables dans les milliers,
  white-space:nowrap, tuile "valeur" plus large que la tuile "nombre") ;
- "128 Go" reste solidaire (espace insécable) : "Go" ne se retrouve jamais seul.
"""
import html
import re

MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin",
          "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

GREEN = "#006A38"
LABEL_STYLE = "margin:0;font-size:11.5px;font-weight:600;color:#8B948E;text-transform:uppercase;letter-spacing:0.05em;"


def french_date(d):
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year}"


def fmt_int(n):
    return f"{int(round(n)):,}".replace(",", "&nbsp;")


def fmt_eur(v):
    return f"{fmt_int(v)}&nbsp;&euro;"


def device_label(name):
    """Échappe le nom et colle la capacité à son unité ("128 Go" ne se coupe pas)."""
    return re.sub(r"(\d+) (Go|To)\b", r"\1&nbsp;\2", html.escape(name))


def kpi_tiles(count, value_eur, value_label="Valeur totale"):
    """Deux tuiles côte à côte : nombre (40 %, valeur courte) et montant (60 %, valeur longue)."""
    value_style = "margin:6px 0 0;font-size:24px;font-weight:700;color:#242424;white-space:nowrap;"
    tile = "background:#F0F4F1;border-radius:10px;padding:16px 14px;"
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td width="39%" style="{tile}">
              <p style="{LABEL_STYLE}">Téléphones repris</p>
              <p style="{value_style}">{fmt_int(count)}</p>
            </td>
            <td width="12" style="width:12px;font-size:1px;line-height:1px;">&nbsp;</td>
            <td width="59%" style="{tile}">
              <p style="{LABEL_STYLE}">{value_label}</p>
              <p style="{value_style}">{fmt_eur(value_eur)}</p>
            </td>
          </tr>
        </table>"""


def device_table(by_device, max_rows=None):
    """by_device : [(nom, nombre, valeur €)] déjà triés. max_rows : au-delà, regroupé en 'Autres'."""
    rows = list(by_device)
    others = None
    if max_rows is not None and len(rows) > max_rows:
        rest = rows[max_rows:]
        rows = rows[:max_rows]
        others = (f"Autres appareils ({len(rest)})", sum(c for _, c, _ in rest), sum(e for _, _, e in rest))
    cell = "padding:10px 0;border-bottom:1px solid #E5E5E0;font-size:14px;color:#242424;"
    num = cell.replace("padding:10px 0;", "padding:10px 0 10px 14px;") + "text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;"
    head = "padding:0 0 8px;font-size:11.5px;font-weight:600;color:#8B948E;text-transform:uppercase;letter-spacing:0.05em;"
    body = "".join(
        f"""
          <tr>
            <td style="{cell}">{device_label(name)}</td>
            <td style="{num}">{fmt_int(count)}</td>
            <td style="{num}">{fmt_eur(eur)}</td>
          </tr>"""
        for name, count, eur in rows)
    if others:
        name, count, eur = others
        body += f"""
          <tr>
            <td style="{cell}font-style:italic;">{html.escape(name)}</td>
            <td style="{num}">{fmt_int(count)}</td>
            <td style="{num}">{fmt_eur(eur)}</td>
          </tr>"""
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="{head}">Appareil</td>
            <td width="46" style="{head}padding-left:14px;text-align:right;white-space:nowrap;">Nb</td>
            <td width="86" style="{head}padding-left:14px;text-align:right;white-space:nowrap;">Valeur</td>
          </tr>{body}
        </table>"""


def build_recap_html(eyebrow, title, by_device, total_count, total_eur, max_rows=None, note=None):
    note_html = (f'<p style="margin:0 0 6px;font-size:12px;line-height:1.5;color:#B4402B;">{html.escape(note)}</p>'
                 if note else "")
    return f"""<div style="background:#FAFAFA;padding:32px 16px;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#FFFFFF;border-radius:12px;overflow:hidden;border:1px solid #E5E5E0;">
    <tr>
      <td style="background:{GREEN};padding:20px 28px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="font-size:15px;font-weight:700;color:#FFFFFF;letter-spacing:0.02em;">Nestgreen</td>
            <td style="text-align:right;font-size:13px;color:#E5F0E9;">Grille Reprise</td>
          </tr>
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:32px 28px 8px;">
        <p style="margin:0;font-size:13px;font-weight:600;color:{GREEN};text-transform:uppercase;letter-spacing:0.05em;">{html.escape(eyebrow)}</p>
        <h1 style="margin:8px 0 0;font-size:24px;line-height:1.3;color:#242424;font-weight:700;">{html.escape(title)}</h1>
      </td>
    </tr>
    <tr>
      <td style="padding:20px 28px 8px;">
        {kpi_tiles(total_count, total_eur)}
      </td>
    </tr>
    <tr>
      <td style="padding:12px 28px 28px;">
        {device_table(by_device, max_rows)}
      </td>
    </tr>
    <tr>
      <td style="padding:16px 28px;border-top:1px solid #E5E5E0;">
        {note_html}<p style="margin:0;font-size:12px;color:#8B948E;">Récapitulatif automatique &middot; Grille Reprise Nestgreen</p>
      </td>
    </tr>
  </table>
</div>"""
