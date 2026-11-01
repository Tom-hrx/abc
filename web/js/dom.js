/** 所有模型输出的渲染都走 textContent / createTextNode，不使用 innerHTML。 */

export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

/**
 * 按词汇区间把句子切成「普通文本 + <mark>」。
 * 区间取自模型给的 span_start / span_end（句内相对偏移）。
 * slice 越界只会得到空串，不需要额外防御。
 */
export function renderHighlighted(text, ranges) {
  const frag = document.createDocumentFragment();
  const valid = (ranges || [])
    .filter((r) => Number.isInteger(r.start) && Number.isInteger(r.end) && r.end > r.start)
    .sort((a, b) => a.start - b.start);

  let cursor = 0;
  for (const range of valid) {
    if (range.start < cursor) continue;
    frag.append(document.createTextNode(text.slice(cursor, range.start)));
    const mark = el("mark", null, text.slice(range.start, range.end));
    mark.dataset.lemma = range.lemma || "";
    mark.title = range.title || "";
    frag.append(mark);
    cursor = range.end;
  }
  frag.append(document.createTextNode(text.slice(cursor)));
  return frag;
}

export function setStep(stepList, stage, state) {
  const node = stepList.querySelector(`[data-step="${stage}"]`);
  if (!node) return;
  node.classList.remove("active", "done", "failed");
  if (state) node.classList.add(state);
}
