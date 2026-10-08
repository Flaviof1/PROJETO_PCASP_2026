const form = document.querySelector('#search-form');
const description = document.querySelector('#description');
const clearButton = document.querySelector('#clear-search');
const resultsSection = document.querySelector('#results-section');
const resultsList = document.querySelector('#results-list');
const resultCount = document.querySelector('#result-count');
const emptyState = document.querySelector('#empty-state');
const moreResults = document.querySelector('#more-results');
const loadMoreButton = document.querySelector('#load-more');
const uploadInput = document.querySelector('#workbook');
const toast = document.querySelector('#toast');
const compareDock = document.querySelector('#compare-dock');
const compareTags = document.querySelector('#compare-tags');
const compareDialog = document.querySelector('#comparison-dialog');
const compareTable = document.querySelector('#compare-table');
const selectedAccounts = new Map();
let currentResults = [];
let hasSearched = false;
let activeQuery = '';
let activeKind = '';
let searchOffset = 0;
let toastTimer;

function showToast(message, isError = false) {
  toast.textContent = message;
  toast.classList.toggle('error', isError);
  toast.hidden = false;
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => { toast.hidden = true; }, 5000);
}

function createTag(label, muted = false) {
  const tag = document.createElement('span');
  tag.className = muted ? 'tag tag-muted' : 'tag';
  tag.textContent = label;
  return tag;
}

function normalizeLabel(value) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

function accountFields(account) {
  return (account.details || '').split('\n').map((line) => {
    const separator = line.indexOf(':');
    return separator < 0 ? null : { label: line.slice(0, separator).trim(), value: line.slice(separator + 1).trim() };
  }).filter((field) => field && field.label && field.value);
}

function findField(account, startsWith) {
  const field = accountFields(account).find((item) => normalizeLabel(item.label).startsWith(startsWith));
  return field?.value || 'Não informado na planilha';
}

function appendHierarchy(parent, hierarchy) {
  if (!hierarchy?.length) return;
  const wrapper = document.createElement('div');
  wrapper.className = 'hierarchy-block';
  const label = document.createElement('p');
  label.className = 'detail-label';
  label.textContent = 'Hierarquia no PCASP';
  const list = document.createElement('ol');
  list.className = 'hierarchy-list';
  for (const node of hierarchy) {
    const item = document.createElement('li');
    const level = document.createElement('span');
    level.className = 'hierarchy-level';
    level.textContent = node.level;
    const title = document.createElement('strong');
    title.textContent = node.title;
    const code = document.createElement('code');
    code.textContent = node.code;
    item.append(level, title, code);
    list.append(item);
  }
  wrapper.append(label, list);
  parent.append(wrapper);
}

function appendAccountFields(parent, account) {
  const excluded = new Set(['classe', 'grupo', 'subgrupo', 'titulo', 'subtitulo', 'item', 'subitem']);
  const fields = accountFields(account).filter((field) => !excluded.has(normalizeLabel(field.label)));
  if (!fields.length) return;
  const grid = document.createElement('dl');
  grid.className = 'detail-grid';
  for (const field of fields) {
    const group = document.createElement('div');
    const label = document.createElement('dt');
    label.textContent = field.label;
    const value = document.createElement('dd');
    value.textContent = field.value;
    group.append(label, value);
    grid.append(group);
  }
  parent.append(grid);
}

function updateCompareDock() {
  compareTags.replaceChildren();
  compareDock.hidden = selectedAccounts.size === 0;
  for (const account of selectedAccounts.values()) {
    const chip = document.createElement('span');
    chip.className = 'compare-chip';
    chip.textContent = `${account.code} · ${account.title}`;
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.setAttribute('aria-label', `Remover conta ${account.code} da comparação`);
    remove.textContent = '×';
    remove.addEventListener('click', () => toggleCompare(account));
    chip.append(remove);
    compareTags.append(chip);
  }
  compareDock.querySelector('#compare-open').textContent = `Comparar ${selectedAccounts.size} contas`;
}

function toggleCompare(account) {
  if (selectedAccounts.has(account.code)) {
    selectedAccounts.delete(account.code);
  } else if (selectedAccounts.size >= 3) {
    showToast('Selecione até três contas para comparar.', true);
    return;
  } else {
    selectedAccounts.set(account.code, account);
  }
  renderResults(currentResults, hasSearched);
}

function renderResults(results, searched = true, append = false) {
  currentResults = append ? [...currentResults, ...results] : results;
  hasSearched = searched;
  if (!append) resultsList.replaceChildren();
  resultsSection.hidden = currentResults.length === 0;
  emptyState.hidden = !hasSearched || currentResults.length !== 0;
  resultCount.textContent = `${currentResults.length} ${currentResults.length === 1 ? 'sugestão' : 'sugestões'}`;
  for (const account of results) {
    const card = document.createElement('article');
    card.className = 'result-card';
    const code = document.createElement('div');
    code.className = 'result-code';
    code.textContent = account.code;
    const main = document.createElement('div');
    main.className = 'result-main';
    const title = document.createElement('h3');
    title.textContent = account.title;
    const description = document.createElement('p');
    description.className = 'result-function';
    description.textContent = account.function || 'A tabela não informa uma função para esta conta.';
    const tags = document.createElement('div');
    tags.className = 'result-tags';
    if (account.balance_nature) tags.append(createTag(`Natureza do saldo: ${account.balance_nature}`));
    if (account.status) tags.append(createTag(account.status, true));
    main.append(title, description, tags);
    if (account.match_reasons?.length) {
      const reasonBlock = document.createElement('div');
      reasonBlock.className = 'match-reasons';
      const reasonTitle = document.createElement('strong');
      reasonTitle.textContent = 'Por que apareceu';
      const reasonList = document.createElement('ul');
      for (const reason of account.match_reasons) {
        const item = document.createElement('li');
        item.textContent = reason;
        reasonList.append(item);
      }
      reasonBlock.append(reasonTitle, reasonList);
      main.append(reasonBlock);
    }
    if (account.details) {
      const details = document.createElement('details');
      details.className = 'details';
      const summary = document.createElement('summary');
      summary.textContent = 'Ver hierarquia e campos completos da tabela';
      details.append(summary);
      appendHierarchy(details, account.hierarchy);
      appendAccountFields(details, account);
      main.append(details);
    }
    const compareButton = document.createElement('button');
    compareButton.type = 'button';
    compareButton.className = 'compare-button';
    const isSelected = selectedAccounts.has(account.code);
    compareButton.textContent = isSelected ? 'Remover da comparação' : 'Adicionar à comparação';
    compareButton.disabled = !isSelected && selectedAccounts.size >= 3;
    compareButton.setAttribute('aria-pressed', String(isSelected));
    compareButton.addEventListener('click', () => toggleCompare(account));
    main.append(compareButton);
    card.append(code, main);
    resultsList.append(card);
  }
  updateCompareDock();
}

function hierarchyText(account) {
  return account.hierarchy?.map((node) => `${node.level}: ${node.title} (${node.code})`).join(' › ') || 'Hierarquia não disponível na tabela';
}

function openComparison() {
  const accounts = [...selectedAccounts.values()];
  if (accounts.length < 2) {
    showToast('Adicione pelo menos duas contas para comparar.');
    return;
  }
  const rows = [
    ['Código', (account) => account.code],
    ['Título', (account) => account.title],
    ['Hierarquia', hierarchyText],
    ['Função', (account) => account.function || 'Não informado na planilha'],
    ['Natureza do saldo', (account) => account.balance_nature || 'Não informado na planilha'],
    ['Situação', (account) => account.status || 'Não informado na planilha'],
    ['Indicador do superávit financeiro', (account) => findField(account, 'indicador do superavit')],
    ['Registro obrigatório', (account) => findField(account, 'n registro obrig')],
    ['Atributo obrigatório (conta corrente)', (account) => findField(account, 'atributo obrig conta corrente')],
    ['Atributo obrigatório (inclusão/exclusão/alteração)', (account) => findField(account, 'atributo obrig inclusao')],
    ['Exercício da atualização do atributo', (account) => findField(account, 'exercicio da atualizacao do atributo')],
    ['Escrituração', (account) => findField(account, 'escrituracao')],
    ['Encerramento', (account) => findField(account, 'encerramento')],
  ];
  compareTable.replaceChildren();
  const head = document.createElement('thead');
  const headerRow = document.createElement('tr');
  const firstHeader = document.createElement('th');
  firstHeader.textContent = 'Campo';
  headerRow.append(firstHeader);
  for (const account of accounts) {
    const header = document.createElement('th');
    header.textContent = `${account.code} · ${account.title}`;
    headerRow.append(header);
  }
  head.append(headerRow);
  compareTable.append(head);
  const body = document.createElement('tbody');
  for (const [label, valueFor] of rows) {
    const row = document.createElement('tr');
    const heading = document.createElement('th');
    heading.scope = 'row';
    heading.textContent = label;
    row.append(heading);
    for (const account of accounts) {
      const cell = document.createElement('td');
      cell.textContent = valueFor(account);
      row.append(cell);
    }
    body.append(row);
  }
  compareTable.append(body);
  compareDialog.showModal();
}

document.querySelector('#compare-open').addEventListener('click', openComparison);
document.querySelector('#compare-clear').addEventListener('click', () => {
  selectedAccounts.clear();
  renderResults(currentResults, hasSearched);
});
document.querySelector('#close-comparison').addEventListener('click', () => compareDialog.close());
compareDialog.addEventListener('click', (event) => {
  if (event.target === compareDialog) compareDialog.close();
});

async function fetchSearchPage(append = false) {
  const submitButton = form.querySelector('button[type="submit"]');
  if (append) {
    loadMoreButton.disabled = true;
    loadMoreButton.textContent = 'Carregando…';
  } else {
    submitButton.disabled = true;
    submitButton.querySelector('span').textContent = 'Buscando…';
  }
  try {
    const params = new URLSearchParams({ q: activeQuery, tipo: activeKind, limit: '15', offset: String(searchOffset) });
    const response = await fetch(`/api/search?${params}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível realizar a busca.');
    renderResults(data.results, true, append);
    searchOffset += data.results.length;
    moreResults.hidden = !data.has_more;
  } catch (error) {
    showToast(error.message || 'Falha ao conectar com o sistema.', true);
  } finally {
    if (append) {
      loadMoreButton.disabled = false;
      loadMoreButton.textContent = 'Carregar mais sugestões';
    } else {
      submitButton.disabled = false;
      submitButton.querySelector('span').textContent = 'Buscar contas';
    }
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const text = description.value.trim();
  if (!text) return;
  activeQuery = text;
  activeKind = new FormData(form).get('kind') || '';
  searchOffset = 0;
  moreResults.hidden = true;
  await fetchSearchPage(false);
});
loadMoreButton.addEventListener('click', () => fetchSearchPage(true));

description.addEventListener('input', () => { clearButton.hidden = !description.value; });
clearButton.addEventListener('click', () => {
  description.value = '';
  clearButton.hidden = true;
  activeQuery = '';
  searchOffset = 0;
  moreResults.hidden = true;
  description.focus();
  renderResults([], false);
});

async function loadStatus() {
  const status = document.querySelector('#source-status');
  try {
    const response = await fetch('/api/status');
    const data = await response.json();
    const date = data.updated_at ? new Date(data.updated_at).toLocaleString('pt-BR') : '';
    document.querySelector('#access-mode').textContent = data.can_upload ? 'Uso local' : 'Rede local';
    if (!data.can_upload) {
      document.querySelector('#upload-form').hidden = true;
      document.querySelector('.import-copy h2').textContent = 'Tabela compartilhada';
    }
    status.textContent = data.account_count
      ? `${Number(data.account_count).toLocaleString('pt-BR')} contas · ${data.source}${date ? ` · Atualizada em ${date}` : ''}${data.can_upload ? '' : ' · Atualização no computador principal'}`
      : 'Nenhuma planilha PCASP carregada.';
  } catch {
    status.textContent = 'Não foi possível consultar o estado da tabela.';
  }
}

uploadInput.addEventListener('change', async () => {
  const file = uploadInput.files?.[0];
  if (!file) return;
  document.querySelector('#file-hint').textContent = file.name;
  const body = new FormData();
  body.append('arquivo', file);
  try {
    const response = await fetch('/api/upload', { method: 'POST', body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível importar a planilha.');
    showToast(data.message);
    await loadStatus();
    activeQuery = '';
    searchOffset = 0;
    moreResults.hidden = true;
    renderResults([], false);
  } catch (error) {
    showToast(error.message || 'Falha ao enviar a planilha.', true);
  } finally {
    uploadInput.value = '';
    document.querySelector('#file-hint').textContent = '.xlsx até 20 MB';
  }
});

loadStatus();
