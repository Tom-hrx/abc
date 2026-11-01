import { api, describeError } from "./api.js";
import { clear, el, renderHighlighted, setStep } from "./dom.js";
import { MAX_COUNT, createUploader } from "./upload.js";

const $ = (id) => document.getElementById(id);

const ui = {
  dropzone: $("dropzone"),
  fileInput: $("fileInput"),
  thumbs: $("thumbs"),
  uploadAlert: $("uploadAlert"),
  imageCount: $("imageCount"),
  level: $("level"),
  docTitle: $("docTitle"),
  btnAnalyze: $("btnAnalyze"),
  steps: $("steps"),
  status: $("status"),
  usage: $("usage"),
  extractedBox: $("extractedBox"),
  extractedText: $("extractedText"),
  resultMeta: $("resultMeta"),
  empty: $("empty"),
  structureCard: $("structureCard"),
  stTitle: $("stTitle"),
  stGenre: $("stGenre"),
  stThesis: $("stThesis"),
  stDifficulty: $("stDifficulty"),
  stSections: $("stSections"),
  stFlow: $("stFlow"),
  stTips: $("stTips"),
  sentences: $("sentences"),
  fallbackNote: $("fallbackNote"),
  modeBadge: $("modeBadge"),
};

let busy = false;

const uploader = createUploader({
  dropzone: ui.dropzone,
  input: ui.fileInput,
  thumbs: ui.thumbs,
  onChange: (files, rejected) => {
    ui.imageCount.textContent = `${files.length} / ${MAX_COUNT}`;

    if (rejected && rejected.length) {
      ui.uploadAlert.hidden = false;
      ui.uploadAlert.textContent = rejected.join("；");
    } else {
      ui.uploadAlert.hidden = true;
      ui.uploadAlert.textContent = "";
    }

    if (!busy && files.length) setStatus(`已选择 ${files.length} 张图片，点击「识别并分析」。`);
    if (!files.length && !busy) setStatus("等待上传");
  },
});

function setStatus(text, { error = false, loading = false } = {}) {
  clear(ui.status);
  if (loading) ui.status.append(el("span", "spinner"));
  ui.status.append(document.createTextNode(text));
  ui.status.classList.toggle("error", error);
}

function setBusy(value) {
  busy = value;
  ui.btnAnalyze.disabled = value;
  ui.btnAnalyze.textContent = value ? "处理中…" : "识别并分析";
}

function resetSteps() {
  ui.steps.querySelectorAll("li").forEach((li) => li.classList.remove("active", "done", "failed"));
}

function resetResult() {
  ui.empty.hidden = false;
  ui.structureCard.hidden = true;
  ui.fallbackNote.hidden = true;
  ui.resultMeta.textContent = "";
  ui.usage.hidden = true;
  ui.extractedBox.hidden = true;
  ui.extractedText.textContent = "";
  clear(ui.sentences);
}

function renderStructure(structure) {
  if (!structure) return;
  ui.structureCard.hidden = false;
  ui.empty.hidden = true;

  ui.stTitle.textContent = structure.topic || "全文结构";
  ui.stGenre.textContent = structure.genre || "";
  ui.stThesis.textContent = structure.thesis || "";

  clear(ui.stDifficulty);
  const difficulty = structure.difficulty || {};
  const chips = [difficulty.level, difficulty.exam && `${difficulty.exam}难度`].filter(Boolean);
  chips.forEach((text) => ui.stDifficulty.append(el("span", null, text)));
  if (difficulty.reason) ui.stDifficulty.append(el("span", null, difficulty.reason));

  clear(ui.stSections);
  (structure.sections || []).forEach((section) => {
    const row = el("div", "section-row");
    const left = el("div");
    left.append(el("div", "role", section.role || ""));
    left.append(el("div", "paras", `P${(section.paragraphs || []).join("·")}`));
    row.append(left);
    row.append(el("div", null, section.summary_cn || ""));
    ui.stSections.append(row);
  });

  clear(ui.stFlow);
  (structure.logic_flow || []).forEach((step) => ui.stFlow.append(el("span", null, step)));

  clear(ui.stTips);
  (structure.reading_tips || []).forEach((tip) => ui.stTips.append(el("li", null, tip)));
}

function renderSentence(sentence) {
  const item = el("li", "sentence");

  const head = el("div", "sentence-head");
  head.append(el("span", "sentence-idx", `#${sentence.idx}`));

  const textNode = el("div", "sentence-text");
  const ranges = (sentence.vocab || []).map((vocab) => ({
    start: vocab.span_start,
    end: vocab.span_end,
    lemma: vocab.lemma,
    title: vocab.sense_cn || "",
  }));
  textNode.append(renderHighlighted(sentence.text || "", ranges));
  head.append(textNode);
  item.append(head);

  if (sentence.translation) item.append(el("p", "translation", sentence.translation));

  if (sentence.structure_hint) {
    const hint = el("p", "hint");
    hint.append(el("b", null, "骨架"));
    hint.append(document.createTextNode(sentence.structure_hint));
    item.append(hint);
  }

  const vocabList = el("div", "vocab-list");
  (sentence.vocab || []).forEach((vocab) => {
    const card = el("div", "vocab");
    const isTarget = Boolean(vocab.exam_label);
    if (isTarget) card.classList.add("target");

    card.append(el("span", "vocab-word", vocab.surface));
    card.append(document.createTextNode(` ${vocab.pos || ""} `));
    card.append(el("span", "vocab-sense", vocab.sense_cn || ""));
    card.append(el("span", isTarget ? "vocab-tag" : "vocab-tag none", vocab.exam_label || "不在词表"));

    if (vocab.pitfall_cn) card.append(el("span", "vocab-note", `易错 · ${vocab.pitfall_cn}`));
    if (vocab.exam_hint) card.append(el("span", "vocab-note", `考法 · ${vocab.exam_hint}`));
    vocabList.append(card);
  });
  if (vocabList.childElementCount) item.append(vocabList);

  const grammarList = el("div", "grammar-list");
  (sentence.grammar || []).forEach((grammar) => {
    const node = el("div", "grammar");
    node.append(el("b", null, grammar.label));
    node.append(document.createTextNode(` ${grammar.explain_cn || ""}`));
    if (grammar.exam_tip) node.append(el("span", "tip", `▸ ${grammar.exam_tip}`));
    grammarList.append(node);
  });
  if (grammarList.childElementCount) item.append(grammarList);

  return item;
}

function renderSentences(items) {
  clear(ui.sentences);
  items.forEach((sentence) => ui.sentences.append(renderSentence(sentence)));
  ui.empty.hidden = items.length > 0 || !ui.structureCard.hidden;
}

async function loadSentences(docId) {
  const page = await api.sentences(docId);
  renderSentences(page.items || []);
  ui.resultMeta.textContent = `${page.total} SENTENCES`;
}

async function run() {
  if (busy) return;

  const files = uploader.files;
  if (!files.length) {
    setStatus("请先上传文章图片。", { error: true });
    ui.dropzone.focus();
    return;
  }

  resetSteps();
  resetResult();
  setBusy(true);

  let docId = null;
  try {
    setStep(ui.steps, "vision", "active");
    setStatus(`图像识别中…（${files.length} 张，模型逐张转写）`, { loading: true });

    const created = await api.fromImage(files, ui.level.value, ui.docTitle.value.trim());
    docId = created.id;
    const extraction = created.extraction || {};
    setStep(ui.steps, "vision", "done");

    ui.extractedBox.hidden = false;
    ui.extractedText.textContent = extraction.text || "";
    const noteText = (extraction.notes || []).join("；");
    setStatus(
      `识别完成：${created.char_count} 字符${extraction.complete ? "" : "（部分内容可能看不清）"}${noteText ? ` · ${noteText}` : ""}`,
      { error: extraction.complete === false }
    );

    setStep(ui.steps, "segment", "active");
    setStatus("分段切句中…", { loading: true });
    const segment = await api.analyze(docId, ["segment"]);
    const segResult = (segment.stages && segment.stages.segment) || {};
    let segmentOk = segResult.status !== "failed";
    if (!segmentOk) {
      setStep(ui.steps, "segment", "failed");
      ui.fallbackNote.hidden = false;
      setStatus(`分段失败：${describeError({ code: segResult.error_code, message: segResult.error_message })}`, {
        error: true,
      });
    } else {
      setStep(ui.steps, "segment", "done");
      setStatus(`分段完成：${segResult.sentence_count} 句`, { loading: true });
    }

    setStep(ui.steps, "structure", "active");
    setStatus("分析全文结构…", { loading: true });
    const structure = await api.analyze(docId, ["structure"]);
    const stResult = (structure.stages && structure.stages.structure) || {};
    if (stResult.status === "failed") {
      setStep(ui.steps, "structure", "failed");
      setStatus(`结构分析失败：${describeError({ code: stResult.error_code })}`, { error: true });
    } else {
      setStep(ui.steps, "structure", "done");
      const doc = await api.document(docId);
      renderStructure(doc.structure);
    }

    if (!segmentOk) {
      setStep(ui.steps, "sentences", "failed");
      setStatus("分段未完成，逐句精讲已跳过。重新上传或重试可解决。", { error: true });
    } else {
      setStep(ui.steps, "sentences", "active");
      setStatus("逐句精讲中…（长文需要 1–3 分钟）", { loading: true });
      const result = await api.analyze(docId, ["sentences"]);
      const snResult = (result.stages && result.stages.sentences) || {};
      if (snResult.status === "failed") {
        setStep(ui.steps, "sentences", "failed");
        setStatus(`逐句精讲失败：${describeError({ code: snResult.error_code })}`, { error: true });
      } else {
        setStep(ui.steps, "sentences", "done");
        await loadSentences(docId);
        setStatus(`完成：${snResult.analyzed} 句已精讲`);
      }
    }

    try {
      const runs = await api.runs(docId);
      const total = runs.total || {};
      ui.usage.hidden = false;
      ui.usage.textContent =
        `CALLS ${total.calls} · IN ${total.input_tokens} · OUT ${total.output_tokens} · $${total.cost_usd}`;
    } catch {
      /* 账单失败不影响主流程 */
    }
  } catch (error) {
    setStatus(`出错了：${describeError(error)}`, { error: true });
    ui.steps.querySelectorAll("li.active").forEach((li) => {
      li.classList.remove("active");
      li.classList.add("failed");
    });
    if (!docId) ui.extractedBox.hidden = true;
  } finally {
    setBusy(false);
  }
}

async function refreshMode() {
  try {
    const health = await api.health();
    const fake = health.llm_mode === "fake";
    ui.modeBadge.textContent = fake ? "FIXTURE MODE" : `MODEL ${health.llm_mode}`;
    ui.modeBadge.classList.toggle("fake", fake);
    ui.modeBadge.title = fake
      ? "当前用录制的测试夹具：上传图片不会真的被识别。在 backend/.env 配置 LLM_API_KEY 并重启后才是真实识别。"
      : `目标学段默认 ${health.target_level}，词表 ${health.exam_words} 条`;
  } catch {
    ui.modeBadge.textContent = "OFFLINE";
    ui.modeBadge.classList.add("fake");
    setStatus("连不上后端服务，确认 flask 是否在运行。", { error: true });
  }
}

ui.btnAnalyze.addEventListener("click", run);

refreshMode();
