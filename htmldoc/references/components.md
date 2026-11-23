# Content blocks

Copy-paste blocks for `/htmldoc` pages. Every one already follows the `.en` / `.zh` contract.
All styling exists in the template — do not add new CSS unless a block genuinely needs it.

## Page header

```html
<h1><span class="en">Q3 Platform Review</span><span class="zh">三季度平台回顾</span></h1>
<p class="subtitle">
  <span class="en">What shipped, what slipped, and what changes next quarter.</span>
  <span class="zh">已交付的、延期的，以及下季度的调整。</span>
</p>
<p class="meta">
  <span class="en">Bruce Xu · Updated 2026-08-27</span>
  <span class="zh">Bruce Xu · 更新于 2026-08-27</span>
</p>
```

## Section heading

```html
<h2><span class="en">Data pipeline</span><span class="zh">数据管道</span></h2>
<h3><span class="en">Ingestion</span><span class="zh">数据接入</span></h3>
<h4><span class="en">Retry policy</span><span class="zh">重试策略</span></h4>
```

## Paragraph and list

```html
<p>
  <span class="en">Each worker retries three times with exponential backoff.</span>
  <span class="zh">每个 worker 会以指数退避方式重试三次。</span>
</p>

<ul>
  <li><span class="en">First attempt is immediate.</span><span class="zh">第一次立即重试。</span></li>
  <li><span class="en">Then 2s, then 8s.</span><span class="zh">之后间隔 2 秒、8 秒。</span></li>
</ul>
```

## Callouts — default / warning / success

```html
<div class="note">
  <p class="note-title"><span class="en">Note</span><span class="zh">说明</span></p>
  <p><span class="en">Config lives in <code>conf/pipeline.yaml</code>.</span>
     <span class="zh">配置文件位于 <code>conf/pipeline.yaml</code>。</span></p>
</div>

<div class="note warn">
  <p class="note-title"><span class="en">Careful</span><span class="zh">注意</span></p>
  <p><span class="en">Changing the partition key requires a full backfill.</span>
     <span class="zh">修改分区键需要执行完整回填。</span></p>
</div>

<div class="note ok">
  <p class="note-title"><span class="en">Done</span><span class="zh">已完成</span></p>
  <p><span class="en">Migrated on 2026-07-14 with no downtime.</span>
     <span class="zh">已于 2026-07-14 无停机迁移完成。</span></p>
</div>
```

## Table

Spans go **inside** the cells. Never put `.en` / `.zh` on `<td>`, `<th>` or `<tr>`.

```html
<div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th><span class="en">Field</span><span class="zh">字段</span></th>
        <th><span class="en">Type</span><span class="zh">类型</span></th>
        <th><span class="en">Description</span><span class="zh">说明</span></th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><code>demand_type</code></td>
        <td><code>string</code></td>
        <td><span class="en">Traffic source category.</span><span class="zh">流量来源类别。</span></td>
      </tr>
    </tbody>
  </table>
</div>
```

Header labels never wrap (`th` is `white-space: nowrap`), so keep them short **in both languages**. English usually runs about twice as wide as Chinese, so check the English view. If a label needs a qualifier, use a grouped header (below) instead of a long label.

### Column widths

The browser sizes columns from their content, so a column of long sentences can squeeze a label column into a sliver. When a table mixes short labels with long text, set relative widths with a `<colgroup>`:

```html
<div class="table-wrap">
  <table>
    <colgroup><col style="width:24%"><col style="width:38%"><col style="width:38%"></colgroup>
    <thead>…</thead>
    <tbody>…</tbody>
  </table>
</div>
```

### Numeric table

Put `class="num"` on the `th` **and** every `td` of a figures column: right-aligned, tabular digits, never wraps. Only figures go in `.num` cells. A descriptive row inside a numeric table, such as owners or risks, uses plain `<td>`s so it wraps, because one sentence in a no-wrap cell stretches the column and crushes the rest. `.ctr` centres short codes or counts. `tr.total` marks a totals row. `.table-note` is the footnote under a table.

```html
<div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th><span class="en">Item</span><span class="zh">项目</span></th>
        <th class="num">2025</th>
        <th class="num">2026</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><span class="en">Compute</span><span class="zh">计算</span></td>
        <td class="num">$120,000</td>
        <td class="num">$145,500</td>
      </tr>
      <tr class="total">
        <td><span class="en">Total</span><span class="zh">合计</span></td>
        <td class="num">$180,000</td>
        <td class="num">$212,000</td>
      </tr>
      <tr>
        <td><span class="en">Main risk</span><span class="zh">主要风险</span></td>
        <td><span class="en">Vendor raises prices at renewal</span><span class="zh">续约时供应商涨价</span></td>
        <td><span class="en">Migration runs over schedule</span><span class="zh">迁移超期</span></td>
      </tr>
    </tbody>
  </table>
</div>
<p class="table-note"><span class="en">USD, excluding tax.</span><span class="zh">单位美元，不含税。</span></p>
```

### Grouped header (two rows)

Use this when several columns share a qualifier, so that no header label has to carry it. `th.grp` spans its columns on the top row. Every ungrouped column takes `rowspan="2"`. The second row holds only the grouped columns' labels.

```html
<thead>
  <tr>
    <th rowspan="2"><span class="en">Item</span><span class="zh">项目</span></th>
    <th class="grp" colspan="2">Q3</th>
    <th class="grp">Q4</th>
  </tr>
  <tr>
    <th class="num"><span class="en">Plan</span><span class="zh">计划</span></th>
    <th class="num"><span class="en">Actual</span><span class="zh">实际</span></th>
    <th class="num"><span class="en">Plan</span><span class="zh">计划</span></th>
  </tr>
</thead>
```

## Card grid

```html
<div class="cards">
  <div class="card">
    <h4><span class="en">Throughput</span><span class="zh">吞吐量</span></h4>
    <p><span class="en">1.2M events/min at peak.</span><span class="zh">峰值 120 万事件/分钟。</span></p>
  </div>
  <div class="card">
    <h4><span class="en">Latency</span><span class="zh">延迟</span></h4>
    <p><span class="en">p99 under 300ms.</span><span class="zh">p99 低于 300 毫秒。</span></p>
  </div>
</div>
```

Card headings never enter the TOC.

## Code — never duplicated

Code is language-neutral. Write it once, translate only the surrounding prose and comments if the comments are prose.

```html
<p><span class="en">Run the backfill:</span><span class="zh">执行回填：</span></p>
<pre><code>bin/backfill --from 2026-07-01 --to 2026-07-14</code></pre>
```

## Inline badge

```html
<span class="badge"><span class="en">Draft</span><span class="zh">草稿</span></span>
```

## Blockquote

```html
<blockquote>
  <p><span class="en">"Ship the boring version first."</span>
     <span class="zh">"先交付最朴素的版本。"</span></p>
</blockquote>
```

## Whole-block duplication

When the two languages need different structure or length, duplicate the block instead of fighting span-by-span:

```html
<p class="en">English phrasing that runs long and needs its own rhythm.</p>
<p class="zh">中文表达的节奏与结构不同，单独成段更自然。</p>
```

## Anchors between sections

Ids come from the English heading text, lowercased and hyphenated:
`<h2><span class="en">Data pipeline</span>…` → `#data-pipeline`.

```html
<a href="#data-pipeline"><span class="en">see Data pipeline</span><span class="zh">见「数据管道」</span></a>
```
