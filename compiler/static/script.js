// ============================================================
// GrammarForge — script.js
// ============================================================

// ── STATE ────────────────────────────────────────────────────
const state = {
  grammar:      null,   // original generated grammar
  ll1Result:    null,   // full ll1 pipeline result
  lr1Result:    null,   // lr1 action + goto
  activeParser: 'll1'  // 'll1' | 'lr1'
}

// ── DOM REFS ─────────────────────────────────────────────────
const $ = id => document.getElementById(id)

const inputEl        = $('input-string')
const btnRun         = $('btn-run')
const btnSimulate    = $('btn-simulate')
const toggleLL1      = $('toggle-ll1')
const toggleLR1      = $('toggle-lr1')
const loader         = $('loader')
const loaderText     = $('loader-text')
const warningsBox    = $('warnings-box')
const warningsList   = $('warnings-list')


// ── LOADER ────────────────────────────────────────────────────
function showLoader(msg = 'Processing...') {
  loaderText.textContent = msg
  loader.classList.remove('hidden')
}

function hideLoader() {
  loader.classList.add('hidden')
}


// ── SECTION REVEAL ────────────────────────────────────────────
function showSection(id) {
  const el = $(id)
  if (el) {
    el.classList.remove('hidden')
    el.style.animation = 'none'
    el.offsetHeight     // reflow
    el.style.animation = ''
  }
}

function hideSection(id) {
  const el = $(id)
  if (el) el.classList.add('hidden')
}


// ── WARNINGS ──────────────────────────────────────────────────
function renderWarnings(warnings) {
  if (!warnings || warnings.length === 0) {
    warningsBox.classList.add('hidden')
    return
  }

  warningsList.innerHTML = ''
  warnings.forEach(w => {
    const li = document.createElement('li')
    li.textContent = w
    if (w.startsWith('⚠'))      li.className = 'warn'
    else if (w.startsWith('✔')) li.className = 'ok'
    else if (w.startsWith('✘')) li.className = 'error'
    warningsList.appendChild(li)
  })

  warningsBox.classList.remove('hidden')
}


// ── GRAMMAR SECTION ───────────────────────────────────────────
function renderGrammar(originalGrammar, finalGrammar, formatted) {
  $('grammar-original').textContent = formatGrammarDict(originalGrammar)
  $('grammar-final').textContent    = formatted || formatGrammarDict(finalGrammar)
  showSection('section-grammar')
}

function formatGrammarDict(grammar) {
  if (!grammar) return ''
  return Object.entries(grammar)
    .map(([nt, prods]) => {
      const rhs = prods.map(p => p.join(' ')).join(' | ')
      return `${nt}  →  ${rhs}`
    })
    .join('\n')
}


// ── FIRST & FOLLOW ────────────────────────────────────────────
function renderSets(first, follow) {
  renderSetTable('first-table', first)
  renderSetTable('follow-table', follow)
  showSection('section-sets')
}

function renderSetTable(tableId, sets) {
  const tbody = document.querySelector(`#${tableId} tbody`)
  tbody.innerHTML = ''

  Object.entries(sets).forEach(([nt, symbols]) => {
    const tr = document.createElement('tr')
    tr.innerHTML = `
      <td>${nt}</td>
      <td>{ ${symbols.sort().join(', ')} }</td>
    `
    tbody.appendChild(tr)
  })
}


// ── LL(1) TABLE ───────────────────────────────────────────────
function renderLL1Table(tableData, conflicts, finalGrammar, first, follow) {
  // Collect all terminals from table keys
  const terminals = new Set()
  const conflictSet = new Set()

  Object.keys(tableData).forEach(key => {
    const [, terminal] = key.split(',')
    terminals.add(terminal)
  })

  conflicts.forEach(c => conflictSet.add(`${c.non_terminal},${c.terminal}`))

  // Get non-terminals (row headers)
  const nonTerminals = finalGrammar ? Object.keys(finalGrammar) : []
  const termList     = [...terminals].sort()

  // Build header
  const thead = $('ll1-table-head')
  thead.innerHTML = '<th>NT \\ Terminal</th>' +
    termList.map(t => `<th>${t}</th>`).join('')

  // Build body
  const tbody = $('ll1-table-body')
  tbody.innerHTML = ''

  nonTerminals.forEach(nt => {
    const tr = document.createElement('tr')
    let html = `<td>${nt}</td>`

    termList.forEach(t => {
      const key   = `${nt},${t}`
      const entry = tableData[key]
      const isConflict = conflictSet.has(key)

      if (entry) {
        const prod = Array.isArray(entry) ? entry.join(' ') : entry
        html += `<td class="${isConflict ? 'conflict' : ''}">${nt} → ${prod}</td>`
      } else {
        html += `<td class="${isConflict ? 'conflict' : ''}">—</td>`
      }
    })

    tr.innerHTML = html
    tbody.appendChild(tr)
  })

  // Conflict banner
  const banner = $('ll1-conflicts-banner')
  if (conflicts.length > 0) {
    banner.textContent = `⚠ ${conflicts.length} conflict(s) detected — grammar is not LL(1). Conflicting cells highlighted in red.`
    banner.classList.remove('hidden')
  } else {
    banner.classList.add('hidden')
  }

  showSection('section-ll1')
}


// ── LR(1) TABLE ───────────────────────────────────────────────
function renderLR1Table(actionData, gotoData, conflicts, statesCount, startSymbol) {
  // Parse all state indices
  const stateSet   = new Set()
  const termSet    = new Set()
  const ntSet      = new Set()

  Object.keys(actionData).forEach(key => {
    const [s, sym] = key.split(',')
    stateSet.add(parseInt(s))
    termSet.add(sym)
  })

  Object.keys(gotoData).forEach(key => {
    const [s, sym] = key.split(',')
    stateSet.add(parseInt(s))
    ntSet.add(sym)
  })

  const states   = [...stateSet].sort((a, b) => a - b)
  const terms    = [...termSet].sort()
  const nts      = [...ntSet].sort()

  // Header
  const thead = $('lr1-table-head')
  thead.innerHTML =
    '<th>State</th>' +
    terms.map(t => `<th>${t}</th>`).join('') +
    (nts.length ? '<th class="nt-header" colspan="' + nts.length + '">GOTO</th>' : '') +
    nts.map(nt => `<th class="nt-header">${nt}</th>`).join('')

  // Actually rebuild header properly
  thead.innerHTML =
    '<th>State</th>' +
    terms.map(t => `<th>${escHtml(t)}</th>`).join('') +
    nts.map(nt => `<th class="nt-header">${escHtml(nt)}</th>`).join('')

  // Body
  const tbody = $('lr1-table-body')
  tbody.innerHTML = ''

  states.forEach(s => {
    const tr = document.createElement('tr')
    let html = `<td>${s}</td>`

    terms.forEach(t => {
      const key = `${s},${t}`
      const act = actionData[key]

      if (!act) {
        html += '<td>—</td>'
        return
      }

      if (act[0] === 'accept') {
        html += '<td class="accept">ACC</td>'
      } else if (act[0] === 'shift') {
        html += `<td class="shift">s${act[1]}</td>`
      } else if (act[0] === 'reduce') {
        const prod = act[2] ? act[2].join(' ') : ''
        html += `<td class="reduce">r: ${act[1]}→${prod}</td>`
      } else {
        html += `<td>${JSON.stringify(act)}</td>`
      }
    })

    nts.forEach(nt => {
      const key = `${s},${nt}`
      const g   = gotoData[key]
      html += g !== undefined ? `<td class="shift">${g}</td>` : '<td>—</td>'
    })

    tr.innerHTML = html
    tbody.appendChild(tr)
  })

  // Meta
  $('lr1-meta').textContent = `${statesCount} states  ·  start: ${startSymbol}`

  // Conflict banner
  const banner = $('lr1-conflicts-banner')
  if (conflicts && conflicts.length > 0) {
    banner.textContent = `⚠ ${conflicts.length} conflict(s) detected in LR(1) table.`
    banner.classList.remove('hidden')
  } else {
    banner.classList.add('hidden')
  }

  showSection('section-lr1')
}


// ── SIMULATE ──────────────────────────────────────────────────
function renderSimulation(result, steps, parserType) {
  const badge = $('result-badge')
  badge.textContent = result
  badge.className   = 'result-badge ' + (
    result === 'ACCEPTED' || result === 'ACCEPT' ? 'accepted' : 'error'
  )

  // Build step table
  const isLL1 = parserType === 'll1'
  const thead = $('sim-table-head')
  const tbody = $('sim-table-body')

  thead.innerHTML = isLL1
    ? '<th>#</th><th>Stack</th><th>Input</th><th>Action</th>'
    : '<th>#</th><th>Stack</th><th>Input</th><th>Action</th>'

  tbody.innerHTML = ''

  steps.forEach((step, i) => {
    const tr  = document.createElement('tr')
    const stack  = Array.isArray(step.stack) ? step.stack.join(' ') : step.stack
    const input  = Array.isArray(step.input) ? step.input.join(' ') : step.input
    const action = step.action || ''

    const isError  = action.toString().includes('ERROR')
    const isAccept = action.toString().includes('ACCEPT')

    tr.innerHTML = `
      <td>${i + 1}</td>
      <td>${escHtml(String(stack))}</td>
      <td>${escHtml(String(input))}</td>
      <td class="${isError ? 'conflict' : isAccept ? 'accept' : ''}">${escHtml(String(action))}</td>
    `
    tbody.appendChild(tr)
  })

  $('sim-result').classList.remove('hidden')
  showSection('section-simulate')
}


// ── TOGGLE PARSER TYPE ────────────────────────────────────────
toggleLL1.addEventListener('click', () => {
  state.activeParser = 'll1'
  toggleLL1.classList.add('active')
  toggleLR1.classList.remove('active')
})

toggleLR1.addEventListener('click', () => {
  state.activeParser = 'lr1'
  toggleLR1.classList.add('active')
  toggleLL1.classList.remove('active')
})


// ── MAIN RUN ──────────────────────────────────────────────────
btnRun.addEventListener('click', runPipeline)
inputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter') runPipeline()
})

async function runPipeline() {
  const inputString = inputEl.value.trim()

  if (!inputString) {
    inputEl.focus()
    return
  }

  // Hide all result sections
  hideSection('section-grammar')
  hideSection('section-sets')
  hideSection('section-ll1')
  hideSection('section-lr1')
  hideSection('section-simulate')
  $('sim-result').classList.add('hidden')

  showLoader('Generating grammar...')

  try {
    // ── Step 1: Full pipeline ──────────────────────────────
    loaderText.textContent = 'Running full pipeline...'

    const res = await fetch('/api/full-pipeline', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input_string: inputString })
    })

    const data = await res.json()

    if (!res.ok || data.error) {
      hideLoader()
      alert(`Error: ${data.error || 'Unknown error'}`)
      return
    }

    // Store state
    state.grammar   = data.grammar
    state.ll1Result = data.ll1
    state.lr1Result = data.lr1

    // ── Render warnings ────────────────────────────────────
    const allWarnings = [
      ...(data.warnings || []),
      ...(data.ll1?.warnings || [])
    ]
    renderWarnings(allWarnings)

    // ── Render grammar ─────────────────────────────────────
    loaderText.textContent = 'Rendering grammar...'
    renderGrammar(data.grammar, data.ll1?.final_grammar, data.ll1?.formatted)

    // ── Render FIRST & FOLLOW ──────────────────────────────
    loaderText.textContent = 'Computing FIRST & FOLLOW...'
    renderSets(data.first, data.follow)

    // ── Render LL(1) table ─────────────────────────────────
    loaderText.textContent = 'Building LL(1) table...'
    renderLL1Table(
      data.ll1.table,
      data.ll1.conflicts || [],
      data.ll1.final_grammar,
      data.first,
      data.follow
    )

    // ── Render LR(1) table ─────────────────────────────────
    loaderText.textContent = 'Building LR(1) table...'
    renderLR1Table(
      data.lr1.action,
      data.lr1.goto,
      data.lr1.conflicts || [],
      data.lr1.states_count,
      data.lr1.start_symbol
    )

    // ── Show simulate section ──────────────────────────────
    showSection('section-simulate')

  } catch (err) {
    console.error(err)
    alert('Network error: ' + err.message)
  } finally {
    hideLoader()
  }
}


// ── SIMULATE ──────────────────────────────────────────────────
btnSimulate.addEventListener('click', async () => {
  const inputString = inputEl.value.trim()

  if (!inputString || !state.grammar) {
    alert('Please run the analyzer first.')
    return
  }

  showLoader(`Simulating ${state.activeParser.toUpperCase()} parser...`)

  try {
    const endpoint = state.activeParser === 'll1'
      ? '/api/simulate-ll1'
      : '/api/simulate-lr1'

    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        input_string: inputString,
        grammar: state.grammar
      })
    })

    const data = await res.json()

    if (!res.ok || data.error) {
      hideLoader()
      alert(`Simulation error: ${data.error}`)
      return
    }

    renderSimulation(data.result, data.steps, state.activeParser)

  } catch (err) {
    console.error(err)
    alert('Network error: ' + err.message)
  } finally {
    hideLoader()
  }
})


// ── HELPERS ───────────────────────────────────────────────────
function escHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}
