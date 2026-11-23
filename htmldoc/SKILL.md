---
name: htmldoc
description: Organize any information (notes, research, specs, comparisons, reports, meeting output, onboarding docs) into ONE self-contained bilingual HTML page - floating nested table of contents on the left, EN/中文 toggle in the top-right corner. Use whenever the user asks to "turn this into HTML", wants a readable/navigable document, a report page, a handbook, or says 整理成 HTML / 做成网页 / 双语文档 / 带目录的文档.
trigger: /htmldoc
---

# /htmldoc

Turn a pile of information into a single HTML file a human can actually navigate: a **floating nested TOC** pinned to the left, a **language toggle in the top-right**, and every word available in **both English and Chinese**.

## Usage

```
/htmldoc                          # organize the current conversation / analysis into a page
/htmldoc <path-or-topic>          # read the source(s) first, then build the page
/htmldoc <src> -o docs/guide.html # choose the output path
```

## What it produces

One `.html` file, self-contained, no build step, no network:

| Feature | Behaviour |
|---|---|
| Left sidebar | `position: fixed`, auto-generated from `h2/h3/h4`, nested, **starts fully collapsed**; **accordion — opening one section folds the others**, so the sidebar never outgrows one screen; per-section carets plus one expand/collapse-all button in the header; scroll-spy marks the active branch without opening it |
| Navigation | Clicking a TOC entry or following a `#hash` link **jumps instantly** — no smooth-scroll animation. A deep link opens the section it lands in and folds the rest |
| Language toggle | Globe button fixed top-right, or press **`P`** anywhere; flips `<html data-lang>`; remembers the choice in `localStorage`; first visit follows `navigator.language` |
| Keyboard | **`P`** toggles language — inert while typing in a field, and `Cmd/Ctrl+P` still prints. `Esc` closes the mobile drawer |
| Bilingual content | Every visible string exists in both languages; CSS shows one, hides the other — no flicker, no re-render |
| Layout | The content column grows with the window up to 1360px, so wide tables get room on big screens. Paragraphs, lists and callouts stop at a 920px reading width |
| Responsive | Under 900px the sidebar becomes a drawer behind a hamburger button |
| Print | Sidebar and buttons drop out; the active language prints clean |
| Theme | Follows the OS light/dark preference |

## Workflow

1. **Gather** — read the sources the user pointed at (files, conversation, notes). Ask only if the *subject* is ambiguous, not the formatting.
2. **Outline first** — decide the `h2` sections before writing any HTML. 5–9 top-level sections is the sweet spot; the TOC is the product's whole value, so the outline matters more than the prose.
3. **Copy the template** — `cp ~/.claude/skills/htmldoc/assets/template.html <output>` then replace the `<title>` and everything inside `<div class="wrap">`. **Never rewrite the CSS or the script** — they are the working parts.
4. **Fill in content** following the bilingual contract below. Grab ready-made blocks from `references/components.md`.
5. **Verify** with the checklist, then tell the user the path and offer to open it (`open <file>`).

## The bilingual contract

One rule powers everything: `class="en"` and `class="zh"` mark language-specific nodes, and CSS hides the inactive one.

```html
<h2><span class="en">Architecture</span><span class="zh">架构</span></h2>
<p>
  <span class="en">The ingest service writes to Kafka.</span>
  <span class="zh">接入服务将数据写入 Kafka。</span>
</p>
```

**Rules**

- **Every** visible string gets both languages — headings, list items, table cells, captions, button labels, the `<title>`. A page that falls back to English in one language is a bug.
- Put the pair **as close to the text as possible**. Prefer two `<span>`s inside one element over duplicating the element.
- Never put `.en`/`.zh` directly on `<td>`, `<th>`, or `<tr>` — hiding a cell breaks the column grid. Wrap spans **inside** the cell.
- For a whole block whose *structure* differs between languages (a long paragraph, a differently-ordered list), it is fine to duplicate the block: `<p class="en">…</p><p class="zh">…</p>`.
- The `<title>` carries `data-en` / `data-zh`; the script swaps `document.title`.
- **Do not translate**: code, identifiers, file paths, SQL, API/field names, CLI flags, product and company names, numbers, dates in ISO form. Keep them identical in both languages.
- Chinese text is written for a Chinese reader — translate the *meaning*, don't transliterate the English word order. English text is written for an English reader. Neither is a machine gloss of the other.
- Headings drive the TOC in both languages, so a heading missing its `.zh` span shows English in the Chinese TOC. Check every heading.

## Structure that navigates well

- Exactly one `<h1>`, plus `.subtitle` and `.meta` lines under it.
- `h2` = top-level section, `h3` = subsection, `h4` = deepest. Never skip a level (no `h2` → `h4`) — the nesting is built from the tag level.
- Heading text should be short and scannable; the sidebar is ~250px wide.
- The TOC opens **collapsed**, so the `h2` list is the entire first impression. Those 5–9 headings have to describe the whole document on their own — a reader should be able to pick a section without expanding anything.
- The TOC is an **accordion**: opening a section folds every other one, so only one branch is ever open. Its own ancestors stay open — otherwise expanding a child would hide the child. This is what keeps a 40-heading document navigable in a 250px column, and it means deep `h3`/`h4` nesting costs the reader less than it looks like it should.
- Headings inside `.card` and `.note` blocks are automatically excluded from the TOC. Add `data-no-toc` to any other heading you want kept out.
- Ids are auto-generated from the English heading text, so `#section-name` anchors are stable and shareable.

## Tables that read well

Tables carry most of the data in a report, and they break in ways that prose doesn't. Blocks are in `references/components.md`.

- **Header labels never wrap.** Keep them short in *both* languages, and check the English view, which runs about twice as wide. If several columns need the same qualifier, such as "(plan)" or "(USD, excl. tax)", move it into a **grouped two-row header** instead of repeating it in each label.
- **Figures go in `.num` cells.** Put `class="num"` on the column's `th` and on every `td` holding a figure: right-aligned, tabular digits, no wrap. Never put a sentence in a `.num` cell, because it won't wrap and will push the other columns off the page. A descriptive row inside a numeric table, such as owners, dates or risks, uses plain `<td>`s.
- **Protect the label column.** When long text sits beside short labels, add a `<colgroup>` with percentage widths so the first column keeps enough room.
- Use `tr.total` for totals rows and `p.table-note` for the footnote under a table.

## Self-contained, always

No CDN links, no web fonts, no remote images, no `fetch`. Images go in as `data:` URIs. The file must work from a USB stick on a plane.

## Verification checklist

Run through this before reporting done:

```
[ ] Open the file, click the globe: every visible string changes language, nothing disappears or falls back
[ ] Press `P` with the page focused: the language flips, and the tab title flips with it. Cmd/Ctrl+P still opens the print dialog
[ ] On load every section is collapsed — only the `h2` entries show
[ ] The header button expands all, flips to the collapse icon, then collapses all again; its tooltip follows the language
[ ] Open one section, then another: the first folds by itself. Open a child inside the open one: its parent stays open
[ ] Individual carets still close their own section when clicked again; entries are translated too
[ ] Scroll the page: the active section is marked in the TOC and nothing auto-expands
[ ] Expand a section, then click entries at three depths: each jumps straight to its heading, with no scrolling animation
[ ] Narrow the window under 900px: hamburger opens the drawer, a link closes it
[ ] On a wide window (1920px), the column widens and tables fill it, while paragraphs keep their reading width
[ ] In both languages, at a laptop width (~1300px) and a wide one: no table scrolls sideways, and no first column is squeezed into a sliver (snippet below)
[ ] Reload: the language choice persisted
[ ] No console errors, no external network requests
```

Quick grep for untranslated content:

```bash
grep -c 'class="en"' out.html; grep -c 'class="zh"' out.html   # counts should match
```

If the counts differ, some string is missing a translation — find it before shipping.

Quick table check. Paste it into the DevTools console, then run it again after switching language:

```js
document.querySelectorAll('.table-wrap').forEach((w, i) => {
  const over = w.scrollWidth - w.clientWidth;
  const lh = parseFloat(getComputedStyle(w).lineHeight);
  const squeezed = [...w.querySelectorAll('tbody td:first-child')].some(td => td.clientHeight > 5 * lh);
  if (over > 0 || squeezed) console.warn(`table ${i}:`, over > 0 ? `scrolls sideways by ${over}px` : 'first column wraps past ~4 lines', w);
});
```
