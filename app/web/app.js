const form = document.querySelector('#search-form');
const description = document.querySelector('#description');
const clearButton = document.querySelector('#clear-search');
const resultsSection = document.querySelector('#results-section');
const resultsList = document.querySelector('#results-list');
const resultCount = document.querySelector('#result-count');
const emptyState = document.querySelector('#empty-state');
const uploadInput = document.querySelector('#workbook');
const toast = document.querySelector('#toast');
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

function renderResults(results) {
  resultsList.replaceChildren();
  resultsSection.hidden = results.length === 0;
  emptyState.hidden = results.length !== 0;
  resultCount.textContent = `${results.length} ${results.length === 1 ? 'sugestão' : 'sugestões'}`;
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
    if (account.details) {
      const details = document.createElement('details');
      details.className = 'details';
      const summary = document.createElement('summary');
      summary.textContent = 'Ver atributos e informações adicionais';
      const content = document.createElement('pre');
      content.textContent = account.details;
      details.append(summary, content);
      main.append(details);
    }
    card.append(code, main);
    resultsList.append(card);
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const text = description.value.trim();
  if (!text) return;
  const kind = new FormData(form).get('kind') || '';
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  button.querySelector('span').textContent = 'Buscando…';
  try {
    const response = await fetch(`/api/search?q=${encodeURIComponent(text)}&tipo=${encodeURIComponent(kind)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível realizar a busca.');
    renderResults(data.results);
  } catch (error) {
    showToast(error.message || 'Falha ao conectar com o sistema.', true);
  } finally {
    button.disabled = false;
    button.querySelector('span').textContent = 'Buscar contas';
  }
});

description.addEventListener('input', () => { clearButton.hidden = !description.value; });
clearButton.addEventListener('click', () => {
  description.value = '';
  clearButton.hidden = true;
  description.focus();
  renderResults([]);
});

async function loadStatus() {
  const status = document.querySelector('#source-status');
  try {
    const response = await fetch('/api/status');
    const data = await response.json();
    const date = data.updated_at ? new Date(data.updated_at).toLocaleString('pt-BR') : '';
    status.textContent = data.account_count
      ? `${Number(data.account_count).toLocaleString('pt-BR')} contas · ${data.source}${date ? ` · Atualizada em ${date}` : ''}`
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
    renderResults([]);
  } catch (error) {
    showToast(error.message || 'Falha ao enviar a planilha.', true);
  } finally {
    uploadInput.value = '';
    document.querySelector('#file-hint').textContent = '.xlsx até 20 MB';
  }
});

loadStatus();
