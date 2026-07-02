#!/usr/bin/env python3
"""
Generate a static HTML site from the SQLite database.
Single self-contained HTML file with chapter navigation, search, and dark mode.

Output: ocr/shams-al-maarif-static.html
"""

import os
import re
import sqlite3
from pathlib import Path

DB_PATH   = Path("/mnt/c/Working Folder/Research/shams-al-maarif-ocr/ocr/shams_chapters.db")
HTML_PATH = Path("/mnt/c/Working Folder/Research/shams-al-maarif-ocr/ocr/shams-al-maarif-static.html")

HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Shams al-Ma'arif wa Lata'if al-'Awarif — English Translation</title>
<style>
:root {{
  --bg: #faf8f5; --bg2: #f0ece6; --bg3: #e8e2d9;
  --fg: #2c1810; --fg2: #5a3e2b; --fg3: #8a6e5a;
  --accent: #8b4513; --accent2: #a0522d;
  --border: #d4c4b0; --shadow: rgba(0,0,0,0.08);
  --arabic-bg: #fdf6ee; --page-bg: #fff;
}}
.dark {{
  --bg: #1a1410; --bg2: #2a2018; --bg3: #3a3028;
  --fg: #e8ddd0; --fg2: #c4b4a0; --fg3: #8a7a6a;
  --accent: #d4a06a; --accent2: #c49060;
  --border: #4a3a2a; --shadow: rgba(0,0,0,0.3);
  --arabic-bg: #2a2018; --page-bg: #221a12;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: 'Source Serif 4', 'Georgia', serif;
  background: var(--bg); color: var(--fg);
  line-height: 1.7; font-size: 17px;
}}
/* ── Header ── */
.header {{
  background: var(--bg2); border-bottom: 2px solid var(--border);
  padding: 1.5rem 2rem; text-align: center;
  position: sticky; top: 0; z-index: 100;
}}
.header h1 {{
  font-size: 1.6rem; color: var(--accent);
  font-family: 'Poppins', sans-serif;
  margin-bottom: 0.3rem;
}}
.header .subtitle {{ color: var(--fg3); font-size: 0.9rem; font-style: italic; }}
.header .controls {{
  margin-top: 0.8rem; display: flex; gap: 0.8rem;
  justify-content: center; flex-wrap: wrap;
}}
.header input[type="search"] {{
  padding: 0.4rem 0.8rem; border: 1px solid var(--border);
  border-radius: 6px; background: var(--page-bg); color: var(--fg);
  font-size: 0.9rem; width: 280px;
}}
.header button {{
  padding: 0.4rem 0.8rem; border: 1px solid var(--border);
  border-radius: 6px; background: var(--bg3); color: var(--fg2);
  cursor: pointer; font-size: 0.85rem;
}}
.header button:hover {{ background: var(--accent); color: #fff; }}
/* ── Layout ── */
.layout {{ display: flex; min-height: 100vh; }}
/* ── Sidebar ── */
.sidebar {{
  width: 280px; min-width: 280px;
  background: var(--bg2); border-right: 1px solid var(--border);
  padding: 1rem 0; overflow-y: auto;
  position: sticky; top: 0; height: 100vh;
}}
.sidebar h3 {{
  padding: 0.5rem 1rem; font-size: 0.8rem;
  color: var(--fg3); text-transform: uppercase;
  letter-spacing: 0.05em; font-family: 'Poppins', sans-serif;
}}
.sidebar a {{
  display: block; padding: 0.35rem 1rem;
  color: var(--fg2); text-decoration: none;
  font-size: 0.85rem; border-left: 3px solid transparent;
  transition: all 0.15s;
}}
.sidebar a:hover, .sidebar a.active {{
  background: var(--bg3); color: var(--accent);
  border-left-color: var(--accent);
}}
.sidebar a .ch-num {{
  display: inline-block; width: 24px;
  color: var(--fg3); font-size: 0.8rem;
}}
/* ── Main content ── */
.main {{
  flex: 1; max-width: 800px; margin: 0 auto;
  padding: 2rem 2.5rem;
}}
.chapter {{ margin-bottom: 3rem; }}
.chapter-header {{
  border-bottom: 2px solid var(--accent);
  padding-bottom: 0.8rem; margin-bottom: 1.5rem;
}}
.chapter-header h2 {{
  font-size: 1.4rem; color: var(--accent);
  font-family: 'Poppins', sans-serif;
}}
.chapter-header .ch-subtitle {{
  color: var(--fg3); font-size: 0.9rem; font-style: italic;
  margin-top: 0.2rem;
}}
.chapter-header .ch-meta {{
  color: var(--fg3); font-size: 0.8rem; margin-top: 0.3rem;
}}
.page-block {{
  margin-bottom: 2rem; padding: 1rem 1.2rem;
  background: var(--page-bg); border-radius: 8px;
  box-shadow: 0 1px 4px var(--shadow);
}}
.page-num {{
  font-size: 0.75rem; color: var(--fg3);
  font-family: 'JetBrains Mono', monospace;
  margin-bottom: 0.5rem; text-transform: uppercase;
  letter-spacing: 0.05em;
}}
.arabic-section {{
  background: var(--arabic-bg); padding: 0.8rem 1rem;
  border-radius: 6px; margin-bottom: 0.8rem;
  direction: rtl; text-align: right;
  font-size: 1.05rem; line-height: 1.9;
  font-family: 'Amiri', 'Traditional Arabic', serif;
  border: 1px solid var(--border);
}}
.english-section {{
  padding: 0.3rem 0; line-height: 1.75;
}}
.section-label {{
  font-size: 0.7rem; color: var(--fg3);
  text-transform: uppercase; letter-spacing: 0.08em;
  margin-bottom: 0.3rem; font-family: 'Poppins', sans-serif;
}}
/* ── Grid tables ── */
table {{
  border-collapse: collapse; margin: 0.8rem 0;
  font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;
}}
td, th {{
  border: 1px solid var(--border); padding: 0.3rem 0.6rem;
  text-align: center;
}}
/* ── Search results ── */
.search-results {{
  background: var(--bg3); padding: 1rem; border-radius: 8px;
  margin-bottom: 1.5rem; display: none;
}}
.search-results.active {{ display: block; }}
.search-result-item {{
  padding: 0.5rem 0; border-bottom: 1px solid var(--border);
  cursor: pointer;
}}
.search-result-item:hover {{ color: var(--accent); }}
.search-result-item .sr-page {{ font-size: 0.8rem; color: var(--fg3); }}
mark {{ background: #f0c060; color: #000; padding: 0 2px; border-radius: 2px; }}
/* ── Responsive ── */
@media (max-width: 768px) {{
  .sidebar {{ display: none; }}
  .main {{ padding: 1rem; }}
  .header h1 {{ font-size: 1.2rem; }}
}}
/* ── Scrollbar ── */
::-webkit-scrollbar {{ width: 8px; }}
::-webkit-scrollbar-track {{ background: var(--bg2); }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}
</style>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&family=Amiri:wght@400;700&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
</head>
<body>

<div class="header">
  <h1>شمس المعارف ولطائف العوارف</h1>
  <div class="subtitle">Shams al-Ma'arif wa Lata'if al-'Awarif — Verbatim English Translation</div>
  <div class="controls">
    <input type="search" id="searchInput" placeholder="Search the text… (Arabic or English)">
    <button onclick="toggleDark()">🌙 Dark</button>
    <button onclick="toggleSidebar()">☰ Chapters</button>
  </div>
</div>

<div class="layout">
  <nav class="sidebar" id="sidebar">
    <h3>Chapters</h3>
    <div id="chapterNav"></div>
  </nav>

  <main class="main" id="mainContent">
    <div class="search-results" id="searchResults"></div>
    <div id="chapters"></div>
  </main>
</div>

<script>
// ── Data (injected at build time) ──
const CHAPTERS = __CHAPTERS_JSON__;

// ── Build sidebar ──
const nav = document.getElementById('chapterNav');
CHAPTERS.forEach(ch => {{
  const a = document.createElement('a');
  a.href = `#ch-${{ch.num}}`;
  a.innerHTML = `<span class="ch-num">${{ch.num}}</span> ${{ch.title}}`;
  a.dataset.ch = ch.num;
  nav.appendChild(a);
}});

// ── Render chapters ──
const container = document.getElementById('chapters');
CHAPTERS.forEach(ch => {{
  const sec = document.createElement('div');
  sec.className = 'chapter';
  sec.id = `ch-${{ch.num}}`;
  
  let pagesHtml = '';
  ch.pages.forEach(p => {{
    // Split content into Arabic and English sections
    const sections = p.content.split(/(?=^Arabic:|^English:)/m);
    let arabicHtml = '';
    let englishHtml = '';
    
    sections.forEach(s => {{
      const trimmed = s.trim();
      if (trimmed.startsWith('Arabic:')) {{
        const text = trimmed.replace(/^Arabic:\s*/, '').trim();
        if (text && !text.match(/^(There is no text|This page is empty)/i)) {{
          arabicHtml = `<div class="section-label">Arabic Original</div><div class="arabic-section">${{escHtml(text)}}</div>`;
        }}
      }} else if (trimmed.startsWith('English:')) {{
        const text = trimmed.replace(/^English:\s*/, '').trim();
        if (text && !text.match(/^(There is no text|This page is empty)/i)) {{
          englishHtml = `<div class="section-label">English Translation</div><div class="english-section">${{escHtml(text)}}</div>`;
        }}
      }} else if (trimmed) {{
        englishHtml += `<div class="english-section">${{escHtml(trimmed)}}</div>`;
      }}
    }});
    
    pagesHtml += `<div class="page-block" data-page="${{p.page_num}}">
      <div class="page-num">Page ${{p.page_num}}</div>
      ${{arabicHtml}}
      ${{englishHtml}}
    </div>`;
  }});
  
  sec.innerHTML = `
    <div class="chapter-header">
      <h2>Chapter ${{ch.num}}: ${{ch.title}}</h2>
      <div class="ch-subtitle">${{ch.subtitle}}</div>
      <div class="ch-meta">${{ch.page_count}} pages · ${{ch.total_chars.toLocaleString()}} characters</div>
    </div>
    ${{pagesHtml}}
  `;
  container.appendChild(sec);
}});

// ── Helpers ──
function escHtml(s) {{
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}

// ── Dark mode ──
function toggleDark() {{
  document.body.classList.toggle('dark');
  localStorage.setItem('dark', document.body.classList.contains('dark'));
}}
if (localStorage.getItem('dark') === 'true') document.body.classList.add('dark');

// ── Sidebar toggle ──
function toggleSidebar() {{
  const sb = document.getElementById('sidebar');
  sb.style.display = sb.style.display === 'none' ? 'block' : 'none';
}}

// ── Scroll spy ──
const observer = new IntersectionObserver(entries => {{
  entries.forEach(e => {{
    if (e.isIntersecting) {{
      document.querySelectorAll('.sidebar a').forEach(a => a.classList.remove('active'));
      const link = document.querySelector(`.sidebar a[href="#${{e.target.id}}"]`);
      if (link) link.classList.add('active');
    }}
  }});
}}, {{ threshold: 0.2 }});
document.querySelectorAll('.chapter').forEach(ch => observer.observe(ch));

// ── Search ──
const searchInput = document.getElementById('searchInput');
const searchResults = document.getElementById('searchResults');
let searchTimeout;

searchInput.addEventListener('input', () => {{
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(doSearch, 300);
}});

function doSearch() {{
  const q = searchInput.value.trim().toLowerCase();
  if (q.length < 2) {{ searchResults.classList.remove('active'); return; }}
  
  const results = [];
  document.querySelectorAll('.page-block').forEach(block => {{
    const text = block.textContent.toLowerCase();
    if (text.includes(q)) {{
      const page = block.dataset.page;
      const snippet = block.textContent.substring(0, 200).replace(new RegExp(q, 'gi'), m => `<mark>${{m}}</mark>`);
      results.push({{ page, snippet }});
    }}
  }});
  
  if (results.length === 0) {{
    searchResults.innerHTML = `<div style="color:var(--fg3)">No results for "${{q}}"</div>`;
  }} else {{
    searchResults.innerHTML = `<div style="margin-bottom:0.5rem;color:var(--fg3)">${{results.length}} results</div>` +
      results.slice(0, 20).map(r => 
        `<div class="search-result-item" onclick="document.querySelector('[data-page=\\'${{r.page}}\\']')?.scrollIntoView({{behavior:'smooth',block:'center'}})">
          <span class="sr-page">Page ${{r.page}}</span><br>${{r.snippet}}…
        </div>`
      ).join('');
  }}
  searchResults.classList.add('active');
}}
</script>
</body>
</html>'''


def build_html():
    """Generate the static HTML from the database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get all chapters with pages
    chapters = cur.execute('''
        SELECT c.chapter_num, c.slug, c.title, c.subtitle, c.page_count, c.total_chars,
               p.page_num, p.content
        FROM chapters c
        JOIN pages p ON c.chapter_num = p.chapter_num
        ORDER BY c.chapter_num, p.page_num
    ''').fetchall()

    # Group by chapter
    chapters_data = {}
    for row in chapters:
        ch_num = row['chapter_num']
        if ch_num not in chapters_data:
            chapters_data[ch_num] = {
                'num': ch_num,
                'slug': row['slug'],
                'title': row['title'],
                'subtitle': row['subtitle'],
                'page_count': row['page_count'],
                'total_chars': row['total_chars'],
                'pages': []
            }
        chapters_data[ch_num]['pages'].append({
            'page_num': row['page_num'],
            'content': row['content'],
        })

    conn.close()

    # Build JSON data
    import json
    chapters_list = [chapters_data[k] for k in sorted(chapters_data.keys())]
    chapters_json = json.dumps(chapters_list, ensure_ascii=False, indent=None)

    # Inject into template
    html = HTML_TEMPLATE.replace('__CHAPTERS_JSON__', chapters_json)

    # Write
    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(html)

    size_mb = HTML_PATH.stat().st_size / 1024 / 1024
    print(f"Generated: {HTML_PATH}")
    print(f"Size: {size_mb:.1f} MB")
    print(f"Chapters: {len(chapters_list)}")
    print(f"Total pages: {sum(ch['page_count'] for ch in chapters_list)}")


if __name__ == '__main__':
    build_html()
