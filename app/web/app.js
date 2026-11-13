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
const reconcileForm = document.querySelector('#reconcile-form');
const reviewForm = document.querySelector('#review-form');
const assetReviewDialog = document.querySelector('#asset-review-dialog');
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
let reviewInventoryFile = null;
let systemAccountFile = null;
let reviewItems = [];
let activeReviewItem = null;
let selectedReviewAccount = null;
const approvedReviewItems = new Map();
const rejectedReviewItems = new Set();

function showToast(message, isError = false) {
  toast.textContent = message;
  toast.classList.toggle('error', isError);
  toast.hidden = false;
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => { toast.hidden = true; }, 5000);
}

async function saveReviewDecision(item, decision, account = null) {
  if (!systemAccountFile) throw new Error('Carregue a relação do SH3 antes de salvar a análise.');
  const body = new FormData();
  body.append('decision', new Blob([JSON.stringify({
    asset_code: item.asset_code,
    plate: item.plate,
    description: item.description,
    source_account: item.source_account,
    decision,
    account_code: account?.code || '',
  })], { type: 'application/json' }), 'decisao.json');
  body.append('plano_sh3', systemAccountFile);
  const response = await fetch('/api/inventory-review-decision', { method: 'POST', body });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Não foi possível salvar esta decisão da análise.');
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
      reconcileForm.hidden = true;
      reviewForm.hidden = true;
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
    document.querySelector('#file-hint').textContent = 'Planilha de referência PCASP · .xlsx até 20 MB';
  }
});

reconcileForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const inventory = document.querySelector('#inventory-file').files?.[0];
  const ledger = document.querySelector('#ledger-file').files?.[0];
  if (!inventory || !ledger) return;
  const button = reconcileForm.querySelector('button[type="submit"]');
  button.disabled = true;
  button.textContent = 'Analisando…';
  const body = new FormData();
  body.append('inventario', inventory);
  body.append('relatorio', ledger);
  try {
    const response = await fetch('/api/reconcile', { method: 'POST', body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível analisar os arquivos.');
    const results = document.querySelector('#reconcile-results');
    const summary = document.querySelector('#reconcile-summary');
    const rows = document.querySelector('#reconcile-rows');
    summary.replaceChildren();
    rows.replaceChildren();
    const cards = [
      [`${Number(data.inventory_items).toLocaleString('pt-BR')}`, 'bens lidos'],
      [`${Number(data.inventory_accounts).toLocaleString('pt-BR')}`, 'contas no inventário'],
      [`${Number(data.matched_accounts).toLocaleString('pt-BR')}`, 'contas comparadas'],
      [`${data.rows.filter((row) => row.has_difference).length.toLocaleString('pt-BR')}`, 'diferenças para conferir'],
    ];
    for (const [value, label] of cards) {
      const card = document.createElement('div');
      card.className = 'summary-card';
      const strong = document.createElement('strong');
      strong.textContent = value;
      const small = document.createElement('span');
      small.textContent = label;
      card.append(strong, small);
      summary.append(card);
    }
    for (const item of data.rows) {
      const row = document.createElement('tr');
      if (item.has_difference) row.className = 'difference-row';
      for (const value of [item.code, item.title, item.item_count ? Number(item.item_count).toLocaleString('pt-BR') : '—', item.inventory_value, item.ledger_balance, item.difference, item.status]) {
        const cell = document.createElement('td');
        cell.textContent = value;
        row.append(cell);
      }
      rows.append(row);
    }
    document.querySelector('#reconcile-note').textContent = `${data.period ? `Período do relatório: ${data.period}. ` : ''}${data.note}`;
    results.hidden = false;
    results.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) {
    showToast(error.message || 'Falha ao conectar com o sistema.', true);
  } finally {
    button.disabled = false;
    button.innerHTML = 'Analisar arquivos <span aria-hidden="true">→</span>';
  }
});

function updateReviewApprovalSummary() {
  const count = approvedReviewItems.size;
  document.querySelector('#approval-count').textContent = `${count.toLocaleString('pt-BR')} aprovada(s)`;
  document.querySelector('#export-approved').disabled = count === 0 || !systemAccountFile;
  document.querySelector('#export-account-summary').disabled = !reviewInventoryFile || !systemAccountFile;
}

function renderReviewRows() {
  const filter = normalizeLabel(document.querySelector('#review-filter').value);
  const rows = document.querySelector('#review-rows');
  rows.replaceChildren();
  const filtered = reviewItems.filter((item) => normalizeLabel([
    item.plate, item.asset_code, item.description, item.current_code, item.current_title,
    ...item.suggestions.map((suggestion) => `${suggestion.code} ${suggestion.title}`),
  ].join(' ')).includes(filter));
  for (const item of filtered.slice(0, 500)) {
    const row = document.createElement('tr');
    const locator = document.createElement('td');
    locator.textContent = `Plaqueta ${item.plate || '—'}${item.asset_code ? ` · Código ${item.asset_code}` : ''}`;
    const description = document.createElement('td');
    description.textContent = item.description;
    const current = document.createElement('td');
    current.textContent = `${item.current_code} · ${item.current_title}${item.current_available_in_system ? '' : ' (não localizada no SH3)'}`;
    const suggestions = document.createElement('td');
    suggestions.textContent = item.suggestions.map((suggestion) =>
      `${suggestion.code} · ${suggestion.title} (${suggestion.available_in_system ? 'cadastrada no SH3' : 'não cadastrada no SH3'})`
    ).join(' / ');
    const status = document.createElement('td');
    if (approvedReviewItems.has(item.row_index)) {
      const approved = approvedReviewItems.get(item.row_index);
      status.textContent = `Aprovada: ${approved.code}`;
      status.className = 'approved-state';
    } else if (rejectedReviewItems.has(item.row_index)) {
      status.textContent = 'Não aprovada';
      status.className = 'rejected-state';
    } else {
      status.textContent = 'Aguardando análise';
    }
    const action = document.createElement('td');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'secondary-button review-open-button';
    button.textContent = 'Analisar';
    button.addEventListener('click', () => openAssetReview(item));
    action.append(button);
    row.append(locator, description, current, suggestions, status, action);
    rows.append(row);
  }
  document.querySelector('#review-filter-count').textContent = `${filtered.length.toLocaleString('pt-BR')} item(ns)${filtered.length > 500 ? ' · exibindo os primeiros 500' : ''}`;
  updateReviewApprovalSummary();
}

function openAssetReview(item) {
  activeReviewItem = item;
  const existing = approvedReviewItems.get(item.row_index);
  selectedReviewAccount = existing
    ? item.suggestions.find((suggestion) => suggestion.code === existing.code && suggestion.available_in_system)
    : item.suggestions.find((suggestion) => suggestion.available_in_system);
  document.querySelector('#asset-review-title').textContent = item.description || 'Confira as características do bem';
  const details = document.querySelector('#asset-review-details');
  details.replaceChildren();
  const characteristics = [
    { label: 'Plaqueta', value: item.plate || 'Não informada' },
    { label: 'Conta Bem atual', value: `${item.current_code} · ${item.current_title}` },
    ...(item.current_function ? [{ label: 'Função da conta atual', value: item.current_function }] : []),
    ...(item.current_balance_nature ? [{ label: 'Natureza do saldo atual', value: item.current_balance_nature }] : []),
    ...(item.current_status ? [{ label: 'Situação da conta atual', value: item.current_status }] : []),
    ...item.characteristics,
  ];
  for (const characteristic of characteristics) {
    const line = document.createElement('div');
    line.className = 'review-detail-line';
    const label = document.createElement('strong');
    label.textContent = characteristic.label;
    const value = document.createElement('span');
    value.textContent = characteristic.value;
    line.append(label, value);
    details.append(line);
  }
  if (item.current_account_details) {
    const currentFields = document.createElement('details');
    currentFields.className = 'review-account-metadata';
    const summary = document.createElement('summary');
    summary.textContent = 'Ver demais campos da conta atual';
    const pre = document.createElement('pre');
    pre.textContent = item.current_account_details;
    currentFields.append(summary, pre);
    details.append(currentFields);
  }
  const options = document.querySelector('#asset-account-options');
  options.replaceChildren();
  for (const suggestion of item.suggestions) {
    const option = document.createElement('label');
    option.className = 'review-account-option';
    const radio = document.createElement('input');
    radio.type = 'radio';
    radio.name = 'review-account-choice';
    radio.value = suggestion.code;
    radio.checked = suggestion.code === selectedReviewAccount?.code;
    radio.disabled = !suggestion.available_in_system;
    radio.addEventListener('change', () => {
      selectedReviewAccount = suggestion;
      document.querySelector('#approve-suggestion').disabled = !suggestion.available_in_system;
    });
    const content = document.createElement('span');
    const heading = document.createElement('strong');
    heading.textContent = `${suggestion.code} · ${suggestion.title}`;
    const availability = document.createElement('span');
    availability.className = `account-availability ${suggestion.available_in_system ? 'available' : 'unavailable'}`;
    availability.textContent = suggestion.available_in_system
      ? 'Cadastrada no SH3/Siap — disponível para aprovação'
      : 'Não cadastrada no SH3/Siap — solicite inclusão antes de usar';
    const functionText = document.createElement('span');
    functionText.textContent = suggestion.function || 'Função não informada na tabela PCASP.';
    const nature = document.createElement('span');
    nature.textContent = `Natureza do saldo: ${suggestion.balance_nature || 'não informada'}${suggestion.status ? ` · Situação: ${suggestion.status}` : ''}`;
    const reason = document.createElement('span');
    reason.className = 'review-reason';
    reason.textContent = `Motivo da sugestão: ${suggestion.reasons.join(' ')}`;
    content.append(heading, availability, functionText, nature, reason);
    if (suggestion.details) {
      const metadata = document.createElement('details');
      metadata.className = 'review-account-metadata';
      const summary = document.createElement('summary');
      summary.textContent = 'Ver atributos e outros campos';
      const pre = document.createElement('pre');
      pre.textContent = suggestion.details;
      metadata.append(summary, pre);
      content.append(metadata);
    }
    option.append(radio, content);
    options.append(option);
  }
  const approveButton = document.querySelector('#approve-suggestion');
  approveButton.disabled = !selectedReviewAccount?.available_in_system;
  const hasAvailableOption = item.suggestions.some((suggestion) => suggestion.available_in_system);
  document.querySelector('#asset-review-guidance').textContent = hasAvailableOption
    ? `${item.guidance} Somente contas cadastradas no SH3 podem ser aprovadas e exportadas.`
    : `${item.guidance} Nenhuma candidata desta análise está cadastrada no SH3; consulte a SH3 para solicitar inclusão.`;
  assetReviewDialog.showModal();
}

document.querySelector('#close-asset-review').addEventListener('click', () => assetReviewDialog.close());
assetReviewDialog.addEventListener('click', (event) => { if (event.target === assetReviewDialog) assetReviewDialog.close(); });
document.querySelector('#approve-suggestion').addEventListener('click', async () => {
  if (!activeReviewItem || !selectedReviewAccount?.available_in_system) return;
  const button = document.querySelector('#approve-suggestion');
  button.disabled = true;
  try {
    await saveReviewDecision(activeReviewItem, 'approved', selectedReviewAccount);
  } catch (error) {
    showToast(error.message || 'Não foi possível salvar esta decisão.', true);
    button.disabled = false;
    return;
  }
  approvedReviewItems.set(activeReviewItem.row_index, { code: selectedReviewAccount.code, title: selectedReviewAccount.title });
  rejectedReviewItems.delete(activeReviewItem.row_index);
  renderReviewRows();
  assetReviewDialog.close();
  button.disabled = false;
});
document.querySelector('#reject-suggestion').addEventListener('click', async () => {
  if (!activeReviewItem) return;
  const button = document.querySelector('#reject-suggestion');
  button.disabled = true;
  try {
    await saveReviewDecision(activeReviewItem, 'keep');
  } catch (error) {
    showToast(error.message || 'Não foi possível salvar esta decisão.', true);
    button.disabled = false;
    return;
  }
  approvedReviewItems.delete(activeReviewItem.row_index);
  rejectedReviewItems.add(activeReviewItem.row_index);
  renderReviewRows();
  assetReviewDialog.close();
  button.disabled = false;
});

reviewForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const file = document.querySelector('#review-file').files?.[0];
  if (!file || !systemAccountFile) return;
  const button = reviewForm.querySelector('button[type="submit"]');
  button.disabled = true;
  button.textContent = 'Analisando…';
  const body = new FormData();
  body.append('inventario', file);
  body.append('plano_sh3', systemAccountFile);
  try {
    const response = await fetch('/api/inventory-review', { method: 'POST', body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível analisar o inventário.');
    reviewInventoryFile = file;
    reviewItems = data.recommendations;
    approvedReviewItems.clear();
    rejectedReviewItems.clear();
    for (const item of reviewItems) {
      if (item.saved_decision?.decision === 'approved') {
        approvedReviewItems.set(item.row_index, {
          code: item.saved_decision.account_code,
          title: item.saved_decision.account_title,
        });
      } else if (item.saved_decision?.decision === 'keep') {
        rejectedReviewItems.add(item.row_index);
      }
    }
    document.querySelector('#review-filter').value = '';
    document.querySelector('#review-summary').replaceChildren();
    for (const [value, label] of [
      [Number(data.item_count).toLocaleString('pt-BR'), 'bens com descrição analisados'],
      [Number(data.unique_descriptions).toLocaleString('pt-BR'), 'descrições distintas'],
      [Number(data.review_count).toLocaleString('pt-BR'), 'bens sugeridos para conferência'],
      [Number(data.unavailable_suggestion_codes).toLocaleString('pt-BR'), 'contas candidatas ausentes do SH3'],
    ]) {
      const card = document.createElement('div');
      card.className = 'summary-card';
      const strong = document.createElement('strong');
      strong.textContent = value;
      const small = document.createElement('span');
      small.textContent = label;
      card.append(strong, small);
      document.querySelector('#review-summary').append(card);
    }
    document.querySelector('#review-note').textContent = data.note;
    document.querySelector('#review-results').hidden = false;
    renderReviewRows();
    const savedCount = approvedReviewItems.size + rejectedReviewItems.size;
    if (savedCount) showToast(`${savedCount.toLocaleString('pt-BR')} decisão(ões) salva(s) anteriormente foram recuperadas.`);
    document.querySelector('#review-results').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) {
    showToast(error.message || 'Falha ao analisar os bens.', true);
  } finally {
    button.disabled = false;
    button.innerHTML = 'Analisar bens <span aria-hidden="true">→</span>';
  }
});

document.querySelector('#review-filter').addEventListener('input', renderReviewRows);
document.querySelector('#export-approved').addEventListener('click', async () => {
  if (!reviewInventoryFile || !systemAccountFile || approvedReviewItems.size === 0) return;
  const button = document.querySelector('#export-approved');
  button.disabled = true;
  button.textContent = 'Preparando cópia…';
  const body = new FormData();
  body.append('inventario', reviewInventoryFile);
  body.append('plano_sh3', systemAccountFile);
  body.append('aprovadas', new Blob([JSON.stringify([...approvedReviewItems].map(([row_index, value]) => ({ row_index, account_code: value.code })))]), 'aprovadas.json');
  try {
    const response = await fetch('/api/inventory-export', { method: 'POST', body });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || 'Não foi possível gerar a cópia aprovada.');
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = 'Localizar_Bens_alteracoes_aprovadas.csv';
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    showToast(`Cópia gerada com ${approvedReviewItems.size.toLocaleString('pt-BR')} alteração(ões) aprovada(s). O original permanece intacto.`);
  } catch (error) {
    showToast(error.message || 'Falha ao gerar a cópia aprovada.', true);
  } finally {
    button.textContent = 'Baixar cópia com aprovadas';
    button.disabled = approvedReviewItems.size === 0 || !systemAccountFile;
  }
});

document.querySelector('#export-account-summary').addEventListener('click', async () => {
  if (!reviewInventoryFile || !systemAccountFile) return;
  const button = document.querySelector('#export-account-summary');
  button.disabled = true;
  button.textContent = 'Preparando Excel…';
  const body = new FormData();
  body.append('inventario', reviewInventoryFile);
  body.append('plano_sh3', systemAccountFile);
  body.append('aprovadas', new Blob([JSON.stringify([...approvedReviewItems].map(([row_index, value]) => ({ row_index, account_code: value.code })))]), 'aprovadas.json');
  try {
    const response = await fetch('/api/inventory-summary', { method: 'POST', body });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || 'Não foi possível gerar o resumo por conta.');
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = 'Resumo_final_por_conta.xlsx';
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    const excludedCount = Number(response.headers.get('X-Summary-Excluded') || 0);
    showToast(excludedCount
      ? `Comparativo antes/depois gerado. ${excludedCount.toLocaleString('pt-BR')} bem(ns) sem correspondência foram excluídos dos totais finais e listados na planilha.`
      : 'Comparativo Excel antes/depois gerado por conta patrimonial.');
  } catch (error) {
    showToast(error.message || 'Falha ao gerar o resumo Excel por conta.', true);
  } finally {
    button.textContent = 'Baixar resumo Excel';
    button.disabled = !reviewInventoryFile || !systemAccountFile;
  }
});

document.querySelector('#system-account-file').addEventListener('change', (event) => {
  const hadAnalysis = Boolean(reviewInventoryFile);
  systemAccountFile = event.target.files?.[0] || null;
  if (hadAnalysis) {
    reviewInventoryFile = null;
    reviewItems = [];
    approvedReviewItems.clear();
    rejectedReviewItems.clear();
    document.querySelector('#review-results').hidden = true;
    showToast('A relação do SH3 mudou. Refaça a análise do inventário para atualizar as candidatas.');
  }
  updateReviewApprovalSummary();
});

document.querySelector('#clear-imports').addEventListener('click', () => {
  reconcileForm.reset();
  reviewForm.reset();
  document.querySelector('#system-account-file').value = '';
  document.querySelector('#reconcile-results').hidden = true;
  document.querySelector('#review-results').hidden = true;
  document.querySelector('#review-summary').replaceChildren();
  document.querySelector('#review-rows').replaceChildren();
  document.querySelector('#review-note').textContent = '';
  document.querySelector('#review-filter').value = '';
  document.querySelector('#review-filter-count').textContent = '';
  reviewInventoryFile = null;
  systemAccountFile = null;
  reviewItems = [];
  activeReviewItem = null;
  selectedReviewAccount = null;
  approvedReviewItems.clear();
  rejectedReviewItems.clear();
  if (assetReviewDialog.open) assetReviewDialog.close();
  updateReviewApprovalSummary();
  showToast('Arquivos e resultados desta tela foram limpos. As decisões salvas no banco local foram mantidas.');
});

document.querySelector('#clear-saved-reviews').addEventListener('click', async () => {
  if (!window.confirm('Apagar todas as decisões salvas da análise neste computador? Esta ação não pode ser desfeita.')) return;
  try {
    const response = await fetch('/api/inventory-review-decisions/clear', { method: 'POST', body: new FormData() });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível apagar as decisões salvas.');
    approvedReviewItems.clear();
    rejectedReviewItems.clear();
    for (const item of reviewItems) delete item.saved_decision;
    renderReviewRows();
    updateReviewApprovalSummary();
    showToast(`${Number(data.deleted || 0).toLocaleString('pt-BR')} decisão(ões) salva(s) apagada(s).`);
  } catch (error) {
    showToast(error.message || 'Não foi possível apagar as decisões salvas.', true);
  }
});

loadStatus();
